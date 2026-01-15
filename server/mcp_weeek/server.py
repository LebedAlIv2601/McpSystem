"""MCP server for Weeek task management."""

import asyncio
import json
import logging
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from weeek_client import WeeekClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
WEEEK_API_TOKEN = os.getenv("WEEEK_API_TOKEN", "")
WEEEK_PROJECT_ID = int(os.getenv("WEEEK_PROJECT_ID", "0"))
WEEEK_BOARD_ID = int(os.getenv("WEEEK_BOARD_ID", "0"))
WEEEK_COLUMN_OPEN_ID = int(os.getenv("WEEEK_COLUMN_OPEN_ID", "0"))
WEEEK_COLUMN_IN_PROGRESS_ID = int(os.getenv("WEEEK_COLUMN_IN_PROGRESS_ID", "0"))
WEEEK_COLUMN_DONE_ID = int(os.getenv("WEEEK_COLUMN_DONE_ID", "0"))

server = Server("weeek-tasks")

weeek_client: WeeekClient = None


def get_weeek_client() -> WeeekClient:
    """Get or create Weeek client instance."""
    global weeek_client
    if weeek_client is None:
        weeek_client = WeeekClient(
            api_token=WEEEK_API_TOKEN,
            project_id=WEEEK_PROJECT_ID,
            board_id=WEEEK_BOARD_ID,
            column_open_id=WEEEK_COLUMN_OPEN_ID,
            column_in_progress_id=WEEEK_COLUMN_IN_PROGRESS_ID,
            column_done_id=WEEEK_COLUMN_DONE_ID,
        )
    return weeek_client


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Weeek tools."""
    return [
        Tool(
            name="list_tasks",
            description="Получить список задач из Weeek. Возвращает все задачи с текущей доски проекта, сгруппированные по статусам (Open, In Progress, Done).",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_task_details",
            description="Получить детальную информацию о задаче по её ID или точному названию.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "ID задачи в Weeek"
                    },
                    "title": {
                        "type": "string",
                        "description": "Точное название задачи (альтернатива task_id)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="create_task",
            description="Создать новую задачу в Weeek. Задача создаётся в статусе Open. Приоритет определяется автоматически на основе контекста, если не указан явно.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Название задачи"
                    },
                    "description": {
                        "type": "string",
                        "description": "Описание задачи"
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Приоритет: 0=Low, 1=Medium, 2=High. По умолчанию 1 (Medium).",
                        "enum": [0, 1, 2],
                        "default": 1
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="move_task",
            description="Переместить задачу в другой статус (Open, In Progress, Done). Требуется указать task_id или точное название задачи.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "ID задачи"
                    },
                    "title": {
                        "type": "string",
                        "description": "Точное название задачи (альтернатива task_id)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Новый статус задачи",
                        "enum": ["Open", "In Progress", "Done"]
                    }
                },
                "required": ["status"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "list_tasks":
            return await handle_list_tasks()
        elif name == "get_task_details":
            return await handle_get_task_details(arguments)
        elif name == "create_task":
            return await handle_create_task(arguments)
        elif name == "move_task":
            return await handle_move_task(arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    except Exception as e:
        logger.error(f"Tool {name} error: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def handle_list_tasks() -> list[TextContent]:
    """Handle list_tasks tool call."""
    client = get_weeek_client()
    result = await client.list_tasks()
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def handle_get_task_details(arguments: dict) -> list[TextContent]:
    """Handle get_task_details tool call."""
    task_id = arguments.get("task_id")
    title = arguments.get("title")

    if not task_id and not title:
        return [TextContent(type="text", text=json.dumps({
            "error": "Требуется task_id или title"
        }))]

    client = get_weeek_client()

    if task_id:
        result = await client.get_task(task_id)
    else:
        task = await client.find_task_by_title(title)
        if task:
            result = await client.get_task(task["id"])
        else:
            result = {"error": f"Задача с названием '{title}' не найдена"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def handle_create_task(arguments: dict) -> list[TextContent]:
    """Handle create_task tool call."""
    title = arguments.get("title")

    if not title:
        return [TextContent(type="text", text=json.dumps({
            "error": "Требуется title"
        }))]

    description = arguments.get("description")
    priority = arguments.get("priority", 1)

    client = get_weeek_client()
    result = await client.create_task(
        title=title,
        description=description,
        priority=priority,
    )

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def handle_move_task(arguments: dict) -> list[TextContent]:
    """Handle move_task tool call."""
    task_id = arguments.get("task_id")
    title = arguments.get("title")
    status = arguments.get("status")

    if not status:
        return [TextContent(type="text", text=json.dumps({
            "error": "Требуется status (Open, In Progress, Done)"
        }))]

    if not task_id and not title:
        return [TextContent(type="text", text=json.dumps({
            "error": "Требуется task_id или title"
        }))]

    client = get_weeek_client()

    # Resolve task_id from title if needed
    if not task_id:
        task = await client.find_task_by_title(title)
        if not task:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Задача с названием '{title}' не найдена"
            }))]
        task_id = task["id"]

    result = await client.move_task(task_id, status)

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    """Run the MCP server."""
    logger.info("Starting Weeek MCP server")
    logger.info(f"Project ID: {WEEEK_PROJECT_ID}")
    logger.info(f"Board ID: {WEEEK_BOARD_ID}")
    logger.info(f"Column IDs: Open={WEEEK_COLUMN_OPEN_ID}, In Progress={WEEEK_COLUMN_IN_PROGRESS_ID}, Done={WEEEK_COLUMN_DONE_ID}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
