"""Telegram bot handler for EasyPomodoro project consultant."""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, NetworkError

from config import TELEGRAM_BOT_TOKEN, WELCOME_MESSAGE, ERROR_MESSAGE
from backend_client import BackendClient

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

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user_id = update.effective_user.id
        logger.info(f"User {user_id}: /start command")
        await retry_telegram_call(update.message.reply_text, WELCOME_MESSAGE)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user messages with async polling."""
        user_id = update.effective_user.id
        user_message = update.message.text

        logger.info(f"User {user_id}: Received message: {user_message}")

        thinking_msg = None

        try:
            # Show initial thinking indicator
            thinking_msg = await retry_telegram_call(update.message.reply_text, "Думаю...")

            # Submit task to backend
            task_id = await self.backend_client.submit_chat_async(
                user_id=str(user_id),
                message=user_message
            )

            logger.info(f"User {user_id}: Task submitted {task_id}, starting polling")

            # Poll for result with progress updates
            interval = 30  # Poll every 30 seconds
            max_wait = 1800  # 10 minutes max
            elapsed = 0

            while elapsed < max_wait:
                try:
                    task_data = await self.backend_client.get_task_status(task_id)
                    status = task_data.get("status")

                    logger.info(f"User {user_id}: Task {task_id} status={status}, elapsed={elapsed}s")

                    if status == "completed":
                        # Task completed - extract result
                        result = task_data.get("result", {})
                        response_text = result.get("response", "")
                        mcp_used = result.get("mcp_used", False)

                        # Delete thinking message
                        await retry_telegram_call(thinking_msg.delete)
                        thinking_msg = None

                        # Send final response
                        if response_text:
                            await retry_telegram_call(update.message.reply_text, response_text)
                        else:
                            await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)

                        logger.info(f"User {user_id}: Task {task_id} completed successfully")
                        return

                    elif status == "failed":
                        # Task failed
                        error = task_data.get("error", "Unknown error")
                        logger.error(f"User {user_id}: Task {task_id} failed: {error}")

                        await retry_telegram_call(thinking_msg.delete)
                        thinking_msg = None

                        await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)
                        return

                    # Still pending or processing - update progress indicator
                    elapsed += interval
                    minutes = elapsed // 60
                    seconds = elapsed % 60

                    if minutes > 0:
                        progress_text = f"Думаю... ({minutes} мин {seconds} сек)"
                    else:
                        progress_text = f"Думаю... ({seconds} сек)"

                    try:
                        await retry_telegram_call(thinking_msg.edit_text, progress_text)
                    except Exception as e:
                        logger.warning(f"User {user_id}: Failed to update progress message: {e}")

                    # Wait before next poll
                    await asyncio.sleep(interval)

                except Exception as e:
                    if "not found" in str(e).lower():
                        logger.error(f"User {user_id}: Task {task_id} not found (expired)")
                        raise Exception("Task expired")
                    raise

            # Timeout
            logger.error(f"User {user_id}: Task {task_id} timed out after {max_wait}s")
            raise Exception("Request timed out")

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
