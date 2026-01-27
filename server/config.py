"""Configuration module for backend server."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# API Authentication
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
if not BACKEND_API_KEY:
    raise ValueError("BACKEND_API_KEY not found in .env file")

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env file")

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v3.2")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
OPENROUTER_EMBEDDING_MODEL = "google/gemini-embedding-001"

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "LebedAlIv2601")
GITHUB_REPO = os.getenv("GITHUB_REPO", "EasyPomodoro")
SPECS_PATH = os.getenv("SPECS_PATH", "specs")

# GitHub Copilot MCP Configuration
GITHUB_COPILOT_MCP_URL = "https://api.githubcopilot.com/mcp/"

# Paths
PYTHON_INTERPRETER = Path(__file__).parent / "mcp_rag" / ".venv" / "bin" / "python"
MCP_RAG_SERVER_PATH = Path(__file__).parent / "mcp_rag" / "server.py"

# Use system python if venv doesn't exist
if not PYTHON_INTERPRETER.exists():
    import sys
    PYTHON_INTERPRETER = Path(sys.executable)

# MCP Servers Configuration
MCP_SERVERS = [
    {
        "name": "github_copilot",
        "transport": "http",
        "url": GITHUB_COPILOT_MCP_URL,
        "auth_token": GITHUB_TOKEN
    },
    {
        "name": "rag_specs",
        "transport": "stdio",
        "command": str(PYTHON_INTERPRETER),
        "args": [str(MCP_RAG_SERVER_PATH)],
        "env": {
            **os.environ.copy(),
            "GITHUB_TOKEN": GITHUB_TOKEN,
            "GITHUB_OWNER": GITHUB_OWNER,
            "GITHUB_REPO": GITHUB_REPO,
            "SPECS_PATH": SPECS_PATH,
            "OPENROUTER_API_KEY": OPENROUTER_API_KEY
        }
    }
]

# Conversation settings
MAX_CONVERSATION_HISTORY = 50

# Tool call settings
TOOL_CALL_TIMEOUT = 120.0

# Essential tools filter - only these tools will be sent to the model
ESSENTIAL_TOOLS = [
    # RAG MCP - project structure (use first!)
    "get_project_structure",
    # GitHub Copilot MCP - file operations
    "get_file_contents",
    # GitHub Copilot MCP - commits
    "list_commits",
    "get_commit",
    # GitHub Copilot MCP - issues
    "list_issues",
    "issue_read",
    # GitHub Copilot MCP - pull requests
    "list_pull_requests",
    "pull_request_read",
    # RAG MCP - documentation
    "rag_query",
    "list_specs",
    "get_spec_content",
]

# Response indicator
MCP_USED_INDICATOR = "\n\n✓ MCP was used"

# Voice input settings
VOICE_MAX_DURATION_SEC = 60  # 1 minute
VOICE_MAX_FILE_SIZE_MB = 10
