"""OpenRouter API client integration."""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple

import httpx

from config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_API_URL

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for OpenRouter API with tool support."""

    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self.api_url = OPENROUTER_API_URL

    def convert_mcp_tools_to_openrouter(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert MCP tool format to OpenRouter tool format.

        Args:
            mcp_tools: List of MCP tools

        Returns:
            List of OpenRouter-formatted tools
        """
        openrouter_tools = []
        for tool in mcp_tools:
            openrouter_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"]
                }
            })
        return openrouter_tools

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Send chat completion request to OpenRouter.

        Args:
            messages: Conversation history
            tools: Available tools in OpenRouter format
            tool_choice: Tool selection strategy ("auto", "required", "none")

        Returns:
            Tuple of (response_text, tool_calls)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages
        }

        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
                logger.info(f"Using tool_choice: {tool_choice}")

        logger.info(f"OpenRouter request: model={self.model}, messages={len(messages)}, tools={len(tools) if tools else 0}")
        logger.debug(f"OpenRouter payload: {json.dumps(payload, indent=2)}")

        message_roles = [msg.get("role") for msg in messages]
        logger.info(f"Message roles: {message_roles}")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            logger.debug(f"OpenRouter response: {json.dumps(data, indent=2)}")

            if "choices" not in data or not data["choices"]:
                logger.error("Invalid OpenRouter response: no choices")
                return None, None

            choice = data["choices"][0]
            message = choice.get("message", {})

            response_text = message.get("content")
            tool_calls = message.get("tool_calls")

            if tool_calls:
                logger.info(f"OpenRouter returned {len(tool_calls)} tool calls")
                parsed_tool_calls = []
                for tc in tool_calls:
                    if tc.get("type") == "function":
                        func = tc.get("function", {})
                        parsed_tool_calls.append({
                            "id": tc.get("id"),
                            "name": func.get("name"),
                            "arguments": json.loads(func.get("arguments", "{}"))
                        })
                return response_text, parsed_tool_calls
            else:
                return response_text, None

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            error_headers = e.response.headers

            logger.error(f"OpenRouter HTTP error: {e}")
            logger.error(f"Response body: {error_body}")

            if e.response.status_code == 429:
                logger.error("=== RATE LIMIT HIT ===")
                retry_after = error_headers.get("retry-after")
                rate_limit_limit = error_headers.get("x-ratelimit-limit")
                rate_limit_remaining = error_headers.get("x-ratelimit-remaining")
                rate_limit_reset = error_headers.get("x-ratelimit-reset")

                if retry_after:
                    logger.error(f"Retry after: {retry_after} seconds")
                if rate_limit_limit:
                    logger.error(f"Rate limit: {rate_limit_limit} requests")
                if rate_limit_remaining:
                    logger.error(f"Remaining requests: {rate_limit_remaining}")
                if rate_limit_reset:
                    logger.error(f"Rate limit resets at: {rate_limit_reset}")

                logger.error(f"All headers: {dict(error_headers)}")

            raise

        except httpx.HTTPError as e:
            logger.error(f"OpenRouter HTTP error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"OpenRouter error: {e}", exc_info=True)
            raise
