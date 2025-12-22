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

# Validate required environment variables
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in .env file")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env file")

OPENROUTER_MODEL = "nex-agi/deepseek-v3.1-nex-n1:free"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Ollama Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "nomic-embed-text"
DOCS_FOLDER = str(Path(__file__).parent.parent / "docs")

# MCP Server Paths (legacy - kept for backward compatibility)
MCP_TASKS_SERVER_PATH = Path(__file__).parent.parent / "mcp_tasks" / "server.py"
MCP_FACTS_SERVER_PATH = Path(__file__).parent.parent / "mcp_facts" / "server.py"

PYTHON_INTERPRETER = Path(__file__).parent.parent / "venv" / "bin" / "python"

# MCP Servers Configuration
# Each server is defined by name, command, and args
MCP_SERVERS = [
    {
        "name": "weeek_tasks",
        "command": str(PYTHON_INTERPRETER),
        "args": [str(MCP_TASKS_SERVER_PATH)],
        "env": None
    },
    {
        "name": "random_facts",
        "command": str(PYTHON_INTERPRETER),
        "args": [str(MCP_FACTS_SERVER_PATH)],
        "env": None
    },
    {
        "name": "mobile_mcp",
        "command": "npx",
        "args": ["-y", "@mobilenext/mobile-mcp@latest"],
        "env": {
            **os.environ.copy(),  # Inherit all environment variables
            "NVM_DIR": str(Path.home() / ".nvm"),
            "PATH": f"{Path.home() / '.nvm/versions/node/v22.21.1/bin'}:{os.getenv('PATH', '')}"
        }
    }
]

MAX_CONVERSATION_HISTORY = 50

WELCOME_MESSAGE = "Hello! Use /tasks command to manage your tasks from Weeek task tracker, /fact to get a random fact, or /docs_embed to generate embeddings from markdown files.\n\nExamples:\n/tasks show me what's in progress\n/tasks list all my tasks\n/fact\n/fact tell me something interesting\n/docs_embed\n\nOther commands:\n/subscribe - Enable periodic task summaries\n/unsubscribe - Disable periodic summaries"

MCP_USED_INDICATOR = "\n\n✓ MCP was used"

ERROR_MESSAGE = "Sorry, something went wrong. Please try again."

TOOL_CALL_TIMEOUT = 30.0

# Periodic task monitoring configuration
TASK_FETCH_INTERVAL = 300000  # seconds - how often to fetch tasks from MCP
SUMMARY_INTERVAL = 1200000  # seconds (2 minutes) - how often to send summaries
TASKS_SNAPSHOT_FILE = "tasks_snapshot.json"
SUBSCRIBERS_FILE = "subscribers.json"
