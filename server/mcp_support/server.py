"""MCP server for support ticket management."""

import asyncio
import logging
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_support.database import SupportDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

server = Server("support-tickets")
db = SupportDatabase()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available support tools."""
    return [
        Tool(
            name="get_user_tickets",
            description="Get all tickets for a user. Returns list of tickets with id, status, description, created_at.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID (Telegram user ID)"
                    }
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="create_ticket",
            description="Create a new support ticket for a user. Use when user reports a new issue and has no open tickets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID (Telegram user ID)"
                    },
                    "user_name": {
                        "type": "string",
                        "description": "User name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Initial ticket description - the user's issue or question"
                    }
                },
                "required": ["user_id", "user_name", "description"]
            }
        ),
        Tool(
            name="update_ticket_status",
            description="Update ticket status. Use 'in_progress' when issue is being worked on, 'closed' when resolved.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket ID (UUID)"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "closed"],
                        "description": "New status: 'open', 'in_progress', or 'closed'"
                    }
                },
                "required": ["ticket_id", "status"]
            }
        ),
        Tool(
            name="update_ticket_description",
            description="Update ticket description with new information from the conversation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket ID (UUID)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Updated description including conversation history and resolution details"
                    }
                },
                "required": ["ticket_id", "description"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool call: {name} with args: {arguments}")

    try:
        if name == "get_user_tickets":
            return await handle_get_user_tickets(arguments)
        elif name == "create_ticket":
            return await handle_create_ticket(arguments)
        elif name == "update_ticket_status":
            return await handle_update_ticket_status(arguments)
        elif name == "update_ticket_description":
            return await handle_update_ticket_description(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_get_user_tickets(arguments: dict) -> list[TextContent]:
    """Get all tickets for a user."""
    user_id = arguments.get("user_id")
    if not user_id:
        return [TextContent(type="text", text="Error: user_id is required")]

    tickets = db.get_user_tickets(user_id)

    if not tickets:
        return [TextContent(type="text", text=f"No tickets found for user {user_id}")]

    result = f"Found {len(tickets)} ticket(s) for user {user_id}:\n\n"
    for t in tickets:
        result += f"- ID: {t['id']}\n"
        result += f"  Status: {t['status']}\n"
        result += f"  Created: {t['created_at']}\n"
        result += f"  Description: {t['description'][:200]}{'...' if len(t['description']) > 200 else ''}\n\n"

    return [TextContent(type="text", text=result)]


async def handle_create_ticket(arguments: dict) -> list[TextContent]:
    """Create a new ticket."""
    user_id = arguments.get("user_id")
    user_name = arguments.get("user_name", "")
    description = arguments.get("description", "")

    if not user_id:
        return [TextContent(type="text", text="Error: user_id is required")]
    if not description:
        return [TextContent(type="text", text="Error: description is required")]

    open_ticket = db.get_open_ticket(user_id)
    if open_ticket:
        return [TextContent(
            type="text",
            text=f"Error: User already has an open ticket (ID: {open_ticket['id']}, status: {open_ticket['status']}). Close it first."
        )]

    ticket = db.create_ticket(user_id, user_name, description)

    return [TextContent(
        type="text",
        text=f"Ticket created successfully:\n- ID: {ticket['id']}\n- Status: {ticket['status']}\n- Description: {ticket['description']}"
    )]


async def handle_update_ticket_status(arguments: dict) -> list[TextContent]:
    """Update ticket status."""
    ticket_id = arguments.get("ticket_id")
    status = arguments.get("status")

    if not ticket_id:
        return [TextContent(type="text", text="Error: ticket_id is required")]
    if not status:
        return [TextContent(type="text", text="Error: status is required")]

    ticket = db.update_ticket_status(ticket_id, status)

    if not ticket:
        return [TextContent(type="text", text=f"Error: Ticket {ticket_id} not found or invalid status")]

    return [TextContent(
        type="text",
        text=f"Ticket status updated:\n- ID: {ticket['id']}\n- New status: {ticket['status']}"
    )]


async def handle_update_ticket_description(arguments: dict) -> list[TextContent]:
    """Update ticket description."""
    ticket_id = arguments.get("ticket_id")
    description = arguments.get("description")

    if not ticket_id:
        return [TextContent(type="text", text="Error: ticket_id is required")]
    if not description:
        return [TextContent(type="text", text="Error: description is required")]

    ticket = db.update_ticket_description(ticket_id, description)

    if not ticket:
        return [TextContent(type="text", text=f"Error: Ticket {ticket_id} not found")]

    return [TextContent(
        type="text",
        text=f"Ticket description updated:\n- ID: {ticket['id']}\n- Description: {ticket['description'][:200]}..."
    )]


async def main():
    """Run the MCP server."""
    logger.info("Starting Support Tickets MCP server")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
