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

# Bot messages
WELCOME_MESSAGE = """Добро пожаловать!

Я профессиональный астроном, готовый ответить на ваши вопросы о Вселенной.

Задавайте любые вопросы по астрономии!

Примеры:
- Как образуются черные дыры?
- Что такое красное смещение?
- Как ученые находят экзопланеты?
- Объясни природу темной материи"""

ERROR_MESSAGE = "Извините, произошла ошибка. Пожалуйста, попробуйте еще раз."
