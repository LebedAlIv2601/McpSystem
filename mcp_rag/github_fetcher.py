"""GitHub API client for fetching files from repository."""

import asyncio
import base64
import logging
from typing import Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubFetcher:
    """Fetches files from GitHub repository via API."""

    def __init__(self, token: str, owner: str, repo: str, specs_path: str = "specs"):
        """
        Initialize GitHub fetcher.

        Args:
            token: GitHub personal access token
            owner: Repository owner
            repo: Repository name
            specs_path: Path to specs folder in repository
        """
        self.token = token
        self.owner = owner
        self.repo = repo
        self.specs_path = specs_path
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, str] = {}  # filename -> content cache

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
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

    async def list_specs_files(self) -> List[Dict[str, str]]:
        """
        List all files in the specs folder.

        Returns:
            List of dicts with 'name', 'path', 'type' keys
        """
        client = await self._get_client()
        url = f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo}/contents/{self.specs_path}"

        try:
            response = await client.get(url)
            response.raise_for_status()

            contents = response.json()

            files = []
            for item in contents:
                if item.get("type") == "file":
                    files.append({
                        "name": item["name"],
                        "path": item["path"],
                        "download_url": item.get("download_url"),
                        "sha": item.get("sha")
                    })

            logger.info(f"Found {len(files)} files in {self.specs_path}")
            return files

        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error listing files: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error listing specs files: {e}", exc_info=True)
            raise

    async def get_file_content(self, file_path: str, use_cache: bool = True) -> str:
        """
        Get content of a specific file.

        Args:
            file_path: Path to file in repository
            use_cache: Whether to use cached content

        Returns:
            File content as string
        """
        if use_cache and file_path in self._cache:
            logger.info(f"Using cached content for {file_path}")
            return self._cache[file_path]

        client = await self._get_client()
        url = f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo}/contents/{file_path}"

        try:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()

            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"]).decode("utf-8")
            else:
                content = data.get("content", "")

            self._cache[file_path] = content
            logger.info(f"Fetched {file_path}: {len(content)} chars")
            return content

        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error fetching {file_path}: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching file {file_path}: {e}", exc_info=True)
            raise

    async def get_all_specs_content(self) -> List[Dict[str, str]]:
        """
        Fetch all files from specs folder with their content.

        Returns:
            List of dicts with 'filename', 'path', 'content' keys
        """
        files = await self.list_specs_files()

        results = []
        for file_info in files:
            try:
                content = await self.get_file_content(file_info["path"])
                results.append({
                    "filename": file_info["name"],
                    "path": file_info["path"],
                    "content": content
                })
            except Exception as e:
                logger.error(f"Failed to fetch {file_info['name']}: {e}")

        logger.info(f"Successfully fetched {len(results)} spec files")
        return results

    def clear_cache(self) -> None:
        """Clear content cache."""
        self._cache.clear()
        logger.info("GitHub fetcher cache cleared")
