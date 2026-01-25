"""HTTP client for Ollama API communication."""

import logging
from typing import Optional, Dict, List
import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"


class OllamaClient:
    """Client for communicating with local Ollama API."""

    def __init__(self):
        self.ollama_url = OLLAMA_URL
        self.model_name = OLLAMA_MODEL
        self._client: Optional[httpx.AsyncClient] = None
        self._conversation_history: Dict[str, List[Dict]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0)
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_conversation(self, user_id: str) -> List[Dict]:
        """Get conversation history for user."""
        if user_id not in self._conversation_history:
            self._conversation_history[user_id] = []
        return self._conversation_history[user_id]

    def _add_to_conversation(self, user_id: str, role: str, content: str) -> None:
        """Add message to conversation history."""
        conversation = self._get_conversation(user_id)
        conversation.append({"role": role, "content": content})

        # Keep only last 10 messages to avoid context overflow
        if len(conversation) > 10:
            self._conversation_history[user_id] = conversation[-10:]

    async def send_message(self, user_id: str, message: str) -> str:
        """
        Send message to Ollama and get response.

        Args:
            user_id: Unique user identifier
            message: User message text

        Returns:
            Response text from model

        Raises:
            Exception: If Ollama request fails
        """
        client = await self._get_client()
        url = f"{self.ollama_url}/api/chat"

        # Add user message to history
        self._add_to_conversation(user_id, "user", message)

        # Get conversation context
        messages = self._get_conversation(user_id)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }

        logger.info(f"Sending request to Ollama: user={user_id}, model={self.model_name}")

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract assistant response
            assistant_message = data.get("message", {})
            response_text = assistant_message.get("content", "")

            if not response_text:
                logger.warning("Empty response from Ollama")
                response_text = "Извините, я не смог сгенерировать ответ."

            # Add assistant response to history
            self._add_to_conversation(user_id, "assistant", response_text)

            logger.info(f"Ollama response received for user {user_id}")

            return response_text

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Ollama HTTP error {e.response.status_code}: {error_body}")

            if e.response.status_code == 404:
                raise Exception(f"Model {self.model_name} not found. Run: ollama pull {self.model_name}")
            else:
                raise Exception(f"Ollama error: {e.response.status_code}")

        except httpx.ConnectError:
            logger.error(f"Cannot connect to Ollama at {self.ollama_url}")
            raise Exception("Cannot connect to Ollama service")

        except Exception as e:
            logger.error(f"Ollama request error: {e}", exc_info=True)
            raise

    async def send_message_with_system_prompt(
        self,
        user_id: str,
        message: str,
        system_prompt: str
    ) -> str:
        """
        Send message to Ollama with custom system prompt.
        Does not use conversation history.

        Args:
            user_id: Unique user identifier (for logging)
            message: User message text
            system_prompt: System prompt to guide the model

        Returns:
            Response text from model

        Raises:
            Exception: If Ollama request fails
        """
        client = await self._get_client()
        url = f"{self.ollama_url}/api/chat"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }

        logger.info(f"Sending request to Ollama with system prompt: user={user_id}, model={self.model_name}")

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract assistant response
            assistant_message = data.get("message", {})
            response_text = assistant_message.get("content", "")

            if not response_text:
                logger.warning("Empty response from Ollama")
                response_text = "Извините, я не смог сгенерировать ответ."

            logger.info(f"Ollama response received for user {user_id}")

            return response_text

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Ollama HTTP error {e.response.status_code}: {error_body}")

            if e.response.status_code == 404:
                raise Exception(f"Model {self.model_name} not found. Run: ollama pull {self.model_name}")
            else:
                raise Exception(f"Ollama error: {e.response.status_code}")

        except httpx.ConnectError:
            logger.error(f"Cannot connect to Ollama at {self.ollama_url}")
            raise Exception("Cannot connect to Ollama service")

        except Exception as e:
            logger.error(f"Ollama request error: {e}", exc_info=True)
            raise

    def clear_conversation(self, user_id: str) -> None:
        """Clear conversation history for user."""
        if user_id in self._conversation_history:
            del self._conversation_history[user_id]
            logger.info(f"Cleared conversation for user {user_id}")
