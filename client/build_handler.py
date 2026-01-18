"""Build handler for polling GitHub Actions and delivering APK to Telegram."""

import asyncio
import logging
import os
import tempfile
from datetime import datetime
from typing import Optional

from telegram import Bot

from config import BUILD_POLL_INTERVAL, BUILD_TIMEOUT
from github_client import GitHubBuildClient
from backend_client import BackendClient

logger = logging.getLogger(__name__)


class BuildHandler:
    """Handles build polling and APK delivery to Telegram."""

    def __init__(self, bot: Bot, backend_client: BackendClient):
        self.bot = bot
        self.backend_client = backend_client
        self.github_client = GitHubBuildClient()

    async def close(self) -> None:
        """Close clients."""
        await self.github_client.close()

    async def handle_build_request(
        self,
        chat_id: int,
        user_id: str,
        workflow_run_id: int,
        branch: str
    ) -> None:
        """
        Handle a build request - start polling and deliver APK when ready.

        Args:
            chat_id: Telegram chat ID to send APK to
            user_id: User ID for backend notification
            workflow_run_id: GitHub Actions workflow run ID
            branch: Branch being built
        """
        logger.info(f"Starting build handler for user {user_id}, workflow {workflow_run_id}, branch {branch}")

        # Send initial message
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"Сборка запущена на ветке `{branch}`. Ожидайте, это может занять 5-15 минут..."
            )
        except Exception as e:
            logger.error(f"Failed to send initial message: {e}")

        # Start polling in background
        asyncio.create_task(
            self._poll_and_deliver(chat_id, user_id, workflow_run_id, branch)
        )

    async def _poll_and_deliver(
        self,
        chat_id: int,
        user_id: str,
        workflow_run_id: int,
        branch: str
    ) -> None:
        """
        Poll workflow status and deliver APK when complete.

        Args:
            chat_id: Telegram chat ID
            user_id: User ID
            workflow_run_id: Workflow run ID
            branch: Branch being built
        """
        start_time = datetime.now()

        try:
            while True:
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > BUILD_TIMEOUT:
                    logger.warning(f"Build timeout for workflow {workflow_run_id}")
                    run_url = await self.github_client.get_workflow_run_url(workflow_run_id)
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=f"Сборка превысила таймаут (15 минут). Проверьте статус: {run_url}"
                    )
                    break

                # Poll status
                try:
                    status, conclusion = await self.github_client.get_workflow_run_status(workflow_run_id)
                    logger.info(f"Workflow {workflow_run_id}: status={status}, conclusion={conclusion}")

                    if status == "completed":
                        if conclusion == "success":
                            await self._handle_success(chat_id, workflow_run_id, branch)
                        else:
                            await self._handle_failure(chat_id, workflow_run_id, conclusion)
                        break

                except Exception as e:
                    logger.error(f"Error polling workflow status: {e}")

                # Wait before next poll
                await asyncio.sleep(BUILD_POLL_INTERVAL)

        finally:
            # Notify backend that build is complete
            try:
                await self.backend_client.notify_build_complete(user_id)
            except Exception as e:
                logger.error(f"Failed to notify backend of build completion: {e}")

    async def _handle_success(self, chat_id: int, workflow_run_id: int, branch: str) -> None:
        """Handle successful build - download and send APK."""
        logger.info(f"Build successful for workflow {workflow_run_id}")

        try:
            # Download APK
            apk_content = await self.github_client.download_artifact(workflow_run_id)

            if not apk_content:
                run_url = await self.github_client.get_workflow_run_url(workflow_run_id)
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=f"Сборка завершена, но не удалось скачать APK. Проверьте артефакты: {run_url}"
                )
                return

            # Generate filename
            filename = self._generate_apk_filename(branch)

            # Save to temp file and send
            with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tmp:
                tmp.write(apk_content)
                tmp_path = tmp.name

            try:
                logger.info(f"Sending APK to chat {chat_id}: {filename} ({len(apk_content)} bytes)")
                await self.bot.send_document(
                    chat_id=chat_id,
                    document=open(tmp_path, "rb"),
                    filename=filename
                )
                logger.info(f"APK sent successfully to chat {chat_id}")
            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error handling successful build: {e}", exc_info=True)
            run_url = await self.github_client.get_workflow_run_url(workflow_run_id)
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"Не удалось отправить APK: {str(e)}\n\nСкачайте вручную: {run_url}"
            )

    async def _handle_failure(self, chat_id: int, workflow_run_id: int, conclusion: Optional[str]) -> None:
        """Handle failed build."""
        logger.info(f"Build failed for workflow {workflow_run_id}: {conclusion}")

        run_url = await self.github_client.get_workflow_run_url(workflow_run_id)
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"Сборка упала ({conclusion or 'unknown'}). Детали: {run_url}"
        )

    def _generate_apk_filename(self, branch: str) -> str:
        """
        Generate APK filename with branch and timestamp.

        Args:
            branch: Git branch name

        Returns:
            Filename like EasyPomodoro-feature_login-20240115-1423.apk
        """
        # Replace / with _ in branch name
        safe_branch = branch.replace("/", "_").replace("\\", "_")

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")

        return f"EasyPomodoro-{safe_branch}-{timestamp}.apk"
