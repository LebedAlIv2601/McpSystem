"""Telegram bot handler."""

import asyncio
import json
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
from subscribers import SubscriberManager

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
        self.subscriber_manager = SubscriberManager()
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

        # Track user interaction
        self.subscriber_manager.track_user_interaction(user_id)

        await retry_telegram_call(update.message.reply_text, WELCOME_MESSAGE)

    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tasks command."""
        user_id = update.effective_user.id
        full_message = update.message.text

        logger.info(f"User {user_id}: /tasks command: {full_message}")

        # Track user interaction
        self.subscriber_manager.track_user_interaction(user_id)

        user_query = full_message.replace("/tasks", "", 1).strip()

        if not user_query:
            user_query = "Show me all my tasks"

        thinking_msg = None

        try:
            if self.conversation_manager.check_and_clear_if_full(user_id):
                logger.info(f"User {user_id}: History cleared (reached limit)")
                await update.message.reply_text("Conversation history cleared due to message limit.")

            self.conversation_manager.add_message(user_id, "user", user_query)

            thinking_msg = await retry_telegram_call(update.message.reply_text, "Думаю...")

            response_text = await self._process_with_openrouter(user_id, user_query, force_tool_use=True)

            await retry_telegram_call(thinking_msg.delete)
            thinking_msg = None

            if response_text:
                mcp_indicator_present = MCP_USED_INDICATOR in response_text

                clean_response = response_text.replace(MCP_USED_INDICATOR, "").strip() if mcp_indicator_present else response_text
                self.conversation_manager.add_message(user_id, "assistant", clean_response)

                await retry_telegram_call(update.message.reply_text, response_text)
            else:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)

        except Exception as e:
            logger.error(f"User {user_id}: Error handling /tasks command: {e}", exc_info=True)
            if thinking_msg:
                try:
                    await retry_telegram_call(thinking_msg.delete)
                except Exception:
                    pass
            try:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)
            except Exception:
                logger.error(f"User {user_id}: Failed to send error message to user")

    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /fact command."""
        user_id = update.effective_user.id
        full_message = update.message.text

        logger.info(f"User {user_id}: /fact command: {full_message}")

        # Track user interaction
        self.subscriber_manager.track_user_interaction(user_id)

        user_query = full_message.replace("/fact", "", 1).strip()

        if not user_query:
            user_query = "Give me a random fact"

        thinking_msg = None

        try:
            if self.conversation_manager.check_and_clear_if_full(user_id):
                logger.info(f"User {user_id}: History cleared (reached limit)")
                await update.message.reply_text("Conversation history cleared due to message limit.")

            self.conversation_manager.add_message(user_id, "user", user_query)

            thinking_msg = await retry_telegram_call(update.message.reply_text, "Думаю...")

            response_text = await self._process_with_openrouter(user_id, user_query, force_fact_use=True)

            await retry_telegram_call(thinking_msg.delete)
            thinking_msg = None

            if response_text:
                mcp_indicator_present = MCP_USED_INDICATOR in response_text

                clean_response = response_text.replace(MCP_USED_INDICATOR, "").strip() if mcp_indicator_present else response_text
                self.conversation_manager.add_message(user_id, "assistant", clean_response)

                await retry_telegram_call(update.message.reply_text, response_text)
            else:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)

        except Exception as e:
            logger.error(f"User {user_id}: Error handling /fact command: {e}", exc_info=True)
            if thinking_msg:
                try:
                    await retry_telegram_call(thinking_msg.delete)
                except Exception:
                    pass
            try:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)
            except Exception:
                logger.error(f"User {user_id}: Failed to send error message to user")

    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /subscribe command."""
        user_id = update.effective_user.id
        logger.info(f"User {user_id}: /subscribe command")

        # Track user interaction
        self.subscriber_manager.track_user_interaction(user_id)

        # Add to subscribers
        self.subscriber_manager.add_subscriber(user_id)

        await retry_telegram_call(
            update.message.reply_text,
            "✅ You will now receive task summaries every 2 minutes."
        )

    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /unsubscribe command."""
        user_id = update.effective_user.id
        logger.info(f"User {user_id}: /unsubscribe command")

        # Track user interaction
        self.subscriber_manager.track_user_interaction(user_id)

        # Remove from subscribers
        self.subscriber_manager.remove_subscriber(user_id)

        await retry_telegram_call(
            update.message.reply_text,
            "🔕 Periodic summaries disabled."
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user messages."""
        user_id = update.effective_user.id
        user_message = update.message.text

        logger.info(f"User {user_id}: Received message: {user_message}")

        # Track user interaction
        self.subscriber_manager.track_user_interaction(user_id)

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

    async def _process_with_openrouter(self, user_id: int, user_message: str, force_tool_use: bool = False, force_fact_use: bool = False) -> Optional[str]:
        """
        Process message with OpenRouter and MCP tools.

        Args:
            user_id: User ID
            user_message: User's message
            force_tool_use: If True, instructs model to use get_tasks tool
            force_fact_use: If True, instructs model to use get_fact tool

        Returns:
            Response text or None if error
        """
        conversation_history = self.conversation_manager.get_history(user_id)

        current_date = datetime.now().strftime("%Y-%m-%d")

        if force_tool_use:
            system_prompt = {
                "role": "system",
                "content": f"""Current date: {current_date}. All dates must be calculated relative to this date.

IMPORTANT INSTRUCTIONS:
- You are a task management assistant with access to the user's tasks via the get_tasks tool.
- ALWAYS use the get_tasks tool when the user asks about their tasks.
- The tool provides real-time task data from Weeek task tracker.
- After retrieving tasks, present them in a clear, organized format.
- Tasks have three states: Backlog, In progress, and Done.
- Use the tool immediately to get current task information."""
            }
        elif force_fact_use:
            system_prompt = {
                "role": "system",
                "content": f"""Current date: {current_date}. All dates must be calculated relative to this date.

IMPORTANT INSTRUCTIONS:
- You are a helpful assistant with access to random facts via the get_fact tool.
- ALWAYS use the get_fact tool when the user asks for a fact or interesting information.
- The tool provides random facts from various topics.
- After retrieving the fact, present it in a friendly, engaging way.
- Use the tool immediately to get a random fact."""
            }
        else:
            system_prompt = {
                "role": "system",
                "content": f"""Current date: {current_date}. All dates must be calculated relative to this date.

You are a helpful assistant with access to task management and random facts tools.
- If the user asks about tasks, use the get_tasks tool to retrieve current task information.
- If the user asks for a fact or interesting information, use the get_fact tool.
- You can use multiple tools in sequence if needed. For example, if the user asks to check their tasks and give a fact based on a condition, first use get_tasks, evaluate the condition, and then use get_fact if the condition is met."""
            }

        messages_with_system = [system_prompt] + conversation_history

        mcp_was_used = False

        tool_choice = "auto" if self.openrouter_tools else None

        try:
            # Support chained tool calls with iteration limit
            max_iterations = 15
            iteration = 0
            current_messages = messages_with_system
            response_text = None

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"User {user_id}: Tool call iteration {iteration}/{max_iterations}")

                response_text, tool_calls = await self.openrouter_client.chat_completion(
                    messages=current_messages,
                    tools=self.openrouter_tools if self.openrouter_tools else None,
                    tool_choice=tool_choice
                )

                if not tool_calls:
                    # No more tool calls, we're done
                    logger.info(f"User {user_id}: No tool calls in iteration {iteration}, finishing")
                    break

                # Process tool calls
                logger.info(f"User {user_id}: Processing {len(tool_calls)} tool calls in iteration {iteration}")
                mcp_was_used = True

                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["arguments"]

                    logger.info(f"User {user_id}: Executing tool {tool_name}")

                    try:
                        result = await self.mcp_manager.call_tool(tool_name, tool_args)
                        result_content = result["result"]

                        try:
                            parsed_result = json.loads(result_content)
                            if isinstance(parsed_result, dict) and "error" in parsed_result:
                                logger.error(f"User {user_id}: MCP tool returned error: {parsed_result['error']}")
                        except (json.JSONDecodeError, ValueError):
                            pass

                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result_content
                        })
                    except Exception as e:
                        logger.error(f"User {user_id}: Tool execution error: {e}", exc_info=True)
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps({"error": str(e)})
                        })

                # Build conversation with tool results for next iteration
                conversation_with_tools = conversation_history.copy()

                # Add all previous iterations from current_messages (excluding system prompt)
                for msg in current_messages[1:]:
                    if msg["role"] in ["assistant", "tool"]:
                        conversation_with_tools.append(msg)

                # Add current assistant response with tool calls if present
                if response_text:
                    conversation_with_tools.append({"role": "assistant", "content": response_text})

                # Add tool results
                for tr in tool_results:
                    conversation_with_tools.append(tr)

                # Prepare for next iteration
                current_messages = [system_prompt] + conversation_with_tools

            if response_text and mcp_was_used:
                response_text += MCP_USED_INDICATOR

            return response_text

        except Exception as e:
            logger.error(f"User {user_id}: OpenRouter processing error: {e}", exc_info=True)
            return None

    async def run(self) -> None:
        """Run the Telegram bot."""
        from telegram.request import HTTPXRequest

        # Increase timeout for slow connections
        request = HTTPXRequest(connection_pool_size=8, connect_timeout=30.0, read_timeout=30.0)
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("tasks", self.tasks_command))
        self.application.add_handler(CommandHandler("fact", self.fact_command))
        self.application.add_handler(CommandHandler("subscribe", self.subscribe_command))
        self.application.add_handler(CommandHandler("unsubscribe", self.unsubscribe_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Starting Telegram bot")
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            logger.info("Telegram bot is running")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            logger.error("Check your internet connection and Telegram API accessibility")
            raise

    async def stop(self) -> None:
        """Stop the Telegram bot."""
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
