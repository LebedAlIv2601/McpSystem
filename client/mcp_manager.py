"""MCP client manager for subprocess and connection handling."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import MCP_TASKS_SERVER_PATH, MCP_FACTS_SERVER_PATH, PYTHON_INTERPRETER, TOOL_CALL_TIMEOUT

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages multiple MCP server subprocesses and client connections."""

    def __init__(self):
        self.tasks_session: Optional[ClientSession] = None
        self.facts_session: Optional[ClientSession] = None
        self.tools: List[Dict[str, Any]] = []
        self.tool_server_map: Dict[str, str] = {}  # Maps tool name to server type

    @asynccontextmanager
    async def connect(self):
        """Connect to both MCP servers and initialize client sessions."""
        logger.info("Starting both MCP servers simultaneously")

        # Server parameters for both servers
        tasks_server_params = StdioServerParameters(
            command=str(PYTHON_INTERPRETER),
            args=[str(MCP_TASKS_SERVER_PATH)],
            env=None
        )

        facts_server_params = StdioServerParameters(
            command=str(PYTHON_INTERPRETER),
            args=[str(MCP_FACTS_SERVER_PATH)],
            env=None
        )

        logger.info(f"Starting tasks server: {PYTHON_INTERPRETER} {MCP_TASKS_SERVER_PATH}")
        logger.info(f"Starting facts server: {PYTHON_INTERPRETER} {MCP_FACTS_SERVER_PATH}")

        # Connect to both servers
        async with stdio_client(tasks_server_params) as (tasks_read, tasks_write):
            async with stdio_client(facts_server_params) as (facts_read, facts_write):
                async with ClientSession(tasks_read, tasks_write) as tasks_session:
                    async with ClientSession(facts_read, facts_write) as facts_session:
                        self.tasks_session = tasks_session
                        self.facts_session = facts_session
                        logger.info("Both MCP clients connected")

                        await tasks_session.initialize()
                        logger.info("Tasks MCP session initialized")

                        await facts_session.initialize()
                        logger.info("Facts MCP session initialized")

                        await self._fetch_tools()

                        try:
                            yield self
                        finally:
                            logger.info("Closing both MCP sessions")
                            self.tasks_session = None
                            self.facts_session = None

    async def _fetch_tools(self) -> None:
        """Fetch available tools from both MCP servers."""
        if not self.tasks_session or not self.facts_session:
            raise RuntimeError("MCP sessions not initialized")

        logger.info("Fetching tools from both MCP servers")

        # Fetch tools from tasks server
        tasks_result = await self.tasks_session.list_tools()
        tasks_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            for tool in tasks_result.tools
        ]
        logger.info(f"Fetched {len(tasks_tools)} tools from tasks server: {[t['name'] for t in tasks_tools]}")

        # Fetch tools from facts server
        facts_result = await self.facts_session.list_tools()
        facts_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            for tool in facts_result.tools
        ]
        logger.info(f"Fetched {len(facts_tools)} tools from facts server: {[t['name'] for t in facts_tools]}")

        # Merge tools from both servers
        self.tools = tasks_tools + facts_tools

        # Build tool-to-server mapping for routing
        for tool in tasks_tools:
            self.tool_server_map[tool["name"]] = "tasks"
        for tool in facts_tools:
            self.tool_server_map[tool["name"]] = "facts"

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
        if not self.tasks_session or not self.facts_session:
            raise RuntimeError("MCP sessions not initialized")

        # Determine which server to route to
        server_type = self.tool_server_map.get(tool_name)
        if not server_type:
            raise RuntimeError(f"Unknown tool: {tool_name}")

        session = self.tasks_session if server_type == "tasks" else self.facts_session

        logger.info(f"=== MCP SERVER CALL ===")
        logger.info(f"Server: {server_type}")
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
                logger.info(f"Server: {server_type}")
                logger.info(f"Response: {content_text}")

                return {"result": content_text}
            else:
                logger.info(f"=== MCP SERVER RESPONSE ===")
                logger.info(f"Server: {server_type}")
                logger.info(f"Response: No result")
                return {"result": "No result"}

        except asyncio.TimeoutError:
            logger.error(f"=== MCP SERVER ERROR ===")
            logger.error(f"Server: {server_type}")
            logger.error(f"MCP tool call timeout: {tool_name}")
            import sys
            sys.stdout.flush()
            raise
        except Exception as e:
            logger.error(f"=== MCP SERVER ERROR ===")
            logger.error(f"Server: {server_type}")
            logger.error(f"MCP tool call error: {e}", exc_info=True)
            import sys
            sys.stdout.flush()
            raise
