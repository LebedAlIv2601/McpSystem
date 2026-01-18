"""MCP server for RAG-based documentation retrieval."""

import asyncio
import json
import logging
import os
import sys
import time

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from github_fetcher import GitHubFetcher
from rag_engine import RAGEngine, EmbeddingError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "LebedAlIv2601")
GITHUB_REPO = os.getenv("GITHUB_REPO", "EasyPomodoro")
SPECS_PATH = os.getenv("SPECS_PATH", "specs")

# Build configuration (hardcoded per spec)
WORKFLOW_FILE = "build-apk.yml"
DEFAULT_BRANCH = "master"
GITHUB_API_BASE = "https://api.github.com"

server = Server("rag-specs")

github_fetcher: GitHubFetcher = None
rag_engine: RAGEngine = None
index_built: bool = False


def get_github_fetcher() -> GitHubFetcher:
    """Get or create GitHub fetcher instance."""
    global github_fetcher
    if github_fetcher is None:
        github_fetcher = GitHubFetcher(
            token=GITHUB_TOKEN,
            owner=GITHUB_OWNER,
            repo=GITHUB_REPO,
            specs_path=SPECS_PATH
        )
    return github_fetcher


def get_rag_engine() -> RAGEngine:
    """Get or create RAG engine instance."""
    global rag_engine
    if rag_engine is None:
        rag_engine = RAGEngine()
    return rag_engine


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available RAG tools."""
    return [
        Tool(
            name="rag_query",
            description="Search project documentation using RAG. Retrieves relevant documentation chunks based on semantic similarity. Use this to find information about the EasyPomodoro project architecture, features, and implementation details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant documentation"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_specs",
            description="List all available specification files in the project documentation folder. Returns file names and paths.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_spec_content",
            description="Get the full content of a specific specification file. Use this when you need to read an entire documentation file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the specification file to retrieve"
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="rebuild_index",
            description="Rebuild the RAG index by fetching fresh documentation from GitHub. Use this if the documentation has been updated.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_project_structure",
            description="Get the project directory structure as a tree. Use this FIRST to find file paths before using get_file_contents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Starting path (e.g., 'app/src/main/java'). Empty for root.",
                        "default": ""
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Max depth to traverse (default: 4)",
                        "default": 4
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="build_apk",
            description="Trigger Android APK build for EasyPomodoro project. Use this when user asks to build APK, create a build, or get an APK file. The build runs on GitHub Actions and the APK will be sent to the user's Telegram chat.",
            inputSchema={
                "type": "object",
                "properties": {
                    "branch": {
                        "type": "string",
                        "description": "Git branch to build from. Defaults to 'master' if not specified.",
                        "default": "master"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Telegram user ID who requested the build (passed from context)"
                    }
                },
                "required": ["user_id"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    global index_built

    try:
        if name == "rag_query":
            return await handle_rag_query(arguments)
        elif name == "list_specs":
            return await handle_list_specs()
        elif name == "get_spec_content":
            return await handle_get_spec_content(arguments)
        elif name == "rebuild_index":
            return await handle_rebuild_index()
        elif name == "get_project_structure":
            return await handle_get_project_structure(arguments)
        elif name == "build_apk":
            return await handle_build_apk(arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    except Exception as e:
        logger.error(f"Tool {name} error: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def ensure_index_built() -> bool:
    """Ensure RAG index is built, building it if necessary."""
    global index_built

    if index_built:
        return True

    try:
        fetcher = get_github_fetcher()
        engine = get_rag_engine()

        logger.info("Fetching specs from GitHub for indexing...")
        docs = await fetcher.get_all_specs_content()

        if not docs:
            logger.warning("No documentation files found")
            return False

        documents = [{"filename": d["filename"], "content": d["content"]} for d in docs]
        chunk_count = await engine.build_index(documents)

        if chunk_count > 0:
            index_built = True
            logger.info(f"RAG index built with {chunk_count} chunks")
            return True
        else:
            return False

    except EmbeddingError as e:
        logger.error(f"Embedding error while building index: {e}")
        raise
    except Exception as e:
        logger.error(f"Error building index: {e}", exc_info=True)
        raise


async def handle_rag_query(arguments: dict) -> list[TextContent]:
    """Handle rag_query tool call."""
    query = arguments.get("query", "")
    top_k = arguments.get("top_k", 5)

    if not query:
        return [TextContent(type="text", text=json.dumps({"error": "Query is required"}))]

    try:
        await ensure_index_built()
    except EmbeddingError as e:
        return [TextContent(type="text", text=json.dumps({
            "error": f"Embedding service not available: {e}. Please check OPENROUTER_API_KEY."
        }))]

    engine = get_rag_engine()
    results = await engine.search(query, top_k=top_k)

    if not results:
        return [TextContent(type="text", text=json.dumps({
            "query": query,
            "results": [],
            "message": "No relevant documentation found"
        }))]

    formatted_results = []
    for chunk_text, score, filename in results:
        formatted_results.append({
            "filename": filename,
            "score": round(score, 4),
            "content": chunk_text
        })

    response = {
        "query": query,
        "results_count": len(formatted_results),
        "results": formatted_results
    }

    return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def handle_list_specs() -> list[TextContent]:
    """Handle list_specs tool call."""
    fetcher = get_github_fetcher()

    try:
        files = await fetcher.list_specs_files()
        response = {
            "specs_path": f"{GITHUB_OWNER}/{GITHUB_REPO}/{SPECS_PATH}",
            "files_count": len(files),
            "files": [{"name": f["name"], "path": f["path"]} for f in files]
        }
        return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def handle_get_spec_content(arguments: dict) -> list[TextContent]:
    """Handle get_spec_content tool call."""
    filename = arguments.get("filename", "")

    if not filename:
        return [TextContent(type="text", text=json.dumps({"error": "Filename is required"}))]

    fetcher = get_github_fetcher()

    try:
        file_path = f"{SPECS_PATH}/{filename}"
        content = await fetcher.get_file_content(file_path)
        response = {
            "filename": filename,
            "path": file_path,
            "content": content
        }
        return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def handle_rebuild_index() -> list[TextContent]:
    """Handle rebuild_index tool call."""
    global index_built

    fetcher = get_github_fetcher()
    engine = get_rag_engine()

    try:
        fetcher.clear_cache()
        engine.clear_index()
        index_built = False

        logger.info("Rebuilding RAG index...")
        docs = await fetcher.get_all_specs_content()

        if not docs:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": "No documentation files found"
            }))]

        documents = [{"filename": d["filename"], "content": d["content"]} for d in docs]
        chunk_count = await engine.build_index(documents)

        if chunk_count > 0:
            index_built = True
            stats = engine.get_index_stats()
            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "message": "Index rebuilt successfully",
                "stats": stats
            }, ensure_ascii=False, indent=2))]
        else:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": "Failed to build index - no chunks created"
            }))]

    except EmbeddingError as e:
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": f"Embedding service not available: {e}"
        }))]
    except Exception as e:
        logger.error(f"Error rebuilding index: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": str(e)
        }))]


async def handle_get_project_structure(arguments: dict) -> list[TextContent]:
    """Handle get_project_structure tool call."""
    path = arguments.get("path", "")
    max_depth = arguments.get("max_depth", 4)

    fetcher = get_github_fetcher()

    try:
        structure = await fetcher.get_directory_tree(path, max_depth)
        response = {
            "repository": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            "path": path or "/",
            "structure": structure
        }
        return [TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def handle_build_apk(arguments: dict) -> list[TextContent]:
    """Handle build_apk tool call - triggers GitHub Actions workflow."""
    branch = arguments.get("branch", DEFAULT_BRANCH)
    user_id = arguments.get("user_id", "")

    if not user_id:
        return [TextContent(type="text", text=json.dumps({
            "error": "user_id is required"
        }))]

    if not GITHUB_TOKEN:
        return [TextContent(type="text", text=json.dumps({
            "error": "GitHub token not configured"
        }))]

    logger.info(f"Build APK requested: branch={branch}, user_id={user_id}")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    ) as client:
        # 1. Validate branch exists
        branch_url = f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/branches/{branch}"
        try:
            branch_response = await client.get(branch_url)
            if branch_response.status_code == 404:
                return [TextContent(type="text", text=json.dumps({
                    "error": f"Branch '{branch}' not found in repository {GITHUB_OWNER}/{GITHUB_REPO}"
                }))]
            branch_response.raise_for_status()
            logger.info(f"Branch '{branch}' validated")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return [TextContent(type="text", text=json.dumps({
                    "error": f"Branch '{branch}' not found in repository {GITHUB_OWNER}/{GITHUB_REPO}"
                }))]
            return [TextContent(type="text", text=json.dumps({
                "error": f"Failed to validate branch: {e.response.status_code}"
            }))]

        # 2. Trigger workflow_dispatch
        dispatch_url = f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
        dispatch_payload = {
            "ref": branch,
            "inputs": {
                "branch": branch
            }
        }

        try:
            dispatch_response = await client.post(dispatch_url, json=dispatch_payload)
            if dispatch_response.status_code == 404:
                return [TextContent(type="text", text=json.dumps({
                    "error": f"Workflow '{WORKFLOW_FILE}' not found. Make sure it exists in .github/workflows/"
                }))]
            dispatch_response.raise_for_status()
            logger.info(f"Workflow dispatch triggered for branch '{branch}'")
        except httpx.HTTPStatusError as e:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Failed to trigger workflow: {e.response.status_code} - {e.response.text}"
            }))]

        # 3. Get the workflow run ID (need to wait briefly and poll)
        await asyncio.sleep(2)

        runs_url = f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/runs"
        params = {"event": "workflow_dispatch", "per_page": 5}

        workflow_run_id = None
        for attempt in range(5):
            try:
                runs_response = await client.get(runs_url, params=params)
                runs_response.raise_for_status()
                runs_data = runs_response.json()

                for run in runs_data.get("workflow_runs", []):
                    if run.get("head_branch") == branch and run.get("status") in ["queued", "in_progress"]:
                        workflow_run_id = run.get("id")
                        logger.info(f"Found workflow run: {workflow_run_id}")
                        break

                if workflow_run_id:
                    break

                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} to get workflow run failed: {e}")
                await asyncio.sleep(2)

        if not workflow_run_id:
            return [TextContent(type="text", text=json.dumps({
                "error": "Workflow triggered but could not retrieve run ID. Build may still be running."
            }))]

        # Return success with workflow_run_id for client to poll
        return [TextContent(type="text", text=json.dumps({
            "success": True,
            "workflow_run_id": workflow_run_id,
            "branch": branch,
            "user_id": user_id,
            "message": f"Build started for branch '{branch}'. APK will be sent when ready."
        }))]


async def main():
    """Run the MCP server."""
    logger.info("Starting RAG MCP server")
    logger.info(f"GitHub repo: {GITHUB_OWNER}/{GITHUB_REPO}")
    logger.info(f"Specs path: {SPECS_PATH}")
    logger.info(f"Embedding model: google/gemini-embedding-001 (OpenRouter)")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
