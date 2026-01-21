"""Ollama API client integration."""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple

import httpx

from config import OLLAMA_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama API with tool support."""

    def __init__(self, model_name: Optional[str] = None):
        self.ollama_url = OLLAMA_URL
        self.model = model_name or OLLAMA_MODEL

    def set_model(self, model_name: str) -> None:
        """Update model name (useful when model name changes after pull)."""
        self.model = model_name
        logger.info(f"Updated Ollama model name to: {model_name}")

    def convert_mcp_tools_to_ollama(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert MCP tool format to Ollama tool format.

        Ollama uses the same format as OpenRouter (OpenAI compatible).

        Args:
            mcp_tools: List of MCP tools

        Returns:
            List of Ollama-formatted tools
        """
        ollama_tools = []
        for tool in mcp_tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"]
                }
            })
        return ollama_tools

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Send chat completion request to Ollama.

        Args:
            messages: Conversation history
            tools: Available tools in Ollama format
            tool_choice: Tool selection strategy ("auto", "required", "none")

        Returns:
            Tuple of (response_text, tool_calls)
        """
        url = f"{self.ollama_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        # if tools:
        #     payload["tools"] = tools

        logger.info(f"Ollama request: model={self.model}, messages={len(messages)}, tools={len(tools) if tools else 0}")
        logger.debug(f"Ollama payload: {json.dumps(payload, indent=2)}")

        message_roles = [msg.get("role") for msg in messages]
        logger.info(f"Message roles: {message_roles}")

        try:
            async with httpx.AsyncClient(timeout=900.0) as client:  # 15 minutes for slow models
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            logger.debug(f"Ollama response: {json.dumps(data, indent=2)}")

            if "message" not in data:
                logger.error("Invalid Ollama response: no message field")
                return None, None

            message = data["message"]
            response_text = message.get("content")
            tool_calls = message.get("tool_calls")

            logger.info(f"Ollama response: has_content={response_text is not None and len(response_text) > 0 if response_text else False}, has_tool_calls={tool_calls is not None}")

            if tool_calls:
                logger.info(f"Ollama returned {len(tool_calls)} tool calls")
                parsed_tool_calls = []
                for tc in tool_calls:
                    if tc.get("type") == "function":
                        func = tc.get("function", {})
                        # Ollama returns arguments as dict, not string
                        arguments = func.get("arguments", {})
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)

                        parsed_tool_calls.append({
                            "id": tc.get("id", f"call_{len(parsed_tool_calls)}"),
                            "name": func.get("name"),
                            "arguments": arguments
                        })
                return response_text, parsed_tool_calls
            else:
                return response_text, None

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Ollama HTTP error: {e}")
            logger.error(f"Response body: {error_body}")
            raise

        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to Ollama at {self.ollama_url}")
            logger.error(f"Make sure Ollama is running with: ollama serve")
            raise Exception(f"Cannot connect to Ollama: {e}")

        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Ollama error: {e}", exc_info=True)
            raise
