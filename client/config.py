"""Configuration module for Telegram bot client."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in .env file")

# Backend Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
if not BACKEND_API_KEY:
    raise ValueError("BACKEND_API_KEY not found in .env file")

# GitHub Configuration for build functionality
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = "LebedAlIv2601/EasyPomodoro"
WORKFLOW_FILE = "build-apk.yml"

# Build polling settings
BUILD_POLL_INTERVAL = 30  # seconds
BUILD_TIMEOUT = 900  # 15 minutes

# Bot messages
WELCOME_MESSAGE = """Welcome to EasyPomodoro Project Consultant!

I'm here to help you understand the EasyPomodoro Android project.

I have access to:
- GitHub Copilot MCP - for browsing project code
- RAG Documentation - for searching project specs
- APK Build - build and send debug APK from any branch

Just ask me anything about the project!

Examples:
- What is the project architecture?
- How does the timer feature work?
- Show me the main activity code
- Build APK from master branch
- Build APK from feature/timer branch"""

ERROR_MESSAGE = "Sorry, something went wrong. Please try again."
