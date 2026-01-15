"""HTTP client for Weeek API."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

WEEEK_API_BASE = "https://api.weeek.net/public/v1"


class WeeekClient:
    """Client for Weeek Task Management API."""

    def __init__(
        self,
        api_token: str,
        project_id: int,
        board_id: int,
        column_open_id: int,
        column_in_progress_id: int,
        column_done_id: int,
    ):
        self.api_token = api_token
        self.project_id = project_id
        self.board_id = board_id
        self.column_ids = {
            "Open": column_open_id,
            "In Progress": column_in_progress_id,
            "Done": column_done_id,
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=WEEEK_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_column_name(self, column_id: int) -> str:
        """Get column name by ID."""
        for name, cid in self.column_ids.items():
            if cid == column_id:
                return name
        return f"Unknown ({column_id})"

    def _get_priority_name(self, priority: Optional[int]) -> str:
        """Get priority name."""
        mapping = {0: "Low", 1: "Medium", 2: "High", 3: "Hold"}
        return mapping.get(priority, "Unknown")

    async def list_tasks(self) -> Dict[str, Any]:
        """
        Get all tasks from the board.

        Returns:
            Dict with tasks grouped by status
        """
        client = await self._get_client()

        params = {
            "projectId": self.project_id,
            "boardId": self.board_id,
        }

        logger.info(f"Fetching tasks: projectId={self.project_id}, boardId={self.board_id}")
        response = await client.get("/tm/tasks", params=params)

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Weeek API error: {response.status_code} - {error_text}")
            return {"error": f"Weeek API error: {response.status_code} - {error_text}"}

        data = response.json()
        tasks = data.get("tasks", [])

        grouped = {"Open": [], "In Progress": [], "Done": []}

        for task in tasks:
            task_info = {
                "id": task.get("id"),
                "title": task.get("title", ""),
                "description": task.get("description", ""),
                "priority": self._get_priority_name(task.get("priority")),
                "priority_value": task.get("priority"),
                "status": self._get_column_name(task.get("boardColumnId")),
            }

            status = task_info["status"]
            if status in grouped:
                grouped[status].append(task_info)
            else:
                grouped.setdefault("Other", []).append(task_info)

        return {
            "total_count": len(tasks),
            "tasks_by_status": grouped,
        }

    async def get_task(self, task_id: int) -> Dict[str, Any]:
        """
        Get task details by ID.

        Args:
            task_id: Task ID in Weeek

        Returns:
            Task details or error
        """
        client = await self._get_client()

        logger.info(f"Fetching task: {task_id}")
        response = await client.get(f"/tm/tasks/{task_id}")

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Weeek API error: {response.status_code} - {error_text}")
            return {"error": f"Weeek API error: {response.status_code} - {error_text}"}

        data = response.json()
        task = data.get("task", {})

        return {
            "id": task.get("id"),
            "title": task.get("title", ""),
            "description": task.get("description", ""),
            "priority": self._get_priority_name(task.get("priority")),
            "priority_value": task.get("priority"),
            "status": self._get_column_name(task.get("boardColumnId")),
            "created_at": task.get("createdAt"),
            "updated_at": task.get("updatedAt"),
        }

    async def find_task_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """
        Find task by exact title match.

        Args:
            title: Exact task title

        Returns:
            Task info or None if not found
        """
        result = await self.list_tasks()

        if "error" in result:
            return None

        for status_tasks in result.get("tasks_by_status", {}).values():
            for task in status_tasks:
                if task.get("title") == title:
                    return task

        return None

    async def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: int = 1,
    ) -> Dict[str, Any]:
        """
        Create a new task.

        Args:
            title: Task title
            description: Task description
            priority: Priority (0=Low, 1=Medium, 2=High)

        Returns:
            Created task info or error
        """
        client = await self._get_client()

        body = {
            "title": title,
            "description": description,
            "priority": priority,
            "boardId": self.board_id,
            "boardColumnId": self.column_ids["Open"],
        }

        logger.info(f"Creating task: {title}")
        response = await client.post("/tm/tasks", json=body)

        if response.status_code not in (200, 201):
            error_text = response.text
            logger.error(f"Weeek API error: {response.status_code} - {error_text}")
            return {"error": f"Weeek API error: {response.status_code} - {error_text}"}

        data = response.json()
        task = data.get("task", {})

        return {
            "success": True,
            "id": task.get("id"),
            "title": task.get("title", title),
            "description": task.get("description", description),
            "priority": self._get_priority_name(task.get("priority", priority)),
            "status": "Open",
        }

    async def move_task(
        self,
        task_id: int,
        new_status: str,
    ) -> Dict[str, Any]:
        """
        Move task to a different status.

        Args:
            task_id: Task ID
            new_status: New status (Open, In Progress, Done)

        Returns:
            Updated task info or error
        """
        if new_status not in self.column_ids:
            return {"error": f"Invalid status: {new_status}. Valid: Open, In Progress, Done"}

        client = await self._get_client()

        body = {
            "boardColumnId": self.column_ids[new_status],
        }

        logger.info(f"Moving task {task_id} to {new_status}")
        response = await client.put(f"/tm/tasks/{task_id}", json=body)

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Weeek API error: {response.status_code} - {error_text}")
            return {"error": f"Weeek API error: {response.status_code} - {error_text}"}

        data = response.json()
        task = data.get("task", {})

        return {
            "success": True,
            "id": task.get("id", task_id),
            "title": task.get("title", ""),
            "new_status": new_status,
        }
