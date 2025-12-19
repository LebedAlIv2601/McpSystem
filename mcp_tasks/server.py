"""MCP Task Tracker Server."""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from weeek_api import get_tasks, WeeekAPIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = Server("task-tracker-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_tasks",
            description="Retrieves all tasks from Weeek task tracker. Returns task ID, title, and state (Backlog, In progress, or Done). Use this tool to get current task information.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool call received: {name} with arguments: {arguments}")

    if name != "get_tasks":
        error_msg = f"Unknown tool: {name}. Only 'get_tasks' is supported."
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=json.dumps({"error": error_msg})
        )]

    try:
        logger.info("Fetching tasks from Weeek API")
        tasks = await get_tasks()

        result = {"tasks": tasks}

        logger.info(f"Successfully retrieved {len(tasks)} tasks")

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except WeeekAPIError as e:
        error_msg = str(e)
        logger.error(f"Weeek API error: {error_msg}")
        return [TextContent(
            type="text",
            text=json.dumps({"error": error_msg})
        )]

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [TextContent(
            type="text",
            text=json.dumps({"error": error_msg})
        )]


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
