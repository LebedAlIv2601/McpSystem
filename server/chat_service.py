"""Chat service for processing messages with Ollama and MCP tools."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Tuple

from config import ESSENTIAL_TOOLS, MCP_USED_INDICATOR
from conversation import ConversationManager
from ollama_client import OllamaClient
from mcp_manager import MCPManager
from prompts import get_pr_review_prompt
from task_manager import task_manager, TaskStatus

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat requests with MCP tool integration."""

    def __init__(self, mcp_manager: MCPManager, ollama_manager=None):
        self.mcp_manager = mcp_manager
        self.ollama_manager = ollama_manager
        self.conversation_manager = ConversationManager()
        self.ollama_client = OllamaClient()
        self.ollama_tools = []

    def initialize(self) -> None:
        """Initialize service with MCP tools."""
        mcp_tools = self.mcp_manager.get_tools()

        # Log all available tools from MCP
        logger.info(f"=== ALL MCP TOOLS ({len(mcp_tools)}) ===")
        for tool in mcp_tools:
            logger.info(f"  - {tool['name']}: {tool.get('description', '')[:80]}...")

        # Filter to essential tools only to reduce token usage
        filtered_tools = [t for t in mcp_tools if t["name"] in ESSENTIAL_TOOLS]
        logger.info(f"Filtered tools: {len(filtered_tools)}/{len(mcp_tools)} (saved ~{(len(mcp_tools) - len(filtered_tools)) * 60} tokens)")

        self.ollama_tools = self.ollama_client.convert_mcp_tools_to_ollama(filtered_tools)
        logger.info(f"Chat service initialized with {len(self.ollama_tools)} tools")

        # Update model name if OllamaManager is available
        if self.ollama_manager:
            model_name = self.ollama_manager.get_model_name()
            self.ollama_client.set_model(model_name)
            logger.info(f"Using Ollama model: {model_name}")

    async def process_message(self, user_id: str, message: str) -> Tuple[str, int, bool]:
        """
        Process user message and return response.

        Args:
            user_id: Unique user identifier
            message: User message text

        Returns:
            Tuple of (response_text, tool_calls_count, mcp_was_used)
        """
        logger.info(f"User {user_id}: Processing message: {message[:100]}...")

        # Check and clear history if full
        if self.conversation_manager.check_and_clear_if_full(user_id):
            logger.info(f"User {user_id}: History cleared (reached limit)")

        # Add user message to history
        self.conversation_manager.add_message(user_id, "user", message)

        # Process with Ollama
        response_text, tool_calls_count, mcp_was_used = await self._process_with_ollama(user_id)

        if response_text:
            # Clean response for storage (remove indicator)
            clean_response = response_text.replace(MCP_USED_INDICATOR, "").strip()
            self.conversation_manager.add_message(user_id, "assistant", clean_response)

        return response_text or "Sorry, something went wrong.", tool_calls_count, mcp_was_used

    async def _process_with_ollama(self, user_id: str) -> Tuple[Optional[str], int, bool]:
        """Process message with Ollama and MCP tools."""
        # Update model name from OllamaManager (in case it changed after background pull)
        if self.ollama_manager:
            model_name = self.ollama_manager.get_model_name()
            if self.ollama_client.model != model_name:
                self.ollama_client.set_model(model_name)

        conversation_history = self.conversation_manager.get_history(user_id)
        current_date = datetime.now().strftime("%Y-%m-%d")

        system_prompt = {
            "role": "system",
            "content": f"""Current date: {current_date}.

You are a project consultant for EasyPomodoro Android app (repo: LebedAlIv2601/EasyPomodoro).

**CRITICAL RULES:**
- NEVER say "let me look at..." or "I will check..." - just CALL the tool immediately
- If you need information, CALL a tool. Do NOT describe your intention.
- Do NOT respond until you have ALL the information needed to give a COMPLETE answer
- You can call multiple tools in sequence - keep calling until you have everything

**TOOLS:**
1. **get_project_structure** - Get directory tree. USE FIRST to find file paths!
2. **get_file_contents** - Read file content (owner="LebedAlIv2601", repo="EasyPomodoro", path="...")
3. **rag_query** - Search project documentation semantically
4. **list_commits**, **list_issues**, **list_pull_requests** - GitHub items

**WORKFLOW:**
1. For code questions: get_project_structure -> get_file_contents (repeat as needed)
2. For architecture/design: rag_query
3. ONLY respond with final answer AFTER gathering ALL necessary information

Respond in user's language."""
        }

        # messages_with_system = [system_prompt] + conversation_history
        messages_with_system = conversation_history
        mcp_was_used = False
        total_tool_calls = 0

        tool_choice = "auto" if self.ollama_tools else None

        try:
            max_iterations = 10
            iteration = 0
            current_messages = messages_with_system
            response_text = None

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"User {user_id}: Tool call iteration {iteration}/{max_iterations}")

                # On last iteration, disable tools to force final response
                is_last_iteration = (iteration == max_iterations)
                # current_tools = None if is_last_iteration else self.ollama_tools
                current_tools = None
                # current_tool_choice = None if is_last_iteration else tool_choice
                current_tool_choice = None

                response_text, tool_calls = await self.ollama_client.chat_completion(
                    messages=current_messages,
                    tools=current_tools if current_tools else None,
                    tool_choice=current_tool_choice
                )

                if not tool_calls:
                    # No tool calls - this should be the final response
                    logger.info(f"User {user_id}: No tool calls in iteration {iteration}")

                    # If model returned empty response, force it to generate one
                    if not response_text:
                        logger.info(f"User {user_id}: Empty response, forcing final answer")
                        # Add instruction to generate final answer
                        current_messages.append({
                            "role": "user",
                            "content": "Based on all the information gathered above, provide a complete answer now."
                        })
                        response_text, _ = await self.ollama_client.chat_completion(
                            messages=current_messages,
                            tools=None,
                            tool_choice=None
                        )
                    break

                logger.info(f"User {user_id}: Processing {len(tool_calls)} tool calls")
                mcp_was_used = True
                total_tool_calls += len(tool_calls)

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

            return response_text, total_tool_calls, mcp_was_used

        except Exception as e:
            logger.error(f"User {user_id}: Ollama processing error: {e}", exc_info=True)
            return None, 0, False

    def get_tools_count(self) -> int:
        """Get number of available tools."""
        return len(self.ollama_tools)

    async def review_pr(self, pr_number: int) -> Tuple[str, int]:
        """
        Perform code review for a pull request.

        Args:
            pr_number: Pull request number to review

        Returns:
            Tuple of (review_text, tool_calls_count)
        """
        logger.info(f"Starting PR review for #{pr_number}")

        # Update model name from OllamaManager (in case it changed after background pull)
        if self.ollama_manager:
            model_name = self.ollama_manager.get_model_name()
            if self.ollama_client.model != model_name:
                self.ollama_client.set_model(model_name)

        current_date = datetime.now().strftime("%Y-%m-%d")

        system_prompt = {
            "role": "system",
            "content": get_pr_review_prompt(pr_number, current_date)
        }

        user_prompt = {
            "role": "user",
            "content": f"Review PR #{pr_number} now. Start by calling pull_request_read tool."
        }

        messages = [system_prompt, user_prompt]
        total_tool_calls = 0

        try:
            max_iterations = 15
            iteration = 0
            response_text = None

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"PR Review #{pr_number}: iteration {iteration}/{max_iterations}")

                is_last_iteration = (iteration == max_iterations)
                current_tools = None if is_last_iteration else self.ollama_tools
                # Use "required" on first iteration to force tool call, then "auto"
                if iteration == 1:
                    current_tool_choice = "required"
                elif is_last_iteration:
                    current_tool_choice = None
                else:
                    current_tool_choice = "auto"

                response_text, tool_calls = await self.ollama_client.chat_completion(
                    messages=messages,
                    tools=current_tools,
                    tool_choice=current_tool_choice
                )

                if not tool_calls:
                    logger.info(f"PR Review #{pr_number}: No tool calls, finalizing")

                    if not response_text:
                        logger.info(f"PR Review #{pr_number}: Empty response, forcing final answer")
                        messages.append({
                            "role": "user",
                            "content": "Based on all the information gathered, provide the complete code review now."
                        })
                        response_text, _ = await self.ollama_client.chat_completion(
                            messages=messages,
                            tools=None,
                            tool_choice=None
                        )
                    break

                logger.info(f"PR Review #{pr_number}: Processing {len(tool_calls)} tool calls")
                total_tool_calls += len(tool_calls)

                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["arguments"]

                    logger.info(f"PR Review #{pr_number}: Executing tool {tool_name}")

                    try:
                        result = await self.mcp_manager.call_tool(tool_name, tool_args)
                        result_content = result["result"]

                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result_content
                        })
                    except Exception as e:
                        logger.error(f"PR Review #{pr_number}: Tool error: {e}", exc_info=True)
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps({"error": str(e)})
                        })

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
                messages.append(assistant_msg)

                for tr in tool_results:
                    messages.append(tr)

            logger.info(f"PR Review #{pr_number}: Completed with {total_tool_calls} tool calls")
            return response_text or "Failed to generate review.", total_tool_calls

        except Exception as e:
            logger.error(f"PR Review #{pr_number}: Error: {e}", exc_info=True)
            return f"Error during review: {str(e)}", total_tool_calls

    async def process_message_async(self, task_id: str, user_id: str, message: str) -> None:
        """
        Process user message asynchronously and update task status.

        Args:
            task_id: Task ID to update
            user_id: Unique user identifier
            message: User message text
        """
        logger.info(f"Task {task_id}: Starting async processing for user {user_id}")

        try:
            task_manager.update_status(task_id, TaskStatus.PROCESSING)

            response_text, tool_calls_count, mcp_was_used = await self.process_message(user_id, message)

            result = {
                "response": response_text,
                "tool_calls_count": tool_calls_count,
                "mcp_used": mcp_was_used
            }

            task_manager.set_result(task_id, result)
            task_manager.update_status(task_id, TaskStatus.COMPLETED)

            logger.info(f"Task {task_id}: Completed successfully")

        except Exception as e:
            logger.error(f"Task {task_id}: Failed with error: {e}", exc_info=True)
            task_manager.set_error(task_id, str(e))
            task_manager.update_status(task_id, TaskStatus.FAILED)
