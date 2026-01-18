"""Build state manager for tracking active APK builds."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ActiveBuild:
    """Represents an active build in progress."""

    workflow_run_id: int
    branch: str
    started_at: datetime


class BuildStateManager:
    """
    Manages active build state per user.

    Tracks which users have builds in progress to prevent
    parallel builds from the same user.
    """

    def __init__(self):
        self._active_builds: Dict[str, ActiveBuild] = {}

    def has_active_build(self, user_id: str) -> bool:
        """Check if user has an active build."""
        return user_id in self._active_builds

    def start_build(self, user_id: str, workflow_run_id: int, branch: str) -> None:
        """
        Register a new active build for user.

        Args:
            user_id: Telegram user ID
            workflow_run_id: GitHub Actions workflow run ID
            branch: Git branch being built
        """
        self._active_builds[user_id] = ActiveBuild(
            workflow_run_id=workflow_run_id,
            branch=branch,
            started_at=datetime.now()
        )
        logger.info(f"Build started for user {user_id}: workflow_run_id={workflow_run_id}, branch={branch}")

    def complete_build(self, user_id: str) -> None:
        """
        Mark user's build as completed.

        Args:
            user_id: Telegram user ID
        """
        if user_id in self._active_builds:
            build = self._active_builds.pop(user_id)
            duration = (datetime.now() - build.started_at).total_seconds()
            logger.info(f"Build completed for user {user_id}: workflow_run_id={build.workflow_run_id}, duration={duration:.1f}s")

    def get_active_build(self, user_id: str) -> Optional[ActiveBuild]:
        """
        Get active build info for user.

        Args:
            user_id: Telegram user ID

        Returns:
            ActiveBuild if user has active build, None otherwise
        """
        return self._active_builds.get(user_id)

    def get_all_active_builds(self) -> Dict[str, ActiveBuild]:
        """Get all active builds (for debugging/monitoring)."""
        return self._active_builds.copy()


# Singleton instance
_build_state_manager: Optional[BuildStateManager] = None


def get_build_state_manager() -> BuildStateManager:
    """Get singleton BuildStateManager instance."""
    global _build_state_manager
    if _build_state_manager is None:
        _build_state_manager = BuildStateManager()
    return _build_state_manager
