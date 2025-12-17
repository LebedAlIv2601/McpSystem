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

OPENROUTER_MODEL = "kwaipilot/kat-coder-pro:free"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MCP_SERVER_PATH = Path(__file__).parent.parent / "server.py"

PYTHON_INTERPRETER = Path(__file__).parent.parent / "venv" / "bin" / "python"

MAX_CONVERSATION_HISTORY = 50

WELCOME_MESSAGE = "Hello! Ask me something about weather"

MCP_USED_INDICATOR = "\n\n✓ MCP was used"

ERROR_MESSAGE = "Sorry, something went wrong. Please try again."

TOOL_CALL_TIMEOUT = 30.0
