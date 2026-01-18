"""Telegram bot handler for EasyPomodoro project consultant."""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, NetworkError

from config import TELEGRAM_BOT_TOKEN, WELCOME_MESSAGE, ERROR_MESSAGE, GITHUB_TOKEN
from backend_client import BackendClient
from build_handler import BuildHandler

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

    def __init__(self):
        self.backend_client = BackendClient()
        self.application: Optional[Application] = None
        self.build_handler: Optional[BuildHandler] = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user_id = update.effective_user.id
        logger.info(f"User {user_id}: /start command")
        await retry_telegram_call(update.message.reply_text, WELCOME_MESSAGE)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user messages."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user_message = update.message.text

        logger.info(f"User {user_id}: Received message: {user_message}")

        thinking_msg = None

        try:
            # Show thinking indicator
            thinking_msg = await retry_telegram_call(update.message.reply_text, "Думаю...")

            # Send message to backend
            result = await self.backend_client.send_message(
                user_id=str(user_id),
                message=user_message
            )

            # Delete thinking message
            await retry_telegram_call(thinking_msg.delete)
            thinking_msg = None

            # Send response
            if result.response:
                await retry_telegram_call(update.message.reply_text, result.response)
            else:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)

            # Handle build request if present
            if result.build_request and self.build_handler:
                await self.build_handler.handle_build_request(
                    chat_id=chat_id,
                    user_id=str(user_id),
                    workflow_run_id=result.build_request.workflow_run_id,
                    branch=result.build_request.branch
                )

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

            # Initialize build handler after application is ready (need bot instance)
            if GITHUB_TOKEN:
                self.build_handler = BuildHandler(
                    bot=self.application.bot,
                    backend_client=self.backend_client
                )
                logger.info("Build handler initialized")
            else:
                logger.warning("GITHUB_TOKEN not set - build functionality disabled")

            await self.application.updater.start_polling()
            logger.info("Telegram bot is running")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        # Close build handler
        if self.build_handler:
            await self.build_handler.close()

        # Close backend client
        await self.backend_client.close()

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
