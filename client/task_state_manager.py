"""Task state persistence and change detection module."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class TaskStateManager:
    """Manages task state persistence and change detection."""

    def __init__(self, snapshot_file: str = "tasks_snapshot.json"):
        """Initialize task state manager.

        Args:
            snapshot_file: Name of the JSON file to store task snapshots
        """
        self.snapshot_path = Path(__file__).parent / snapshot_file
        logger.info(f"Task state manager initialized with file: {self.snapshot_path}")

    def load_state(self) -> Dict[str, Any]:
        """Load last task snapshot from JSON file.

        Returns:
            Dictionary with task data, or empty dict if file doesn't exist
        """
        if not self.snapshot_path.exists():
            logger.debug("Snapshot file does not exist, returning empty state")
            return {}

        try:
            with open(self.snapshot_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            logger.debug(f"Loaded state with {len(state.get('tasks', []))} tasks")
            return state
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return {}

    def save_state(self, tasks: List[Dict[str, Any]]) -> None:
        """Save current task snapshot to JSON file.

        Args:
            tasks: List of task dictionaries from MCP get_tasks response
        """
        try:
            state = {"tasks": tasks}
            with open(self.snapshot_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(tasks)} tasks to snapshot")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def clear_state(self) -> None:
        """Delete snapshot file or reset to empty dict."""
        try:
            if self.snapshot_path.exists():
                self.snapshot_path.unlink()
                logger.info("Cleared task snapshot file")
            else:
                logger.debug("Snapshot file already cleared")
        except Exception as e:
            logger.error(f"Failed to clear state: {e}")

    def compare_states(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Compare two task states and detect changes.

        Args:
            old_state: Previous task state dictionary
            new_state: Current task state dictionary

        Returns:
            Dictionary with change categories:
            {
                "new_tasks": [...],
                "deleted_tasks": [...],
                "state_changes": [...],
                "title_changes": [...]
            }
        """
        old_tasks = {task['id']: task for task in old_state.get('tasks', [])}
        new_tasks = {task['id']: task for task in new_state.get('tasks', [])}

        changes = {
            "new_tasks": [],
            "deleted_tasks": [],
            "state_changes": [],
            "title_changes": []
        }

        # Detect new tasks
        for task_id, task in new_tasks.items():
            if task_id not in old_tasks:
                changes["new_tasks"].append(task)

        # Detect deleted tasks
        for task_id, task in old_tasks.items():
            if task_id not in new_tasks:
                changes["deleted_tasks"].append(task)

        # Detect state and title changes
        for task_id, new_task in new_tasks.items():
            if task_id in old_tasks:
                old_task = old_tasks[task_id]

                # State change
                if old_task.get('state') != new_task.get('state'):
                    changes["state_changes"].append({
                        "id": task_id,
                        "title": new_task.get('title'),
                        "old_state": old_task.get('state'),
                        "new_state": new_task.get('state')
                    })

                # Title change
                if old_task.get('title') != new_task.get('title'):
                    changes["title_changes"].append({
                        "id": task_id,
                        "old_title": old_task.get('title'),
                        "new_title": new_task.get('title')
                    })

        logger.debug(f"Detected changes: {len(changes['new_tasks'])} new, "
                    f"{len(changes['deleted_tasks'])} deleted, "
                    f"{len(changes['state_changes'])} state changes, "
                    f"{len(changes['title_changes'])} title changes")

        return changes
