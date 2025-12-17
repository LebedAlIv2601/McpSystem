"""Background scheduler for periodic task monitoring."""

import asyncio
import json
import logging
from typing import Optional
from telegram import Bot

from task_state_manager import TaskStateManager
from subscribers import SubscriberManager
from openrouter_client import OpenRouterClient
from config import TASK_FETCH_INTERVAL, SUMMARY_INTERVAL

logger = logging.getLogger(__name__)


class PeriodicTaskMonitor:
    """Manages periodic task fetching and summary delivery."""

    def __init__(self, bot: Bot, mcp_manager):
        """Initialize periodic task monitor.

        Args:
            bot: Telegram Bot instance
            mcp_manager: MCPManager instance for tool calls
        """
        self.bot = bot
        self.mcp_manager = mcp_manager
        self.task_state_manager = TaskStateManager()
        self.subscriber_manager = SubscriberManager()
        self.openrouter_client = OpenRouterClient()

        self._fetch_task: Optional[asyncio.Task] = None
        self._summary_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info("PeriodicTaskMonitor initialized")

    async def start(self) -> None:
        """Start both periodic tasks."""
        if self._running:
            logger.warning("PeriodicTaskMonitor already running")
            return

        self._running = True
        self._fetch_task = asyncio.create_task(self._fetch_tasks_loop())
        self._summary_task = asyncio.create_task(self._send_summary_loop())
        logger.info("PeriodicTaskMonitor started: 30s fetch, 2min summaries")

    async def stop(self) -> None:
        """Stop all periodic tasks gracefully."""
        if not self._running:
            return

        self._running = False

        if self._fetch_task:
            self._fetch_task.cancel()
            try:
                await self._fetch_task
            except asyncio.CancelledError:
                pass

        if self._summary_task:
            self._summary_task.cancel()
            try:
                await self._summary_task
            except asyncio.CancelledError:
                pass

        logger.info("PeriodicTaskMonitor stopped")

    async def _fetch_tasks_loop(self) -> None:
        """Background coroutine that fetches tasks every 30 seconds."""
        logger.info("Task fetch loop started")

        while self._running:
            try:
                await asyncio.sleep(TASK_FETCH_INTERVAL)
                await self._fetch_and_save_tasks()
            except asyncio.CancelledError:
                logger.info("Task fetch loop cancelled")
                break
            except Exception as e:
                # Fail silently - log but don't notify users
                logger.error(f"Error in task fetch loop: {e}", exc_info=True)

    async def _send_summary_loop(self) -> None:
        """Background coroutine that sends summaries every 2 minutes."""
        logger.info("Summary send loop started")

        while self._running:
            try:
                await asyncio.sleep(SUMMARY_INTERVAL)
                await self._generate_and_send_summary()
            except asyncio.CancelledError:
                logger.info("Summary send loop cancelled")
                break
            except Exception as e:
                # Fail silently - log but don't notify users
                logger.error(f"Error in summary send loop: {e}", exc_info=True)

    async def _fetch_and_save_tasks(self) -> None:
        """Fetch tasks from MCP and save to JSON snapshot.

        Only saves if snapshot doesn't exist, to preserve baseline for 2-minute comparison.
        """
        try:
            logger.info("Periodic: Fetching tasks from MCP (30s cycle)")

            # Call MCP tool
            result = await self.mcp_manager.call_tool("get_tasks", {})

            # Parse result
            if "result" in result:
                tasks_data = json.loads(result["result"])
                tasks = tasks_data.get("tasks", [])

                # Only save if snapshot doesn't exist (preserves baseline for 2-minute comparison)
                current_state = self.task_state_manager.load_state()
                if not current_state or not current_state.get("tasks"):
                    self.task_state_manager.save_state(tasks)
                    logger.info(f"Periodic: Saved {len(tasks)} tasks to snapshot (baseline)")
                else:
                    logger.debug(f"Periodic: Fetched {len(tasks)} tasks, snapshot exists, not overwriting")
            else:
                logger.warning("Periodic: No result from MCP get_tasks")

        except Exception as e:
            # Fail silently
            logger.error(f"Periodic: Failed to fetch tasks: {e}", exc_info=True)

    async def _generate_and_send_summary(self) -> None:
        """Generate summary from state changes and send to subscribed users."""
        try:
            logger.info("Periodic: Generating 2-minute summary")

            # Load old state (from snapshot before it's cleared)
            old_state = self.task_state_manager.load_state()

            # Fetch current tasks
            result = await self.mcp_manager.call_tool("get_tasks", {})

            if "result" not in result:
                logger.warning("Periodic: No result from MCP for summary")
                return

            # Parse current state
            current_tasks_data = json.loads(result["result"])
            current_tasks = current_tasks_data.get("tasks", [])
            current_state = {"tasks": current_tasks}

            # Compare states
            changes = self.task_state_manager.compare_states(old_state, current_state)

            # Generate AI summary using OpenRouter
            summary_message = await self._generate_ai_summary(changes)

            # Get subscribed users
            subscribed_users = self.subscriber_manager.get_subscribed_users()

            if not subscribed_users:
                logger.info("Periodic: No subscribed users, skipping summary delivery")
            else:
                # Send to all subscribed users
                success_count = 0
                for user_id in subscribed_users:
                    try:
                        await self.bot.send_message(
                            chat_id=user_id,
                            text=summary_message
                        )
                        success_count += 1
                    except Exception as e:
                        # Log but continue sending to other users
                        logger.error(f"Periodic: Failed to send summary to user {user_id}: {e}")

                logger.info(f"Periodic: Sent summary to {success_count}/{len(subscribed_users)} users")

            # Clear snapshot after sending summary
            self.task_state_manager.clear_state()
            logger.info("Periodic: Cleared task snapshot")

        except Exception as e:
            # Fail silently
            logger.error(f"Periodic: Failed to generate/send summary: {e}", exc_info=True)

    async def _generate_ai_summary(self, changes: dict) -> str:
        """Generate natural language summary using OpenRouter AI.

        Args:
            changes: Dictionary containing detected changes

        Returns:
            AI-generated summary message
        """
        try:
            # Build structured prompt with changes data
            changes_json = json.dumps(changes, indent=2, ensure_ascii=False)

            prompt = f"""You are a task management assistant. Generate a concise, friendly summary of task changes.

CHANGES DATA:
{changes_json}

INSTRUCTIONS:
- Start with "📊 Task Updates (Last 2 minutes):"
- If there are changes, summarize them in a clear, organized way
- Use emojis to categorize: ✨ (new), 🔄 (state changes), ✏️ (title changes), 🗑️ (deleted)
- If NO changes at all, just say "No changes in the last 2 minutes."
- Be concise and user-friendly
- Include task IDs and relevant details

Generate the summary now:"""

            messages = [{"role": "user", "content": prompt}]

            logger.info("Periodic: Requesting AI summary from OpenRouter")
            summary, _ = await self.openrouter_client.chat_completion(
                messages=messages,
                tools=None,
                tool_choice=None
            )

            if summary:
                logger.info("Periodic: AI summary generated successfully")
                return summary.strip()
            else:
                logger.warning("Periodic: AI summary generation returned empty response")
                return "📊 Task Updates (Last 2 minutes):\n\nNo changes in the last 2 minutes."

        except Exception as e:
            logger.error(f"Periodic: Failed to generate AI summary: {e}", exc_info=True)
            # Fallback to simple message
            return "📊 Task Updates (Last 2 minutes):\n\nUnable to generate summary at this time."
