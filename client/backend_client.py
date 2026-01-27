"""HTTP client for backend API communication."""

import io
import logging
from typing import Optional, Tuple
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

    async def get_profile(self, user_id: str) -> Optional[dict]:
        """
        Get user profile from backend.

        Args:
            user_id: User identifier

        Returns:
            Profile dict or None if not found
        """
        client = await self._get_client()
        url = f"{self.backend_url}/api/profile/{user_id}"

        try:
            response = await client.get(url)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()
            return data.get("profile")

        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                logger.error(f"Get profile error: {e}")
            return None
        except Exception as e:
            logger.error(f"Get profile error: {e}")
            return None

    async def update_profile(self, user_id: str, profile_data: dict) -> bool:
        """
        Update user profile on backend.

        Args:
            user_id: User identifier
            profile_data: Profile data to update

        Returns:
            True if successful, False otherwise
        """
        client = await self._get_client()
        url = f"{self.backend_url}/api/profile/{user_id}"

        try:
            response = await client.put(url, json={"data": profile_data})
            response.raise_for_status()
            logger.info(f"Profile updated for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Update profile error: {e}")
            return False

    async def delete_profile(self, user_id: str) -> bool:
        """
        Delete user profile from backend.

        Args:
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        client = await self._get_client()
        url = f"{self.backend_url}/api/profile/{user_id}"

        try:
            response = await client.delete(url)
            response.raise_for_status()
            logger.info(f"Profile deleted for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Delete profile error: {e}")
            return False

    async def send_voice_message(
        self,
        user_id: str,
        audio_bytes: bytes,
        audio_format: str = "oga"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Send voice message to backend for processing.

        Args:
            user_id: User identifier
            audio_bytes: Audio file bytes
            audio_format: Audio format (oga, mp3, wav)

        Returns:
            Tuple of (transcription, response_text)
        """
        url = f"{self.backend_url}/api/chat-voice"

        # Prepare multipart form data
        # Wrap bytes in BytesIO to create file-like object
        audio_file = io.BytesIO(audio_bytes)
        files = {
            "audio": (f"voice.{audio_format}", audio_file, f"audio/{audio_format}")
        }
        data = {
            "user_id": user_id
        }

        logger.info(f"Sending voice message to backend: user={user_id}, size={len(audio_bytes)} bytes")

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    url,
                    headers={"X-API-Key": self.api_key},
                    files=files,
                    data=data
                )
                response.raise_for_status()
                result = response.json()

            transcription = result.get("transcription")
            response_text = result.get("response")
            latency_ms = result.get("latency_ms", 0)
            audio_tokens = result.get("audio_tokens", 0)
            cost_usd = result.get("cost_usd", 0.0)

            logger.info(
                f"Voice message processed: latency={latency_ms}ms, tokens={audio_tokens}, cost=${cost_usd:.6f}"
            )

            return transcription, response_text

        except httpx.HTTPStatusError as e:
            logger.error(f"Backend error: {e.response.status_code} - {e.response.text}")
            return None, None
        except Exception as e:
            logger.error(f"Voice message error: {e}", exc_info=True)
            return None, None
