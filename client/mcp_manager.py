"""MCP client manager for subprocess and connection handling."""

import asyncio
import logging
from typing import List, Dict, Any
from contextlib import AsyncExitStack, asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import MCP_SERVERS, TOOL_CALL_TIMEOUT

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages multiple MCP server subprocesses and client connections."""

    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: List[Dict[str, Any]] = []
        self.tool_server_map: Dict[str, str] = {}  # Maps tool name to server name
        self._exit_stack: AsyncExitStack = None

    @asynccontextmanager
    async def connect(self):
        """Connect to all configured MCP servers and initialize client sessions."""
        logger.info(f"Starting {len(MCP_SERVERS)} MCP servers")

        async with AsyncExitStack() as stack:
            self._exit_stack = stack

            # Connect to all servers
            for server_config in MCP_SERVERS:
                server_name = server_config["name"]
                params = StdioServerParameters(
                    command=server_config["command"],
                    args=server_config["args"],
                    env=server_config.get("env")
                )

                logger.info(f"Starting {server_name} server: {server_config['command']} {' '.join(server_config['args'])}")

                try:
                    # Enter stdio_client context
                    read, write = await stack.enter_async_context(stdio_client(params))

                    # Enter ClientSession context
                    session = await stack.enter_async_context(ClientSession(read, write))

                    self.sessions[server_name] = session
                    logger.info(f"{server_name} MCP client connected")

                except Exception as e:
                    logger.error(f"Failed to connect to {server_name} server: {e}", exc_info=True)
                    # Continue with other servers even if one fails

            # Initialize all connected sessions
            await self._initialize_sessions()

            try:
                yield self
            finally:
                logger.info("Closing all MCP sessions")
                self.sessions.clear()
                self._exit_stack = None

    async def _initialize_sessions(self):
        """Initialize all connected sessions and fetch tools."""
        logger.info("Initializing all MCP sessions")

        for server_name, session in self.sessions.items():
            try:
                await session.initialize()
                logger.info(f"{server_name} MCP session initialized")
            except Exception as e:
                logger.error(f"Failed to initialize {server_name} session: {e}", exc_info=True)

        await self._fetch_tools()

    async def _fetch_tools(self) -> None:
        """Fetch available tools from all MCP servers."""
        if not self.sessions:
            raise RuntimeError("No MCP sessions initialized")

        logger.info(f"Fetching tools from {len(self.sessions)} MCP servers")

        all_tools = []

        for server_name, session in self.sessions.items():
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
                logger.info(f"Fetched {len(server_tools)} tools from {server_name} server: {[t['name'] for t in server_tools]}")

                # Add to merged tool list
                all_tools.extend(server_tools)

                # Build tool-to-server mapping for routing
                for tool in server_tools:
                    self.tool_server_map[tool["name"]] = server_name

            except Exception as e:
                logger.error(f"Failed to fetch tools from {server_name} server: {e}", exc_info=True)
                # Continue with other servers even if one fails

        self.tools = all_tools
        logger.info(f"Total tools available: {len(self.tools)}")
        logger.info(f"Tool routing map: {self.tool_server_map}")

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
        if not self.sessions:
            raise RuntimeError("MCP sessions not initialized")

        # Determine which server to route to
        server_name = self.tool_server_map.get(tool_name)
        if not server_name:
            raise RuntimeError(f"Unknown tool: {tool_name}")

        session = self.sessions.get(server_name)
        if not session:
            raise RuntimeError(f"Server {server_name} not available")

        logger.info(f"=== MCP SERVER CALL ===")
        logger.info(f"Server: {server_name}")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Arguments: {arguments}")

        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=TOOL_CALL_TIMEOUT
            )

            if result.content:
                content_text = ""
                for item in result.content:
                    if hasattr(item, 'text'):
                        content_text += item.text

                logger.info(f"=== MCP SERVER RESPONSE ===")
                logger.info(f"Server: {server_name}")
                logger.info(f"Response: {content_text}")

                return {"result": content_text}
            else:
                logger.info(f"=== MCP SERVER RESPONSE ===")
                logger.info(f"Server: {server_name}")
                logger.info(f"Response: No result")
                return {"result": "No result"}

        except asyncio.TimeoutError:
            logger.error(f"=== MCP SERVER ERROR ===")
            logger.error(f"Server: {server_name}")
            logger.error(f"MCP tool call timeout: {tool_name}")
            import sys
            sys.stdout.flush()
            raise
        except Exception as e:
            logger.error(f"=== MCP SERVER ERROR ===")
            logger.error(f"Server: {server_name}")
            logger.error(f"MCP tool call error: {e}", exc_info=True)
            import sys
            sys.stdout.flush()
            raise
