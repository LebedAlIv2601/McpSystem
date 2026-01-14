"""Chat service for processing messages with OpenRouter and MCP tools."""

import json
import logging
import re
from datetime import datetime
from typing import Optional, Tuple

from config import ESSENTIAL_TOOLS, MCP_USED_INDICATOR, MAX_TOOL_ITERATIONS
from conversation import ConversationManager
from openrouter_client import OpenRouterClient
from mcp_manager import MCPManager
from prompts import get_pr_review_prompt

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat requests with MCP tool integration."""

    def __init__(self, mcp_manager: MCPManager):
        self.mcp_manager = mcp_manager
        self.conversation_manager = ConversationManager()
        self.openrouter_client = OpenRouterClient()
        self.openrouter_tools = []

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

        self.openrouter_tools = self.openrouter_client.convert_mcp_tools_to_openrouter(filtered_tools)
        logger.info(f"Chat service initialized with {len(self.openrouter_tools)} tools")

    async def process_message(self, user_id: str, user_name: str, message: str) -> Tuple[str, int, bool]:
        """
        Process user message and return response.

        Args:
            user_id: Unique user identifier
            user_name: User display name
            message: User message text

        Returns:
            Tuple of (response_text, tool_calls_count, mcp_was_used)
        """
        logger.info(f"User {user_id} ({user_name}): Processing message: {message[:100]}...")

        # Check and clear history if full
        if self.conversation_manager.check_and_clear_if_full(user_id):
            logger.info(f"User {user_id}: History cleared (reached limit)")

        # Add user message to history
        self.conversation_manager.add_message(user_id, "user", message)

        # Process with OpenRouter
        response_text, tool_calls_count, mcp_was_used = await self._process_with_openrouter(user_id, user_name)

        if response_text:
            # Clean response for storage (remove indicator)
            clean_response = response_text.replace(MCP_USED_INDICATOR, "").strip()
            self.conversation_manager.add_message(user_id, "assistant", clean_response)

        return response_text or "Sorry, something went wrong.", tool_calls_count, mcp_was_used

    async def _process_with_openrouter(self, user_id: str, user_name: str) -> Tuple[Optional[str], int, bool]:
        """Process message with OpenRouter and MCP tools."""
        conversation_history = self.conversation_manager.get_history(user_id)
        current_date = datetime.now().strftime("%Y-%m-%d")

        system_prompt = {
            "role": "system",
            "content": f"""Current date: {current_date}.

You are a support agent for EasyPomodoro Android app. Your role is to help users with their questions and issues.

**USER INFO:**
- User ID: {user_id}
- User Name: {user_name}

**CRITICAL RULES:**
- NEVER say "let me look at..." or "I will check..." - just CALL the tool immediately
- If you need information, CALL a tool. Do NOT describe your intention.
- ALWAYS check user's tickets first using get_user_tickets before responding

**TICKET MANAGEMENT RULES:**
1. On FIRST message: Call get_user_tickets to check user's ticket history
2. If NO open/in_progress tickets exist AND user reports an issue:
   - Call create_ticket with user's issue description
3. After YOUR FIRST response to user:
   - If user says issue is resolved (any phrasing like "thanks", "solved", "works now", etc.):
     - Call update_ticket_status with status="closed"
   - If user continues with more questions/issues on same topic:
     - Call update_ticket_status with status="in_progress"
     - Call update_ticket_description to add new conversation details
4. NEW ticket is created ONLY if previous ticket has status="closed"

**TOOLS:**
1. **get_user_tickets** - Get user's ticket history. USE FIRST on every conversation!
2. **create_ticket** - Create new ticket (only if no open tickets exist)
3. **update_ticket_status** - Update status: "open" -> "in_progress" -> "closed"
4. **update_ticket_description** - Update ticket with conversation progress
5. **rag_query** - Search FAQ and documentation. USE THIS to find answers!
6. **list_specs**, **get_spec_content** - Get documentation files

**WORKFLOW:**
1. FIRST: get_user_tickets to check existing tickets
2. SECOND: rag_query to search FAQ/documentation for answers
3. Create/update tickets as needed based on conversation
4. Provide helpful response to user

