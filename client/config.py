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
WELCOME_MESSAGE = """Добро пожаловать в службу поддержки EasyPomodoro!

Я помогу вам с вопросами по приложению EasyPomodoro.

Что я умею:
- Отвечать на вопросы по использованию приложения
- Помогать с решением проблем
- Создавать и отслеживать ваши обращения

Просто опишите вашу проблему или задайте вопрос!

Примеры:
- Как настроить таймер?
- Приложение не сохраняет настройки
- Как работают уведомления?"""

ERROR_MESSAGE = "Извините, произошла ошибка. Попробуйте ещё раз."
