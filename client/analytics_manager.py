"""Analytics MCP server lifecycle manager."""

import asyncio
import logging
import subprocess
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class AnalyticsManager:
    """Manages Analytics MCP server lifecycle and tool calls."""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.session: Optional[ClientSession] = None
        self.available_tools: List[Dict[str, Any]] = []
        self._context_manager = None
        self._streams = None

    async def start(self) -> None:
        """Start Analytics MCP server and establish connection."""
        logger.info("Starting Analytics MCP server...")

        # Path to analytics MCP server
        server_path = Path(__file__).parent / "mcp_analytics" / "server.py"

        if not server_path.exists():
            raise RuntimeError(f"Analytics MCP server not found at {server_path}")

        # Start server via stdio
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_path)],
            env=None
        )

        try:
            self._context_manager = stdio_client(server_params)
            stdio_transport = await self._context_manager.__aenter__()
            self._streams = stdio_transport
            read_stream, write_stream = stdio_transport

            self.session = ClientSession(read_stream, write_stream)
            await self.session.__aenter__()

            # Initialize session
            await self.session.initialize()

            # List available tools
            response = await self.session.list_tools()
            self.available_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
                for tool in response.tools
            ]

            logger.info(f"Analytics MCP server started with {len(self.available_tools)} tools")
            for tool in self.available_tools:
                logger.info(f"  - {tool['name']}: {tool['description']}")

        except Exception as e:
            logger.error(f"Failed to start Analytics MCP server: {e}", exc_info=True)
            await self.stop()
            raise RuntimeError(f"Failed to start Analytics MCP server: {e}")

    async def stop(self) -> None:
        """Stop Analytics MCP server."""
        logger.info("Stopping Analytics MCP server...")

        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error stopping session: {e}")
            self.session = None

        if self._context_manager and self._streams:
            try:
                await self._context_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error stopping context manager: {e}")
            self._context_manager = None
            self._streams = None

        logger.info("Analytics MCP server stopped")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an analytics tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool response as dict

        Raises:
            RuntimeError: If session is not initialized or tool call fails
        """
        if not self.session:
            raise RuntimeError("Analytics MCP session not initialized")

        logger.info(f"Calling analytics tool: {tool_name} with args: {arguments}")

        try:
            result = await self.session.call_tool(tool_name, arguments)

            if not result.content:
                logger.warning(f"Tool {tool_name} returned no content")
                return {"error": "No content returned from tool"}

            # Parse text content
            response_text = result.content[0].text
            response_data = json.loads(response_text)

            logger.info(f"Tool {tool_name} completed successfully")
            return response_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool response: {e}")
            return {"error": f"Invalid JSON response: {e}"}
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}", exc_info=True)
            return {"error": str(e)}

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available analytics tools."""
        return self.available_tools

    async def get_events(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        screen: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get filtered events."""
        args = {"limit": limit}
        if user_id:
            args["user_id"] = user_id
        if event_type:
            args["event_type"] = event_type
        if screen:
            args["screen"] = screen

        return await self.call_tool("get_events", args)

    async def analyze_errors(self, top_n: int = 10) -> Dict[str, Any]:
        """Analyze top errors."""
        return await self.call_tool("analyze_errors", {"top_n": top_n})

    async def analyze_funnel(self) -> Dict[str, Any]:
        """Analyze conversion funnel."""
        return await self.call_tool("analyze_funnel", {})

    async def analyze_dropoff(self) -> Dict[str, Any]:
        """Analyze user dropoff points."""
        return await self.call_tool("analyze_dropoff", {})

    async def get_user_journey(self, user_id: str) -> Dict[str, Any]:
        """Get user journey."""
        return await self.call_tool("get_user_journey", {"user_id": user_id})

    async def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        return await self.call_tool("get_statistics", {})
