"""MCP client manager for subprocess and HTTP connection handling."""

import asyncio
import logging
from typing import List, Dict, Any
from contextlib import AsyncExitStack, asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import MCP_SERVERS, TOOL_CALL_TIMEOUT
from mcp_http_transport import MCPHttpClient

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages multiple MCP server connections (stdio and HTTP)."""

    def __init__(self):
        self.stdio_sessions: Dict[str, ClientSession] = {}
        self.http_clients: Dict[str, MCPHttpClient] = {}
        self.tools: List[Dict[str, Any]] = []
        self.tool_server_map: Dict[str, str] = {}
        self.tool_transport_map: Dict[str, str] = {}
        self._exit_stack: AsyncExitStack = None
        self._connected = False

    @asynccontextmanager
    async def connect(self):
        """Connect to all configured MCP servers."""
        logger.info(f"Starting {len(MCP_SERVERS)} MCP servers")

        async with AsyncExitStack() as stack:
            self._exit_stack = stack

            for server_config in MCP_SERVERS:
                server_name = server_config["name"]
                transport = server_config.get("transport", "stdio")

                try:
                    if transport == "http":
                        await self._connect_http_server(server_config)
                    else:
                        await self._connect_stdio_server(stack, server_config)
                except Exception as e:
                    logger.error(f"Failed to connect to {server_name}: {e}", exc_info=True)
                    # Continue with other servers

            await self._fetch_tools()
            self._connected = True

            try:
                yield self
            finally:
                logger.info("Closing all MCP sessions")
                await self._cleanup()

    async def _connect_http_server(self, config: Dict) -> None:
        """Connect to HTTP MCP server."""
        server_name = config["name"]
        url = config["url"]
        auth_token = config.get("auth_token", "")

        logger.info(f"Connecting to HTTP MCP server: {server_name}")
        logger.info(f"  URL: {url}")

        client = MCPHttpClient(url=url, auth_token=auth_token)
        await client.connect()
        await client.initialize()

        self.http_clients[server_name] = client
        logger.info(f"{server_name} HTTP MCP client connected")

    async def _connect_stdio_server(self, stack: AsyncExitStack, config: Dict) -> None:
        """Connect to stdio MCP server."""
        server_name = config["name"]
        params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config.get("env")
        )

        logger.info(f"Starting stdio MCP server: {server_name}")
        logger.info(f"  Command: {config['command']} {' '.join(config['args'][:2])}...")

        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))

        await session.initialize()

        self.stdio_sessions[server_name] = session
        logger.info(f"{server_name} stdio MCP client connected")

    async def _fetch_tools(self) -> None:
        """Fetch available tools from all MCP servers."""
        all_tools = []

        # Fetch from HTTP clients
        for server_name, client in self.http_clients.items():
            try:
                server_tools = await client.list_tools()
                logger.info(f"Fetched {len(server_tools)} tools from {server_name}")

                if server_tools:
                    tool_names = [t['name'] for t in server_tools[:5]]
                    if len(server_tools) > 5:
                        tool_names.append(f"... and {len(server_tools) - 5} more")
                    logger.info(f"  Tools: {tool_names}")

                all_tools.extend(server_tools)
                for tool in server_tools:
                    self.tool_server_map[tool["name"]] = server_name
                    self.tool_transport_map[tool["name"]] = "http"

            except Exception as e:
                logger.error(f"Failed to fetch tools from {server_name}: {e}", exc_info=True)

        # Fetch from stdio sessions
        for server_name, session in self.stdio_sessions.items():
            try:
                result = await session.list_tools()
                server_tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    }
                    for tool in result.tools
                ]
                logger.info(f"Fetched {len(server_tools)} tools from {server_name}")

                if server_tools:
                    tool_names = [t['name'] for t in server_tools[:5]]
                    if len(server_tools) > 5:
                        tool_names.append(f"... and {len(server_tools) - 5} more")
                    logger.info(f"  Tools: {tool_names}")

                all_tools.extend(server_tools)
                for tool in server_tools:
                    self.tool_server_map[tool["name"]] = server_name
                    self.tool_transport_map[tool["name"]] = "stdio"

            except Exception as e:
                logger.error(f"Failed to fetch tools from {server_name}: {e}", exc_info=True)

        self.tools = all_tools
        logger.info(f"Total tools available: {len(self.tools)}")

    async def _cleanup(self) -> None:
        """Clean up connections."""
        for client in self.http_clients.values():
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")

        self.http_clients.clear()
        self.stdio_sessions.clear()
        self._exit_stack = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if MCP manager is connected."""
        return self._connected

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return self.tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute MCP tool call, routing to the correct server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        server_name = self.tool_server_map.get(tool_name)
        transport = self.tool_transport_map.get(tool_name)

        if not server_name:
            raise RuntimeError(f"Unknown tool: {tool_name}")

        logger.info(f"=== MCP TOOL CALL ===")
        logger.info(f"Server: {server_name} ({transport})")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Arguments: {arguments}")

        try:
            if transport == "http":
                result = await self._call_http_tool(server_name, tool_name, arguments)
            else:
                result = await self._call_stdio_tool(server_name, tool_name, arguments)

            logger.info(f"=== MCP TOOL RESPONSE ===")
            result_str = str(result.get("result", result) if isinstance(result, dict) else result)
            logger.info(f"Response length: {len(result_str)} chars")
            # Log short responses (potential errors or empty results)
            if len(result_str) < 200:
                logger.info(f"Response content: {result_str}")
            return result

        except Exception as e:
            logger.error(f"=== MCP TOOL ERROR ===")
            logger.error(f"Error: {e}", exc_info=True)
            raise

    async def _call_http_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Dict[str, Any]:
        """Call tool on HTTP MCP server."""
        client = self.http_clients.get(server_name)
        if not client:
            raise RuntimeError(f"HTTP server {server_name} not available")

        return await asyncio.wait_for(
            client.call_tool(tool_name, arguments),
            timeout=TOOL_CALL_TIMEOUT
        )

    async def _call_stdio_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Dict[str, Any]:
        """Call tool on stdio MCP server."""
        session = self.stdio_sessions.get(server_name)
        if not session:
            raise RuntimeError(f"Stdio server {server_name} not available")

        result = await asyncio.wait_for(
            session.call_tool(tool_name, arguments),
            timeout=TOOL_CALL_TIMEOUT
        )

        if result.content:
            content_text = ""
            for item in result.content:
                if hasattr(item, 'text'):
                    content_text += item.text
            return {"result": content_text}
        else:
            return {"result": "No result"}
