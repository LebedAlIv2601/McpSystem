"""GitHub API client for build polling and artifact download."""

import io
import logging
import zipfile
from typing import Optional, Tuple

import httpx

from config import GITHUB_TOKEN, GITHUB_REPO

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubBuildClient:
    """Client for interacting with GitHub Actions API for build operations."""

    def __init__(self):
        self.token = GITHUB_TOKEN
        self.repo = GITHUB_REPO
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            if not self.token:
                raise ValueError("GITHUB_TOKEN not configured")

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_workflow_run_status(self, run_id: int) -> Tuple[str, Optional[str]]:
        """
        Get workflow run status.

        Args:
            run_id: GitHub Actions workflow run ID

        Returns:
            Tuple of (status, conclusion)
            status: queued, in_progress, completed
            conclusion: success, failure, cancelled (only when completed)
        """
        client = await self._get_client()
        url = f"{GITHUB_API_BASE}/repos/{self.repo}/actions/runs/{run_id}"

        try:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            status = data.get("status", "unknown")
            conclusion = data.get("conclusion")

            logger.debug(f"Workflow {run_id} status: {status}, conclusion: {conclusion}")
            return status, conclusion

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get workflow status: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            raise

    async def get_workflow_run_url(self, run_id: int) -> str:
        """
        Get HTML URL for workflow run.

        Args:
            run_id: GitHub Actions workflow run ID

        Returns:
            URL to view workflow run in browser
        """
        client = await self._get_client()
        url = f"{GITHUB_API_BASE}/repos/{self.repo}/actions/runs/{run_id}"

        try:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            return data.get("html_url", f"https://github.com/{self.repo}/actions/runs/{run_id}")

        except Exception as e:
            logger.error(f"Error getting workflow URL: {e}")
            return f"https://github.com/{self.repo}/actions/runs/{run_id}"

    async def download_artifact(self, run_id: int, artifact_name: str = "apk") -> Optional[bytes]:
        """
        Download artifact from completed workflow run.

        Args:
            run_id: GitHub Actions workflow run ID
            artifact_name: Name of the artifact to download

        Returns:
            APK file content as bytes, or None if not found
        """
        client = await self._get_client()

        # Get artifacts for the run
        artifacts_url = f"{GITHUB_API_BASE}/repos/{self.repo}/actions/runs/{run_id}/artifacts"

        try:
            response = await client.get(artifacts_url)
            response.raise_for_status()

            data = response.json()
            artifacts = data.get("artifacts", [])

            # Find the artifact by name
            target_artifact = None
            for artifact in artifacts:
                if artifact.get("name") == artifact_name:
                    target_artifact = artifact
                    break

            if not target_artifact:
                logger.error(f"Artifact '{artifact_name}' not found in run {run_id}")
                return None

            artifact_id = target_artifact.get("id")
            download_url = f"{GITHUB_API_BASE}/repos/{self.repo}/actions/artifacts/{artifact_id}/zip"

            logger.info(f"Downloading artifact {artifact_id} from {download_url}")

            # Download the artifact ZIP
            download_response = await client.get(download_url, follow_redirects=True)
            download_response.raise_for_status()

            zip_content = download_response.content
            logger.info(f"Downloaded ZIP: {len(zip_content)} bytes")

            # Extract APK from ZIP
            apk_content = self._extract_apk_from_zip(zip_content)
            return apk_content

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to download artifact: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error downloading artifact: {e}", exc_info=True)
            raise

    def _extract_apk_from_zip(self, zip_content: bytes) -> Optional[bytes]:
        """
        Extract APK file from ZIP archive.

        Args:
            zip_content: ZIP file content

        Returns:
            APK file content or None if not found
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                # List files in ZIP
                file_list = zf.namelist()
                logger.debug(f"Files in ZIP: {file_list}")

                # Find APK file (could be at root or in subdirectory)
                apk_file = None
                for name in file_list:
                    if name.endswith(".apk"):
                        apk_file = name
                        break

                if not apk_file:
                    logger.error("No APK file found in artifact ZIP")
                    return None

                logger.info(f"Extracting APK: {apk_file}")
                apk_content = zf.read(apk_file)
                logger.info(f"Extracted APK: {len(apk_content)} bytes")

                return apk_content

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting APK: {e}", exc_info=True)
            return None
