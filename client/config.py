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
WELCOME_MESSAGE = """Добро пожаловать в EasyPomodoro Project Consultant!

Я AI-ассистент, готов ответить на ваши вопросы о проекте EasyPomodoro.
У меня есть доступ к коду проекта и документации через MCP инструменты.

Просто задайте мне любой вопрос!

Примеры:
- Расскажи о проекте EasyPomodoro
- Какие основные функции есть в приложении?
- Покажи структуру проекта
- Объясни концепцию Pomodoro техники"""

ERROR_MESSAGE = "Извините, произошла ошибка. Пожалуйста, попробуйте еще раз."
