"""HTTP client for backend API communication."""

import asyncio
import logging
from typing import Optional, Tuple, Dict, Any
import httpx

from config import BACKEND_URL, BACKEND_API_KEY

logger = logging.getLogger(__name__)


class BackendClient:
    """Client for communicating with MCP backend API."""

    def __init__(self):
        self.backend_url = BACKEND_URL.rstrip('/')
        self.api_key = BACKEND_API_KEY
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=30.0),
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json"
                }
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send_message(self, user_id: str, message: str) -> Tuple[str, bool]:
        """
        Send message to backend and get response.

        Args:
            user_id: Unique user identifier
            message: User message text

        Returns:
            Tuple of (response_text, mcp_was_used)

        Raises:
            Exception: If backend request fails
        """
        client = await self._get_client()
        url = f"{self.backend_url}/api/chat"

        payload = {
            "user_id": user_id,
            "message": message
        }

        logger.info(f"Sending request to backend: user={user_id}")

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            response_text = data.get("response", "")
            mcp_used = data.get("mcp_used", False)
            tool_calls_count = data.get("tool_calls_count", 0)

            logger.info(f"Backend response: mcp_used={mcp_used}, tool_calls={tool_calls_count}")

            return response_text, mcp_used

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Backend HTTP error {e.response.status_code}: {error_body}")

            if e.response.status_code == 401:
                raise Exception("Invalid API key")
            elif e.response.status_code == 503:
                raise Exception("Backend service unavailable")
            else:
                raise Exception(f"Backend error: {e.response.status_code}")

        except httpx.ConnectError:
            logger.error(f"Cannot connect to backend at {self.backend_url}")
            raise Exception("Cannot connect to backend service")

        except Exception as e:
            logger.error(f"Backend request error: {e}", exc_info=True)
            raise

    async def health_check(self) -> bool:
        """
        Check if backend is healthy.

        Returns:
            True if backend is healthy, False otherwise
        """
        client = await self._get_client()
        url = f"{self.backend_url}/health"

        try:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            status = data.get("status", "unhealthy")

            logger.info(f"Backend health: {status}")
            return status == "healthy"

        except Exception as e:
            logger.error(f"Backend health check failed: {e}")
            return False

    async def submit_chat_async(self, user_id: str, message: str) -> str:
        """
        Submit chat message for async processing.

        Args:
            user_id: Unique user identifier
            message: User message text

        Returns:
            Task ID for polling

        Raises:
            Exception: If backend request fails
        """
        client = await self._get_client()
        url = f"{self.backend_url}/api/chat/async"

        payload = {
            "user_id": user_id,
            "message": message
        }

        logger.info(f"Submitting async chat request: user={user_id}")

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            task_id = data.get("task_id")

            logger.info(f"Task submitted: {task_id}")
            return task_id

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Backend HTTP error {e.response.status_code}: {error_body}")

            if e.response.status_code == 401:
                raise Exception("Invalid API key")
            elif e.response.status_code == 503:
                raise Exception("Backend service unavailable")
            else:
                raise Exception(f"Backend error: {e.response.status_code}")

        except httpx.ConnectError:
            logger.error(f"Cannot connect to backend at {self.backend_url}")
            raise Exception("Cannot connect to backend service")

        except Exception as e:
            logger.error(f"Backend request error: {e}", exc_info=True)
            raise

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and result.

        Args:
            task_id: Task ID from submit_chat_async

        Returns:
            Dict with task status, result, etc.

        Raises:
            Exception: If backend request fails
        """
        client = await self._get_client()
        url = f"{self.backend_url}/api/tasks/{task_id}"

        try:
            response = await client.get(url)
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Backend HTTP error {e.response.status_code}: {error_body}")

            if e.response.status_code == 404:
                raise Exception("Task not found (may have expired)")
            elif e.response.status_code == 401:
                raise Exception("Invalid API key")
            else:
                raise Exception(f"Backend error: {e.response.status_code}")

        except Exception as e:
            logger.error(f"Get task status error: {e}", exc_info=True)
            raise

    async def poll_task(self, task_id: str, interval: int = 30, max_wait: int = 600) -> Tuple[str, bool]:
        """
        Poll task until completed or failed.

        Args:
            task_id: Task ID from submit_chat_async
            interval: Polling interval in seconds (default: 30)
            max_wait: Maximum wait time in seconds (default: 600 = 10 minutes)

        Returns:
            Tuple of (response_text, mcp_was_used)

        Raises:
            Exception: If task fails or times out
        """
        logger.info(f"Starting polling for task {task_id} (interval={interval}s, max_wait={max_wait}s)")

        elapsed = 0
        while elapsed < max_wait:
            try:
                task_data = await self.get_task_status(task_id)
                status = task_data.get("status")

                logger.info(f"Task {task_id}: status={status}, elapsed={elapsed}s")

                if status == "completed":
                    result = task_data.get("result", {})
                    response_text = result.get("response", "")
                    mcp_used = result.get("mcp_used", False)
                    tool_calls_count = result.get("tool_calls_count", 0)

                    logger.info(f"Task {task_id}: completed (mcp_used={mcp_used}, tool_calls={tool_calls_count})")
                    return response_text, mcp_used

                elif status == "failed":
                    error = task_data.get("error", "Unknown error")
                    logger.error(f"Task {task_id}: failed with error: {error}")
                    raise Exception(f"Task failed: {error}")

                # Still pending or processing - wait and retry
                await asyncio.sleep(interval)
                elapsed += interval

            except Exception as e:
                if "not found" in str(e).lower():
                    raise Exception(f"Task {task_id} not found (may have expired)")
                raise

        raise Exception(f"Task {task_id} timed out after {max_wait}s")
