"""MCP server for analytics data analysis."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import List, Dict, Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

EVENTS_FILE = Path(__file__).parent.parent / "analytics" / "events.json"

server = Server("analytics")

events_data: List[Dict[str, Any]] = []


def load_events() -> List[Dict[str, Any]]:
    """Load events from JSON file."""
    global events_data

    if events_data:
        return events_data

    try:
        with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
            events_data = json.load(f)
        logger.info(f"Loaded {len(events_data)} events from {EVENTS_FILE}")
        return events_data
    except Exception as e:
        logger.error(f"Error loading events: {e}")
        return []


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available analytics tools."""
    return [
        Tool(
            name="get_events",
            description="Get events with optional filters. Returns filtered list of events based on user_id, event_type, screen, or date_range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Filter by user ID (optional)"
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Filter by event type (optional)"
                    },
                    "screen": {
                        "type": "string",
                        "description": "Filter by screen name (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events to return (default: 50)",
                        "default": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="analyze_errors",
            description="Analyze errors in the system. Returns top errors grouped by error code with counts, affected screens, and sample messages.",
            inputSchema={
                "type": "object",
                "properties": {
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top errors to return (default: 10)",
                        "default": 10
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="analyze_funnel",
            description="Analyze conversion funnel across screens. Returns user flow statistics from catalog through confirmation, showing dropoff at each step.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="analyze_dropoff",
            description="Analyze user dropoff points. Returns screens where users most frequently abandon their sessions, with dropoff counts and percentages.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_user_journey",
            description="Get detailed journey for a specific user. Returns chronological list of all events for the user showing their path through the app.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID to analyze"
                    }
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="get_statistics",
            description="Get overall statistics. Returns total counts of users, sessions, events, conversion rate, and most popular screens/categories.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        load_events()

        if name == "get_events":
            return await handle_get_events(arguments)
        elif name == "analyze_errors":
            return await handle_analyze_errors(arguments)
        elif name == "analyze_funnel":
            return await handle_analyze_funnel(arguments)
        elif name == "analyze_dropoff":
            return await handle_analyze_dropoff(arguments)
        elif name == "get_user_journey":
            return await handle_get_user_journey(arguments)
        elif name == "get_statistics":
            return await handle_get_statistics(arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    except Exception as e:
        logger.error(f"Tool {name} error: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def handle_get_events(arguments: dict) -> list[TextContent]:
    """Handle get_events tool call."""
    user_id = arguments.get("user_id")
    event_type = arguments.get("event_type")
    screen = arguments.get("screen")
    limit = arguments.get("limit", 50)

    filtered = events_data

    if user_id:
        filtered = [e for e in filtered if e.get("user_id") == user_id]
    if event_type:
        filtered = [e for e in filtered if e.get("event_type") == event_type]
    if screen:
        filtered = [e for e in filtered if e.get("screen") == screen]

    filtered = filtered[:limit]

    response = {
        "total_matched": len(filtered),
        "filters_applied": {
            "user_id": user_id,
            "event_type": event_type,
            "screen": screen
        },
        "events": filtered
    }

    return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def handle_analyze_errors(arguments: dict) -> list[TextContent]:
    """Handle analyze_errors tool call."""
    top_n = arguments.get("top_n", 10)

    error_events = [e for e in events_data if e.get("event_type") == "error"]

    if not error_events:
        return [TextContent(type="text", text=json.dumps({
            "total_errors": 0,
            "message": "No errors found in the data"
        }))]

    # Group by error code
    errors_by_code = defaultdict(list)
    for event in error_events:
        error_code = event.get("properties", {}).get("error_code", "UNKNOWN")
        errors_by_code[error_code].append(event)

    # Build error statistics
    error_stats = []
    for error_code, events in errors_by_code.items():
        screens = Counter(e.get("screen") for e in events)
        users = set(e.get("user_id") for e in events)
        messages = set(e.get("properties", {}).get("error_message", "") for e in events)

        error_stats.append({
            "error_code": error_code,
            "count": len(events),
            "affected_users": len(users),
            "screens": dict(screens),
            "sample_messages": list(messages)
        })

    # Sort by count
    error_stats.sort(key=lambda x: x["count"], reverse=True)
    error_stats = error_stats[:top_n]

    response = {
        "total_errors": len(error_events),
        "unique_error_codes": len(errors_by_code),
        "top_errors": error_stats
    }

    return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def handle_analyze_funnel(arguments: dict) -> list[TextContent]:
    """Handle analyze_funnel tool call."""
    funnel_screens = ["catalog", "product", "cart", "checkout", "payment", "confirmation"]

    # Get unique users who reached each screen
    users_by_screen = {}
    for screen in funnel_screens:
        users_at_screen = set(
            e.get("user_id") for e in events_data
            if e.get("screen") == screen
        )
        users_by_screen[screen] = users_at_screen

    # Calculate funnel
    funnel_data = []
    total_users = len(users_by_screen.get("catalog", set()))

    for i, screen in enumerate(funnel_screens):
        users = users_by_screen.get(screen, set())
        count = len(users)

        if total_users > 0:
            conversion = (count / total_users) * 100
        else:
            conversion = 0

        # Calculate dropoff from previous step
        if i > 0:
            prev_screen = funnel_screens[i - 1]
            prev_count = len(users_by_screen.get(prev_screen, set()))
            if prev_count > 0:
                dropoff = ((prev_count - count) / prev_count) * 100
            else:
                dropoff = 0
        else:
            dropoff = 0

        funnel_data.append({
            "screen": screen,
            "users": count,
            "conversion_from_start": round(conversion, 2),
            "dropoff_from_previous": round(dropoff, 2)
        })

    response = {
        "funnel": funnel_data,
        "total_users": total_users,
        "completed_purchases": len(users_by_screen.get("confirmation", set()))
    }

    return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def handle_analyze_dropoff(arguments: dict) -> list[TextContent]:
    """Handle analyze_dropoff tool call."""
    # Find session_end events
    session_ends = [e for e in events_data if e.get("event_type") == "session_end"]

    # Group by screen where session ended
    dropoff_by_screen = Counter(e.get("screen") for e in session_ends)

    total_dropoffs = sum(dropoff_by_screen.values())

    dropoff_stats = []
    for screen, count in dropoff_by_screen.most_common():
        percentage = (count / total_dropoffs * 100) if total_dropoffs > 0 else 0
        dropoff_stats.append({
            "screen": screen,
            "dropoff_count": count,
            "percentage": round(percentage, 2)
        })

    response = {
        "total_dropoffs": total_dropoffs,
        "dropoff_by_screen": dropoff_stats
    }

    return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def handle_get_user_journey(arguments: dict) -> list[TextContent]:
    """Handle get_user_journey tool call."""
    user_id = arguments.get("user_id")

    if not user_id:
        return [TextContent(type="text", text=json.dumps({"error": "user_id is required"}))]

    user_events = [e for e in events_data if e.get("user_id") == user_id]

    if not user_events:
        return [TextContent(type="text", text=json.dumps({
            "user_id": user_id,
            "message": "No events found for this user"
        }))]

    # Sort by timestamp
    user_events.sort(key=lambda x: x.get("timestamp", ""))

    # Simplify events for journey
    journey = []
    for event in user_events:
        journey.append({
            "timestamp": event.get("timestamp"),
            "event_type": event.get("event_type"),
            "screen": event.get("screen"),
            "properties": event.get("properties", {})
        })

    sessions = set(e.get("session_id") for e in user_events)

    response = {
        "user_id": user_id,
        "total_events": len(user_events),
        "sessions_count": len(sessions),
        "journey": journey
    }

    return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def handle_get_statistics(arguments: dict) -> list[TextContent]:
    """Handle get_statistics tool call."""
    unique_users = set(e.get("user_id") for e in events_data)
    unique_sessions = set(e.get("session_id") for e in events_data)

    # Count event types
    event_types = Counter(e.get("event_type") for e in events_data)

    # Count screens
    screens = Counter(e.get("screen") for e in events_data)

    # Count completed purchases
    completed_purchases = len([
        e for e in events_data
        if e.get("screen") == "confirmation" and e.get("event_type") == "screen_view"
    ])

    # Conversion rate
    started_users = len(set(
        e.get("user_id") for e in events_data
        if e.get("event_type") == "session_start"
    ))

    if started_users > 0:
        conversion_rate = (completed_purchases / started_users) * 100
    else:
        conversion_rate = 0

    # Categories
    categories = Counter()
    for event in events_data:
        category = event.get("properties", {}).get("category")
        if category:
            categories[category] += 1

    response = {
        "total_users": len(unique_users),
        "total_sessions": len(unique_sessions),
        "total_events": len(events_data),
        "completed_purchases": completed_purchases,
        "conversion_rate": round(conversion_rate, 2),
        "event_types": dict(event_types.most_common()),
        "screens": dict(screens.most_common(10)),
        "categories": dict(categories.most_common())
    }

    return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def main():
    """Run the MCP server."""
    logger.info("Starting Analytics MCP server")
    logger.info(f"Events file: {EVENTS_FILE}")

    # Pre-load events
    load_events()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
