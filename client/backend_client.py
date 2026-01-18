"""HTTP client for backend API communication."""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple
import httpx

from config import BACKEND_URL, BACKEND_API_KEY

logger = logging.getLogger(__name__)


@dataclass
class BuildRequest:
    """Build request info from backend."""
    workflow_run_id: int
    branch: str
    user_id: str


@dataclass
class ChatResult:
    """Result from chat endpoint."""
    response: str
    mcp_used: bool
    build_request: Optional[BuildRequest] = None


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

    async def send_message(self, user_id: str, message: str) -> ChatResult:
        """
        Send message to backend and get response.

        Args:
            user_id: Unique user identifier
            message: User message text

        Returns:
            ChatResult with response, mcp_used flag, and optional build_request

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

            # Parse build_request if present
            build_request = None
            build_request_data = data.get("build_request")
            if build_request_data:
                build_request = BuildRequest(
                    workflow_run_id=build_request_data["workflow_run_id"],
                    branch=build_request_data["branch"],
                    user_id=build_request_data["user_id"]
                )
                logger.info(f"Build request received: workflow_run_id={build_request.workflow_run_id}, branch={build_request.branch}")

            logger.info(f"Backend response: mcp_used={mcp_used}, tool_calls={tool_calls_count}, has_build_request={build_request is not None}")

            return ChatResult(
                response=response_text,
                mcp_used=mcp_used,
                build_request=build_request
            )

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

    async def notify_build_complete(self, user_id: str) -> None:
        """
        Notify backend that a build has completed.

        Args:
            user_id: User whose build completed
        """
        client = await self._get_client()
        url = f"{self.backend_url}/api/build-complete"

        try:
            response = await client.post(url, params={"user_id": user_id})
            response.raise_for_status()
            logger.info(f"Backend notified of build completion for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to notify backend of build completion: {e}")
