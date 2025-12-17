"""Summary message formatting module."""

from typing import Dict, List, Any


class SummaryFormatter:
    """Formats task change summaries for user notifications."""

    @staticmethod
    def format_summary(changes: Dict[str, List[Any]]) -> str:
        """Generate human-readable summary message from changes.

        Args:
            changes: Dictionary containing change categories from TaskStateManager.compare_states()

        Returns:
            Formatted summary message string
        """
        sections = []
        header = "📊 Task Updates (Last 2 minutes):\n"

        # New tasks section
        if changes["new_tasks"]:
            lines = ["✨ New tasks:"]
            for task in changes["new_tasks"]:
                title = task.get('title', 'Untitled')
                task_id = task.get('id', 'Unknown')
                state = task.get('state', 'Unknown')
                lines.append(f"  • {title} (ID: {task_id}) - {state}")
            sections.append("\n".join(lines))

        # State changes section
        if changes["state_changes"]:
            lines = ["🔄 State changes:"]
            for change in changes["state_changes"]:
                title = change.get('title', 'Untitled')
                task_id = change.get('id', 'Unknown')
                old_state = change.get('old_state', 'Unknown')
                new_state = change.get('new_state', 'Unknown')
                lines.append(f"  • {title} (ID: {task_id}): {old_state} → {new_state}")
            sections.append("\n".join(lines))

        # Title changes section
        if changes["title_changes"]:
            lines = ["✏️ Title changes:"]
            for change in changes["title_changes"]:
                task_id = change.get('id', 'Unknown')
                old_title = change.get('old_title', 'Unknown')
                new_title = change.get('new_title', 'Unknown')
                lines.append(f"  • ID {task_id}: \"{old_title}\" → \"{new_title}\"")
            sections.append("\n".join(lines))

        # Deleted tasks section
        if changes["deleted_tasks"]:
            lines = ["🗑️ Deleted tasks:"]
            for task in changes["deleted_tasks"]:
                title = task.get('title', 'Untitled')
                task_id = task.get('id', 'Unknown')
                lines.append(f"  • {title} (ID: {task_id})")
            sections.append("\n".join(lines))

        # Build final message
        if sections:
            message = header + "\n" + "\n\n".join(sections)
        else:
            message = header + "\nNo changes in the last 2 minutes."

        return message
