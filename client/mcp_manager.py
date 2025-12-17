"""MCP client manager for subprocess and connection handling."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import MCP_SERVER_PATH, PYTHON_INTERPRETER, TOOL_CALL_TIMEOUT

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages MCP server subprocess and client connection."""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.stdio_context = None
        self.tools: List[Dict[str, Any]] = []

    @asynccontextmanager
    async def connect(self):
        """Connect to MCP server and initialize client session."""
        server_params = StdioServerParameters(
            command=str(PYTHON_INTERPRETER),
            args=[str(MCP_SERVER_PATH)],
            env=None
        )

        logger.info(f"Starting MCP server: {PYTHON_INTERPRETER} {MCP_SERVER_PATH}")

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                self.session = session
                logger.info("MCP client connected")

                await session.initialize()
                logger.info("MCP session initialized")

                await self._fetch_tools()

                try:
                    yield self
                finally:
                    logger.info("Closing MCP session")
                    self.session = None

    async def _fetch_tools(self) -> None:
        """Fetch available tools from MCP server."""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        logger.info("Fetching tools from MCP server")
        result = await self.session.list_tools()
        self.tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            for tool in result.tools
        ]
        logger.info(f"Fetched {len(self.tools)} tools: {[t['name'] for t in self.tools]}")

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return self.tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute MCP tool call.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        logger.info(f"=== MCP SERVER CALL ===")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Arguments: {arguments}")

        try:
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments),
                timeout=TOOL_CALL_TIMEOUT
            )

            if result.content:
                content_text = ""
                for item in result.content:
                    if hasattr(item, 'text'):
                        content_text += item.text

                logger.info(f"=== MCP SERVER RESPONSE ===")
                logger.info(f"Response: {content_text}")

                return {"result": content_text}
            else:
                logger.info(f"=== MCP SERVER RESPONSE ===")
                logger.info(f"Response: No result")
                return {"result": "No result"}

        except asyncio.TimeoutError:
            logger.error(f"=== MCP SERVER ERROR ===")
            logger.error(f"MCP tool call timeout: {tool_name}")
            import sys
            sys.stdout.flush()
            raise
        except Exception as e:
            logger.error(f"=== MCP SERVER ERROR ===")
            logger.error(f"MCP tool call error: {e}", exc_info=True)
            import sys
            sys.stdout.flush()
            raise
