"""Weeek task tracker API integration."""

import os
import httpx
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from client/.env
env_path = Path(__file__).parent / "client" / ".env"
load_dotenv(dotenv_path=env_path)

WEEEK_API_BASE_URL = "https://api.weeek.net/public/v1"
WEEEK_API_TOKEN = os.getenv("WEEEK_API_TOKEN")

if not WEEEK_API_TOKEN:
    raise ValueError("WEEEK_API_TOKEN not found in .env file")

BOARD_COLUMN_STATE_MAP = {
    1: "Backlog",
    2: "In progress",
    3: "Done"
}


class WeeekAPIError(Exception):
    """Raised when Weeek API call fails."""
    pass


async def get_tasks() -> List[Dict[str, Any]]:
    """
    Fetch all tasks from Weeek task tracker.

    Returns:
        List of task dictionaries with id, title, and state fields

    Raises:
        WeeekAPIError: If API call fails with error message
    """
    url = f"{WEEEK_API_BASE_URL}/tm/tasks"
    headers = {
        "Authorization": f"Bearer {WEEEK_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                raise WeeekAPIError(f"Unexpected response format: expected dict, got {type(data)}")

            tasks_data = data.get("tasks", data.get("data", []))

            if not isinstance(tasks_data, list):
                raise WeeekAPIError(f"Unexpected tasks format: expected list, got {type(tasks_data)}")

            tasks = []
            for task in tasks_data:
                task_id = task.get("id")
                title = task.get("title") or task.get("name", "")
                board_column_id = task.get("boardColumnId")

                if task_id is None:
                    continue

                state = BOARD_COLUMN_STATE_MAP.get(board_column_id, "Unknown")

                tasks.append({
                    "id": task_id,
                    "title": title,
                    "state": state
                })

            return tasks

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        raise WeeekAPIError(f"HTTP {e.response.status_code}: {error_detail}")
    except httpx.RequestError as e:
        raise WeeekAPIError(f"Network error: {str(e)}")
    except Exception as e:
        raise WeeekAPIError(f"Unexpected error: {str(e)}")
