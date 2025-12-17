"""Telegram bot handler."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, NetworkError

from config import (
    TELEGRAM_BOT_TOKEN,
    WELCOME_MESSAGE,
    ERROR_MESSAGE,
    MCP_USED_INDICATOR
)
from conversation import ConversationManager
from openrouter_client import OpenRouterClient
from mcp_manager import MCPManager

logger = logging.getLogger(__name__)


async def retry_telegram_call(func, *args, max_retries=3, **kwargs):
    """
    Retry Telegram API calls with exponential backoff on network errors.

    Args:
        func: Async function to call
        max_retries: Maximum number of retry attempts
        *args, **kwargs: Arguments to pass to function

    Returns:
        Result of function call
    """
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except (TimedOut, NetworkError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Telegram API call failed after {max_retries} attempts: {e}")
                raise

            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            logger.warning(f"Telegram API timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)


class TelegramBot:
    """Telegram bot with OpenRouter and MCP integration."""

    def __init__(self, mcp_manager: MCPManager):
        self.mcp_manager = mcp_manager
        self.conversation_manager = ConversationManager()
        self.openrouter_client = OpenRouterClient()
        self.application: Optional[Application] = None
        self.openrouter_tools = []

    def initialize(self) -> None:
        """Initialize bot with MCP tools."""
        mcp_tools = self.mcp_manager.get_tools()
        self.openrouter_tools = self.openrouter_client.convert_mcp_tools_to_openrouter(mcp_tools)
        logger.info(f"Bot initialized with {len(self.openrouter_tools)} tools")

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
            if self.conversation_manager.check_and_clear_if_full(user_id):
                logger.info(f"User {user_id}: History cleared (reached limit)")
                await update.message.reply_text("Conversation history cleared due to message limit.")

            self.conversation_manager.add_message(user_id, "user", user_message)

            thinking_msg = await retry_telegram_call(update.message.reply_text, "Думаю...")

            response_text = await self._process_with_openrouter(user_id, user_message)

            await retry_telegram_call(thinking_msg.delete)
            thinking_msg = None

            if response_text:
                # Check if MCP indicator is present in response
                mcp_indicator_present = MCP_USED_INDICATOR in response_text

                # Store response WITHOUT indicator in conversation history
                clean_response = response_text.replace(MCP_USED_INDICATOR, "").strip() if mcp_indicator_present else response_text
                self.conversation_manager.add_message(user_id, "assistant", clean_response)

                # Send full response with indicator to user
                await retry_telegram_call(update.message.reply_text, response_text)
            else:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)

        except Exception as e:
            logger.error(f"User {user_id}: Error handling message: {e}", exc_info=True)
            if thinking_msg:
                try:
                    await retry_telegram_call(thinking_msg.delete)
                except Exception:
                    pass  # If delete fails, just continue
            try:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)
            except Exception:
                logger.error(f"User {user_id}: Failed to send error message to user")

    async def _process_with_openrouter(self, user_id: int, user_message: str) -> Optional[str]:
        """
        Process message with OpenRouter and MCP tools.

        Args:
            user_id: User ID
            user_message: User's message

        Returns:
            Response text or None if error
        """
        conversation_history = self.conversation_manager.get_history(user_id)

        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = {
            "role": "system",
            "content": f"""Current date: {current_date}. All dates must be calculated relative to this date.

IMPORTANT INSTRUCTIONS:
- You are a weather assistant with access to real-time weather data via the get_weather_forecast tool.
- ALWAYS use the get_weather_forecast tool when the user asks about weather, temperature, precipitation, or forecast.
- NEVER make up, guess, or hallucinate weather information.
- The tool provides accurate, live weather data - you must use it for all weather queries.
- If the user asks about weather in any location or any date, call the tool immediately.
- Do not provide weather information from your training data - always use the tool."""
        }
        messages_with_system = [system_prompt] + conversation_history

        mcp_was_used = False

        # Always use tool_choice="auto" to encourage tool usage
        # The system prompt instructs model to use tools for weather queries
        # This ensures follow-up questions like "What about Paris?" also use MCP
        tool_choice = "auto" if self.openrouter_tools else None

        try:
            response_text, tool_calls = await self.openrouter_client.chat_completion(
                messages=messages_with_system,
                tools=self.openrouter_tools if self.openrouter_tools else None,
                tool_choice=tool_choice
            )

            if tool_calls:
                logger.info(f"User {user_id}: Processing {len(tool_calls)} tool calls")
                mcp_was_used = True

                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["arguments"]

                    logger.info(f"User {user_id}: Executing tool {tool_name}")

                    try:
                        result = await self.mcp_manager.call_tool(tool_name, tool_args)
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result["result"]
                        })
                    except Exception as e:
                        logger.error(f"User {user_id}: Tool execution error: {e}", exc_info=True)
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": f"Error: {str(e)}"
                        })

                conversation_with_tools = conversation_history.copy()
                if response_text:
                    conversation_with_tools.append({"role": "assistant", "content": response_text})

                for tr in tool_results:
                    conversation_with_tools.append(tr)

                messages_with_tools_and_system = [system_prompt] + conversation_with_tools

                final_response, _ = await self.openrouter_client.chat_completion(
                    messages=messages_with_tools_and_system,
                    tools=None
                )

                response_text = final_response

            if response_text and mcp_was_used:
                response_text += MCP_USED_INDICATOR

            return response_text

        except Exception as e:
            logger.error(f"User {user_id}: OpenRouter processing error: {e}", exc_info=True)
            return None

    async def run(self) -> None:
        """Run the Telegram bot."""
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Starting Telegram bot")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        logger.info("Telegram bot is running")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self.application:
            logger.info("Stopping Telegram bot")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")
