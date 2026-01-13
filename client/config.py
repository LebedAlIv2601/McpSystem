"""Configuration module for Telegram bot client."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Load credentials from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Validate required environment variables
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in .env file")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env file")

# OpenRouter Configuration
OPENROUTER_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# GitHub Repository Configuration
GITHUB_OWNER = "LebedAlIv2601"
GITHUB_REPO = "EasyPomodoro"
SPECS_PATH = "specs"

# GitHub Copilot MCP Configuration
GITHUB_COPILOT_MCP_URL = "https://api.githubcopilot.com/mcp/"

# Paths
PYTHON_INTERPRETER = Path(__file__).parent.parent / "venv" / "bin" / "python"
MCP_RAG_SERVER_PATH = Path(__file__).parent.parent / "mcp_rag" / "server.py"

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
            "SPECS_PATH": SPECS_PATH
        }
    }
]

# Conversation settings
MAX_CONVERSATION_HISTORY = 50

# Bot messages
WELCOME_MESSAGE = """Welcome to EasyPomodoro Project Consultant!

I'm here to help you understand the EasyPomodoro Android project.

I have access to:
- GitHub Copilot MCP - for browsing project code
- RAG Documentation - for searching project specs

Just ask me anything about the project!

Examples:
- What is the project architecture?
- How does the timer feature work?
- Show me the main activity code
- What are the app's core features?"""

MCP_USED_INDICATOR = "\n\n✓ MCP was used"

ERROR_MESSAGE = "Sorry, something went wrong. Please try again."

TOOL_CALL_TIMEOUT = 120.0
