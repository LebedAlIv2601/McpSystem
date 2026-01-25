"""Telegram bot handler for EasyPomodoro project consultant."""

import asyncio
import logging
import json
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, NetworkError

from config import TELEGRAM_BOT_TOKEN, WELCOME_MESSAGE, ERROR_MESSAGE, ANALYTICS_KEYWORDS
from ollama_client import OllamaClient
from analytics_manager import AnalyticsManager
from analytics_prompts import get_analytics_prompt

logger = logging.getLogger(__name__)


async def retry_telegram_call(func, *args, max_retries=3, **kwargs):
    """Retry Telegram API calls with exponential backoff on network errors."""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except (TimedOut, NetworkError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Telegram API call failed after {max_retries} attempts: {e}")
                raise

            wait_time = 2 ** attempt
            logger.warning(f"Telegram API timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)


class TelegramBot:
    """Telegram bot for EasyPomodoro project consultation."""

    def __init__(self, analytics_manager: AnalyticsManager):
        self.ollama_client = OllamaClient()
        self.analytics_manager = analytics_manager
        self.application: Optional[Application] = None

    def _is_analytics_query(self, message: str) -> bool:
        """Check if message is an analytics query."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in ANALYTICS_KEYWORDS)

    async def _handle_analytics_query(self, user_message: str) -> str:
        """Handle analytics query using MCP tools."""
        try:
            # Determine which analytics tool to use based on keywords
            message_lower = user_message.lower()
            analytics_data = None

            if any(word in message_lower for word in ["ошибк", "error"]):
                logger.info("Calling analyze_errors tool")
                analytics_data = await self.analytics_manager.analyze_errors()
                tool_name = "analyze_errors"

            elif any(word in message_lower for word in ["воронк", "funnel", "конверс", "conversion"]):
                logger.info("Calling analyze_funnel tool")
                analytics_data = await self.analytics_manager.analyze_funnel()
                tool_name = "analyze_funnel"

            elif any(word in message_lower for word in ["теряю", "dropoff", "отток", "abandon"]):
                logger.info("Calling analyze_dropoff tool")
                analytics_data = await self.analytics_manager.analyze_dropoff()
                tool_name = "analyze_dropoff"

            elif any(word in message_lower for word in ["статистик", "statistic", "общ"]):
                logger.info("Calling get_statistics tool")
                analytics_data = await self.analytics_manager.get_statistics()
                tool_name = "get_statistics"

            else:
                # Default to statistics for general analytics queries
                logger.info("Calling get_statistics tool (default)")
                analytics_data = await self.analytics_manager.get_statistics()
                tool_name = "get_statistics"

            # Format data for Ollama
            analytics_context = f"""Вопрос пользователя: {user_message}

Использованный инструмент: {tool_name}

Данные из системы аналитики:
```json
{json.dumps(analytics_data, ensure_ascii=False, indent=2)}
```

Проанализируй эти данные и дай структурированный ответ на вопрос пользователя.
"""

            # Send to Ollama with analytics system prompt
            response = await self.ollama_client.send_message_with_system_prompt(
                user_id="analytics",
                message=analytics_context,
                system_prompt=get_analytics_prompt()
            )

            return response

        except Exception as e:
            logger.error(f"Analytics query error: {e}", exc_info=True)
            return f"Ошибка при анализе данных: {str(e)}"

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user_id = update.effective_user.id
        logger.info(f"User {user_id}: /start command")
        await retry_telegram_call(update.message.reply_text, WELCOME_MESSAGE)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user messages."""
        user_id = update.effective_user.id
        user_message = update.message.text

        logger.info(f"User {user_id}: Received message: {user_message}")

        thinking_msg = None

        try:
            # Show thinking indicator
            thinking_msg = await retry_telegram_call(update.message.reply_text, "Думаю...")

            # Check if this is an analytics query
            if self._is_analytics_query(user_message):
                logger.info(f"User {user_id}: Analytics query detected")
                response_text = await self._handle_analytics_query(user_message)
            else:
                # Regular message - send to Ollama
                logger.info(f"User {user_id}: Regular query")
                response_text = await self.ollama_client.send_message(
                    user_id=str(user_id),
                    message=user_message
                )

            # Delete thinking message
            await retry_telegram_call(thinking_msg.delete)
            thinking_msg = None

            # Send response
            if response_text:
                await retry_telegram_call(update.message.reply_text, response_text)
            else:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)

        except Exception as e:
            logger.error(f"User {user_id}: Error handling message: {e}", exc_info=True)
            if thinking_msg:
                try:
                    await retry_telegram_call(thinking_msg.delete)
                except Exception:
                    pass
            try:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)
            except Exception:
                logger.error(f"User {user_id}: Failed to send error message")

    async def run(self) -> None:
        """Run the Telegram bot."""
        from telegram.request import HTTPXRequest

        request = HTTPXRequest(connection_pool_size=8, connect_timeout=30.0, read_timeout=30.0)
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Starting Telegram bot")
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            logger.info("Telegram bot is running")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        # Close Ollama client
        await self.ollama_client.close()

        if self.application:
            logger.info("Stopping Telegram bot")
            try:
                if self.application.updater and self.application.updater.running:
                    await self.application.updater.stop()
            except Exception as e:
                logger.warning(f"Error stopping updater: {e}")

            try:
                await self.application.stop()
            except Exception as e:
                logger.warning(f"Error stopping application: {e}")

            try:
                await self.application.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down application: {e}")

            logger.info("Telegram bot stopped")
