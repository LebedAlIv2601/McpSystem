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

MCP_SERVER_PATH = Path(__file__).parent.parent / "server.py"

PYTHON_INTERPRETER = Path(__file__).parent.parent / "venv" / "bin" / "python"

MAX_CONVERSATION_HISTORY = 50

WELCOME_MESSAGE = "Hello! Use /tasks command to manage your tasks from Weeek task tracker.\n\nExample:\n/tasks show me what's in progress\n/tasks list all my tasks"

MCP_USED_INDICATOR = "\n\n✓ MCP was used"

ERROR_MESSAGE = "Sorry, something went wrong. Please try again."

TOOL_CALL_TIMEOUT = 30.0

# Periodic task monitoring configuration
TASK_FETCH_INTERVAL = 30  # seconds - how often to fetch tasks from MCP
SUMMARY_INTERVAL = 120  # seconds (2 minutes) - how often to send summaries
TASKS_SNAPSHOT_FILE = "tasks_snapshot.json"
SUBSCRIBERS_FILE = "subscribers.json"
