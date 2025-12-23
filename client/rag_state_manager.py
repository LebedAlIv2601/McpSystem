"""
RAG State Manager

Manages per-user RAG (Retrieval Augmented Generation) enabled/disabled state
with JSON persistence.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class RagStateManager:
    """Manages RAG state for users with persistence"""

    def __init__(self, state_file: str = "rag_state.json"):
        """
        Initialize RAG state manager

        Args:
            state_file: Path to JSON file for state persistence
        """
        self.state_file = Path(__file__).parent / state_file
        self.state: Dict[str, bool] = {}
        self.load_state()

    def is_enabled(self, user_id: int) -> bool:
        """
        Check if RAG is enabled for a user

        Args:
            user_id: Telegram user ID

        Returns:
            True if RAG is enabled, False otherwise (default: False)
        """
        return self.state.get(str(user_id), False)

    def set_enabled(self, user_id: int, enabled: bool) -> None:
        """
        Set RAG enabled/disabled state for a user

        Args:
            user_id: Telegram user ID
            enabled: True to enable RAG, False to disable
        """
        user_id_str = str(user_id)
        self.state[user_id_str] = enabled
        self.save_state()
        logger.info(f"User {user_id}: RAG {'enabled' if enabled else 'disabled'}")

    def load_state(self) -> None:
        """Load RAG state from JSON file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded RAG state for {len(self.state)} users")
            else:
                logger.info("No existing RAG state file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading RAG state: {e}")
            self.state = {}

    def save_state(self) -> None:
        """Save RAG state to JSON file"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved RAG state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving RAG state: {e}")
