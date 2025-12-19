"""MCP Facts Server."""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from facts_api import get_random_fact, FactsAPIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = Server("facts-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    logger.info("Tools list requested")
    return [
        Tool(
            name="get_fact",
            description="Retrieves a random fact from API Ninjas Facts API. Returns a single interesting fact. Use this tool when the user asks for a fact or requests interesting information.",
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

    if name != "get_fact":
        error_msg = f"Unknown tool: {name}. Only 'get_fact' is supported."
        logger.error(error_msg)
        return [TextContent(
            type="text",
            text=json.dumps({"error": error_msg})
        )]

    try:
        logger.info("Executing get_fact tool")
        fact = await get_random_fact()

        result = {"fact": fact}

        logger.info(f"Successfully retrieved fact")

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except FactsAPIError as e:
        error_msg = str(e)
        logger.error(f"Facts API error: {error_msg}")
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
    logger.info("Starting Facts MCP server")
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        logger.info("Facts server initialized with stdio transport")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