**IMPORTANT:**
- Always search FAQ using rag_query before answering questions
- Be helpful and friendly
- Respond in user's language (Russian if user writes in Russian)"""
        }

        messages_with_system = [system_prompt] + conversation_history
        mcp_was_used = False
        total_tool_calls = 0

        tool_choice = "auto" if self.openrouter_tools else None

        try:
            max_iterations = MAX_TOOL_ITERATIONS
            iteration = 0
            current_messages = messages_with_system
            response_text = None

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

                # Clean response from tool call artifacts immediately
                if response_text:
                    response_text = self._clean_tool_call_artifacts(response_text)

                if not tool_calls:
                    # No tool calls - this should be the final response
                    logger.info(f"User {user_id}: No tool calls in iteration {iteration}")

                    # If model returned empty response (or only artifacts), force it to generate one
                    if not response_text:
                        logger.info(f"User {user_id}: Empty response, forcing final answer")
                        # Add instruction to generate final answer
                        current_messages.append({
                            "role": "user",
                            "content": "Based on all the information gathered above, provide a complete answer now. Do NOT output any XML or function calls."
                        })
                        response_text, _ = await self.openrouter_client.chat_completion(
                            messages=current_messages,
                            tools=None,
                            tool_choice=None
                        )
                        # Clean forced response as well
                        if response_text:
                            response_text = self._clean_tool_call_artifacts(response_text)
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
            logger.error(f"User {user_id}: OpenRouter processing error: {e}", exc_info=True)
            return None, 0, False

    def get_tools_count(self) -> int:
        """Get number of available tools."""
        return len(self.openrouter_tools)

    def _clean_tool_call_artifacts(self, text: str) -> str:
        """Remove tool call artifacts from response text.

        Some models (like DeepSeek) output tool calls as XML in the content field.
        This method removes those artifacts to provide clean responses.
        """
        if not text:
            return text

        # Remove <function_calls>...</function_calls> blocks (standard format)
        text = re.sub(r'<function_calls>.*?</function_calls>', '', text, flags=re.DOTALL)

        # Remove <｜DSML｜function_calls>...</｜DSML｜function_calls> blocks (DeepSeek format)
        text = re.sub(r'<｜DSML｜function_calls>.*?</｜DSML｜function_calls>', '', text, flags=re.DOTALL)

        # Remove any remaining <invoke>...</invoke> or similar patterns
        text = re.sub(r'<invoke\s+name="[^"]*">.*?</invoke>', '', text, flags=re.DOTALL)
        text = re.sub(r'<｜DSML｜invoke\s+name="[^"]*">.*?</｜DSML｜invoke>', '', text, flags=re.DOTALL)

        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text

    async def review_pr(self, pr_number: int) -> Tuple[str, int]:
        """
        Perform code review for a pull request.

        Args:
            pr_number: Pull request number to review

        Returns:
            Tuple of (review_text, tool_calls_count)
        """
        logger.info(f"Starting PR review for #{pr_number}")
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
                current_tools = None if is_last_iteration else self.openrouter_tools
                # Use "required" on first iteration to force tool call, then "auto"
                if iteration == 1:
                    current_tool_choice = "required"
                elif is_last_iteration:
                    current_tool_choice = None
                else:
                    current_tool_choice = "auto"

                response_text, tool_calls = await self.openrouter_client.chat_completion(
                    messages=messages,
                    tools=current_tools,
                    tool_choice=current_tool_choice
                )

                # Clean response from tool call artifacts immediately
                if response_text:
                    response_text = self._clean_tool_call_artifacts(response_text)

                if not tool_calls:
                    logger.info(f"PR Review #{pr_number}: No tool calls, finalizing")

                    if not response_text:
                        logger.info(f"PR Review #{pr_number}: Empty response, forcing final answer")
                        messages.append({
                            "role": "user",
                            "content": "Based on all the information gathered, provide the complete code review now. Do NOT output any XML or function calls."
                        })
                        response_text, _ = await self.openrouter_client.chat_completion(
                            messages=messages,
                            tools=None,
                            tool_choice=None
                        )
                        # Clean forced response as well
                        if response_text:
                            response_text = self._clean_tool_call_artifacts(response_text)
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
