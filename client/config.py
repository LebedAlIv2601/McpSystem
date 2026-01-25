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

# Backend Configuration (temporarily disabled, using local Ollama)
# BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
# BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
# if not BACKEND_API_KEY:
#     raise ValueError("BACKEND_API_KEY not found in .env file")

# Analytics Configuration
ANALYTICS_KEYWORDS = [
    "ошибк", "error", "аналитик", "analytics", "статистик", "statistic",
    "воронк", "funnel", "конверс", "conversion", "пользовател", "user",
    "теряю", "dropoff", "отток", "abandon", "данны", "data"
]

# Bot messages
WELCOME_MESSAGE = """Добро пожаловать в EasyPomodoro Project Consultant!

Я локальный AI-ассистент на базе Ollama (llama3.1:8b) с модулем аналитики данных.
Готов ответить на ваши вопросы о проекте EasyPomodoro и проанализировать данные использования приложения.

Просто задайте мне любой вопрос!

Примеры:
- Расскажи о проекте EasyPomodoro
- Какие основные функции есть в приложении?
- Помоги с Android разработкой
- Объясни концепцию Pomodoro техники

Аналитические вопросы:
- Какие ошибки чаще всего получают пользователи?
- Где больше всего пользователей теряется?
- Какая конверсия в покупку?
- Покажи общую статистику"""

ERROR_MESSAGE = "Извините, произошла ошибка. Пожалуйста, попробуйте еще раз."
