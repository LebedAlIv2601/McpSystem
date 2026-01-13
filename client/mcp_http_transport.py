"""HTTP Streamable transport for MCP protocol (spec version 2025-03-26)."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class MCPHttpClient:
    """MCP client using Streamable HTTP transport for GitHub Copilot MCP."""

    def __init__(self, url: str, auth_token: str):
        """
        Initialize HTTP MCP client.

        Args:
            url: MCP server endpoint URL
            auth_token: Bearer token for authentication
        """
        self.url = url.rstrip('/')
        self.auth_token = auth_token
        self.tools: List[Dict[str, Any]] = []
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False
        self._session_id: Optional[str] = None
        self._request_id = 0

    def _next_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for MCP requests."""
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    async def connect(self) -> None:
        """Establish HTTP client connection."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0),
            follow_redirects=True
        )
        logger.info(f"HTTP MCP client created for {self.url}")

    async def close(self) -> None:
        """Close HTTP client connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False
            self._session_id = None
        logger.info("HTTP MCP client closed")

    async def _send_request(self, method: str, params: Optional[Dict] = None, is_notification: bool = False) -> Optional[Dict]:
        """
        Send JSON-RPC request to MCP server.

        Args:
            method: JSON-RPC method name
            params: Method parameters
            is_notification: If True, don't expect a response

        Returns:
            Response result or None for notifications
        """
        if not self._client:
            raise RuntimeError("HTTP client not connected")

        request = {
            "jsonrpc": "2.0",
            "method": method,
        }

        if params:
            request["params"] = params

        if not is_notification:
            request["id"] = self._next_id()

        headers = self._get_headers()

        logger.debug(f"MCP HTTP Request: {json.dumps(request)}")
        logger.debug(f"Headers: {headers}")

        try:
            response = await self._client.post(
                self.url,
                headers=headers,
                json=request
            )

            # Log response details
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            # Check for session ID in response
            if "mcp-session-id" in response.headers:
                self._session_id = response.headers["mcp-session-id"]
                logger.info(f"Received session ID: {self._session_id}")

            # Handle different response codes
            if response.status_code == 202:
                # Notification accepted, no body
                return None

            if response.status_code >= 400:
                error_text = response.text
                logger.error(f"HTTP error {response.status_code}: {error_text}")
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {error_text}",
                    request=response.request,
                    response=response
                )

            # Check content type
            content_type = response.headers.get("content-type", "")

            if "text/event-stream" in content_type:
                # Parse SSE response
                return await self._parse_sse_response(response.text)
            else:
                # Parse JSON response
                result = response.json()
                logger.debug(f"MCP HTTP Response: {json.dumps(result)}")

                if "error" in result:
                    logger.error(f"MCP error: {result['error']}")
                    raise RuntimeError(f"MCP error: {result['error']}")

                return result.get("result")

        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.error(f"HTTP request error: {e}", exc_info=True)
            raise

    async def _parse_sse_response(self, sse_text: str) -> Optional[Dict]:
        """Parse SSE response and extract JSON-RPC result."""
        result = None

        for line in sse_text.split('\n'):
            line = line.strip()
            if line.startswith('data:'):
                data = line[5:].strip()
                if data:
                    try:
                        parsed = json.loads(data)
                        if isinstance(parsed, dict) and "result" in parsed:
                            result = parsed["result"]
                        elif isinstance(parsed, list):
                            # Batched response
                            for item in parsed:
                                if isinstance(item, dict) and "result" in item:
                                    result = item["result"]
                                    break
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse SSE data: {data}")

        return result

    async def initialize(self) -> None:
        """Initialize MCP session."""
        if not self._client:
            raise RuntimeError("HTTP client not connected")

        logger.info("Initializing MCP HTTP session...")

        # Send initialize request
        init_result = await self._send_request(
            method="initialize",
            params={
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "telegram-bot-mcp-client",
                    "version": "1.0.0"
                }
            }
        )

        logger.info(f"Initialize result: {init_result}")

        # Send initialized notification
        await self._send_request(
            method="notifications/initialized",
            is_notification=True
        )

        self._initialized = True
        logger.info("MCP HTTP session initialized")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Fetch available tools from MCP server."""
        if not self._initialized:
            raise RuntimeError("MCP session not initialized")

        logger.info("Fetching tools from MCP server...")

        result = await self._send_request(
            method="tools/list",
            params={}
        )

        if result and "tools" in result:
            self.tools = [
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "inputSchema": tool.get("inputSchema", {})
                }
                for tool in result["tools"]
            ]
            logger.info(f"Fetched {len(self.tools)} tools from HTTP MCP server")
            return self.tools
        else:
            logger.warning(f"Unexpected tools/list response: {result}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tool call on MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        if not self._initialized:
            raise RuntimeError("MCP session not initialized")

        logger.info(f"=== HTTP MCP TOOL CALL ===")
        logger.info(f"URL: {self.url}")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Arguments: {arguments}")

        result = await self._send_request(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments
            }
        )

        logger.info(f"=== HTTP MCP TOOL RESPONSE ===")
        logger.info(f"Raw result type: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        logger.info(f"Raw result: {json.dumps(result, indent=2) if isinstance(result, dict) else result}"[:500])

        if result:
            # Handle content array format
            if isinstance(result, dict) and "content" in result:
                content_items = result["content"]
                text_parts = []
                for item in content_items:
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        if item_type == "text":
                            text_parts.append(item.get("text", ""))
                        elif item_type == "resource":
                            # Extract actual file content from resource
                            resource = item.get("resource", {})
                            if "text" in resource:
                                text_parts.append(resource["text"])
                return {"result": "\n".join(text_parts) if text_parts else json.dumps(result)}

            return {"result": json.dumps(result) if isinstance(result, dict) else str(result)}
        else:
            return {"result": "No result"}

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get cached list of available tools."""
        return self.tools
