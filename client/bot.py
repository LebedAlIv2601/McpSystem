"""Telegram bot handler for EasyPomodoro project consultant."""

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
    MCP_USED_INDICATOR,
    ESSENTIAL_TOOLS
)
from conversation import ConversationManager
from openrouter_client import OpenRouterClient
from mcp_manager import MCPManager

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

    def __init__(self, mcp_manager: MCPManager):
        self.mcp_manager = mcp_manager
        self.conversation_manager = ConversationManager()
        self.openrouter_client = OpenRouterClient()
        self.application: Optional[Application] = None
        self.openrouter_tools = []

    def initialize(self) -> None:
        """Initialize bot with MCP tools."""
        mcp_tools = self.mcp_manager.get_tools()

        # Log all available tools from MCP
        logger.info(f"=== ALL MCP TOOLS ({len(mcp_tools)}) ===")
        for tool in mcp_tools:
            logger.info(f"  - {tool['name']}: {tool.get('description', '')[:80]}...")

        # Filter to essential tools only to reduce token usage
        filtered_tools = [t for t in mcp_tools if t["name"] in ESSENTIAL_TOOLS]
        logger.info(f"Filtered tools: {len(filtered_tools)}/{len(mcp_tools)} (saved ~{(len(mcp_tools) - len(filtered_tools)) * 60} tokens)")

        self.openrouter_tools = self.openrouter_client.convert_mcp_tools_to_openrouter(filtered_tools)
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
                mcp_indicator_present = MCP_USED_INDICATOR in response_text
                clean_response = response_text.replace(MCP_USED_INDICATOR, "").strip() if mcp_indicator_present else response_text
                self.conversation_manager.add_message(user_id, "assistant", clean_response)

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

    async def _process_with_openrouter(self, user_id: int, user_message: str) -> Optional[str]:
        """Process message with OpenRouter and MCP tools."""
        conversation_history = self.conversation_manager.get_history(user_id)
        current_date = datetime.now().strftime("%Y-%m-%d")

        system_prompt = {
            "role": "system",
            "content": f"""Current date: {current_date}.

You are a project consultant for EasyPomodoro Android app (repo: LebedAlIv2601/EasyPomodoro).

**TOOLS:**

1. **get_project_structure** - Get directory tree. USE FIRST to find file paths!
   Example: get_project_structure(path="app/src/main/java", max_depth=4)

2. **get_file_contents** - Read file content (use exact path from structure)
   Example: get_file_contents(owner="LebedAlIv2601", repo="EasyPomodoro", path="app/.../MainActivity.kt")

3. **rag_query** - Search project documentation

4. **list_commits**, **list_issues**, **list_pull_requests** - GitHub items

**WORKFLOW:**
1. For code → get_project_structure to find paths → get_file_contents to read
2. For architecture → rag_query
3. ALWAYS provide complete answer after using tools

Respond in user's language."""
        }

        messages_with_system = [system_prompt] + conversation_history
        mcp_was_used = False

        tool_choice = "auto" if self.openrouter_tools else None

        try:
            max_iterations = 5
            iteration = 0
            current_messages = messages_with_system
            response_text = None
            accumulated_content = []  # Collect content from all iterations

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"User {user_id}: Tool call iteration {iteration}/{max_iterations}")

                # On last iteration, disable tools to force final response
                is_last_iteration = (iteration == max_iterations)
                current_tools = None if is_last_iteration else self.openrouter_tools
                current_tool_choice = None if is_last_iteration else tool_choice

                response_text, tool_calls = await self.openrouter_client.chat_completion(
                    messages=current_messages,
                    tools=current_tools if current_tools else None,
                    tool_choice=current_tool_choice
                )

                # Accumulate non-empty content
                if response_text:
                    accumulated_content.append(response_text)

                if not tool_calls:
                    logger.info(f"User {user_id}: No tool calls in iteration {iteration}, finishing")
                    # Use accumulated content if final response is empty
                    if not response_text and accumulated_content:
                        response_text = accumulated_content[-1]  # Use last non-empty
                        logger.info(f"User {user_id}: Using accumulated content")
                    logger.info(f"User {user_id}: Final response_text: {response_text[:200] if response_text else 'None'}")
                    break

                logger.info(f"User {user_id}: Processing {len(tool_calls)} tool calls")
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

                # Add assistant message with tool_calls for proper API format
                assistant_msg = {"role": "assistant", "content": response_text or ""}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"])
                        }
                    }
                    for tc in tool_calls
                ]
                current_messages.append(assistant_msg)

                # Add tool results
                for tr in tool_results:
                    current_messages.append(tr)

            if response_text and mcp_was_used:
                response_text += MCP_USED_INDICATOR

            return response_text

        except Exception as e:
            logger.error(f"User {user_id}: OpenRouter processing error: {e}", exc_info=True)
            return None

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
