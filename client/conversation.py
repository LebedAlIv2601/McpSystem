"""Conversation history manager with per-user storage."""

import threading
from typing import Dict, List
from config import MAX_CONVERSATION_HISTORY


class ConversationManager:
    """Thread-safe conversation history manager for multiple users."""

    def __init__(self):
        self._histories: Dict[int, List[Dict[str, str]]] = {}
        self._lock = threading.Lock()

    def add_message(self, user_id: int, role: str, content: str) -> None:
        """Add message to user's conversation history."""
        with self._lock:
            if user_id not in self._histories:
                self._histories[user_id] = []

            self._histories[user_id].append({
                "role": role,
                "content": content
            })

    def get_history(self, user_id: int) -> List[Dict[str, str]]:
        """Retrieve user's conversation history."""
        with self._lock:
            return self._histories.get(user_id, []).copy()

    def clear_history(self, user_id: int) -> None:
        """Clear user's conversation history."""
        with self._lock:
            if user_id in self._histories:
                self._histories[user_id] = []

    def check_and_clear_if_full(self, user_id: int) -> bool:
        """
        Check if history reached limit and clear if needed.

        Returns:
            True if history was cleared, False otherwise
        """
        with self._lock:
            if user_id in self._histories:
                if len(self._histories[user_id]) >= MAX_CONVERSATION_HISTORY:
                    self._histories[user_id] = []
                    return True
        return False

    def get_message_count(self, user_id: int) -> int:
        """Get current message count for user."""
        with self._lock:
            return len(self._histories.get(user_id, []))
