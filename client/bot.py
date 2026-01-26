"""Telegram bot handler for EasyPomodoro project consultant."""

import asyncio
import json
import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, NetworkError

from config import TELEGRAM_BOT_TOKEN, WELCOME_MESSAGE, ERROR_MESSAGE
from backend_client import BackendClient

logger = logging.getLogger(__name__)


async def retry_telegram_call(func, *args, max_retries=3, **kwargs):
    """Retry Telegram API calls with exponential backoff on network errors."""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except (TimedOut, NetworkError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Telegram API call failed after {max_retries} attempts: {e}")
                raise

            wait_time = 2 ** attempt
            logger.warning(f"Telegram API timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)


class TelegramBot:
    """Telegram bot for EasyPomodoro project consultation."""

    def __init__(self):
        self.backend_client = BackendClient()
        self.application: Optional[Application] = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user_id = update.effective_user.id
        logger.info(f"User {user_id}: /start command")
        await retry_telegram_call(update.message.reply_text, WELCOME_MESSAGE)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile command - show current user profile."""
        user_id = str(update.effective_user.id)
        logger.info(f"User {user_id}: /profile command")

        try:
            profile = await self.backend_client.get_profile(user_id)

            if not profile:
                message = (
                    "❌ Профиль не найден.\n\n"
                    "Создайте профиль командой /edit_profile\n"
                    "Или посмотрите пример: /profile_example"
                )
                await retry_telegram_call(update.message.reply_text, message)
                return

            # Format profile for display (plain text, no Markdown to avoid conflicts)
            msg_parts = [f"👤 {profile.get('name', 'Пользователь')}", "━━━━━━━━━━━━━━━━━━━━"]

            # Basic info
            msg_parts.append(f"🌍 Язык: {profile.get('language', 'не указан')}")
            msg_parts.append(f"⏰ Timezone: {profile.get('timezone', 'не указан')}")

            # Personal info
            personal = profile.get('personal_info', {})
            if personal:
                msg_parts.append("\n💼 Личная информация:")
                if 'role' in personal:
                    msg_parts.append(f"• Роль: {personal['role']}")
                if 'experience_years' in personal:
                    msg_parts.append(f"• Опыт: {personal['experience_years']} лет")

            # Development preferences
            dev = profile.get('development_preferences', {})
            if dev:
                msg_parts.append("\n🛠 Разработка:")
                if 'primary_language' in dev:
                    msg_parts.append(f"• Основной язык: {dev['primary_language']}")
                if 'architecture_style' in dev:
                    msg_parts.append(f"• Архитектура: {dev['architecture_style']}")
                if 'preferred_libraries' in dev and dev['preferred_libraries']:
                    libs = ', '.join(dev['preferred_libraries'][:3])
                    msg_parts.append(f"• Библиотеки: {libs}")

            # AI preferences
            ai = profile.get('ai_assistant_preferences', {})
            if ai:
                msg_parts.append("\n⚙️ Настройки AI:")
                style_map = {
                    "brief": "Краткий",
                    "step_by_step": "Пошаговый",
                    "detailed": "Подробный",
                    "concise": "Сжатый",
                    "balanced": "Сбалансированный"
                }
                if 'explain_code' in ai:
                    msg_parts.append(f"• Объяснение кода: {style_map.get(ai['explain_code'], ai['explain_code'])}")
                if 'code_comments' in ai:
                    msg_parts.append(f"• Комментарии: {ai['code_comments']}")

            msg_parts.append("\n━━━━━━━━━━━━━━━━━━━━")
            msg_parts.append("Редактировать: /edit_profile")

            await retry_telegram_call(
                update.message.reply_text,
                "\n".join(msg_parts)
            )

        except Exception as e:
            logger.error(f"User {user_id}: Profile command error: {e}", exc_info=True)
            await retry_telegram_call(update.message.reply_text, "❌ Ошибка при получении профиля")

    async def edit_profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /edit_profile command - instructions for editing profile."""
        user_id = str(update.effective_user.id)
        logger.info(f"User {user_id}: /edit_profile command")

        message = """📝 *Редактирование профиля*

Для обновления профиля отправьте JSON в следующем формате:

```json
{
  "name": "Ваше имя",
  "language": "ru",
  "timezone": "Europe/Moscow",
  "development_preferences": {
    "primary_language": "Kotlin",
    "architecture_style": "Clean Architecture"
  }
}
```

Можно обновлять только нужные поля.

Команды:
• /profile - Текущий профиль
• /profile_example - Полный пример
• /delete_profile - Удалить профиль

Просто отправьте JSON боту, и он обновит ваш профиль."""

        await retry_telegram_call(
            update.message.reply_text,
            message,
            parse_mode="Markdown"
        )

    async def profile_example_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile_example command - send example profile."""
        user_id = str(update.effective_user.id)
        logger.info(f"User {user_id}: /profile_example command")

        # Read example from server/data/profile_example.json (hardcoded here)
        example = """{
  "name": "Александр",
  "language": "ru",
  "timezone": "Europe/Moscow",

  "personal_info": {
    "role": "Senior Android Developer",
    "experience_years": 8
  },

  "communication_preferences": {
    "response_style": "concise",
    "tone": "professional",
    "use_emojis": false
  },

  "development_preferences": {
    "primary_language": "Kotlin",
    "secondary_languages": ["Python", "Java"],
    "architecture_style": "Clean Architecture + MVI",
    "code_style": "idiomatic_kotlin",
    "preferred_libraries": ["Jetpack Compose", "Coroutines", "Room"]
  },

  "ai_assistant_preferences": {
    "explain_code": "step_by_step",
    "code_comments": "minimal",
    "suggest_alternatives": true
  }
}"""

        message = "📋 *Пример профиля:*\n\nСкопируйте и заполните своими данными, затем отправьте боту."

        await retry_telegram_call(update.message.reply_text, message, parse_mode="Markdown")
        await retry_telegram_call(update.message.reply_text, f"```json\n{example}\n```", parse_mode="Markdown")

    async def delete_profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /delete_profile command - delete user profile."""
        user_id = str(update.effective_user.id)
        logger.info(f"User {user_id}: /delete_profile command")

        try:
            success = await self.backend_client.delete_profile(user_id)

            if success:
                message = "✅ Профиль успешно удален."
            else:
                message = "❌ Профиль не найден."

            await retry_telegram_call(update.message.reply_text, message)

        except Exception as e:
            logger.error(f"User {user_id}: Delete profile error: {e}", exc_info=True)
            await retry_telegram_call(update.message.reply_text, "❌ Ошибка при удалении профиля")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user messages."""
        user_id = update.effective_user.id
        user_message = update.message.text

        logger.info(f"User {user_id}: Received message: {user_message}")

        # Check if message is JSON (profile update)
        if user_message.strip().startswith('{'):
            await self._handle_profile_update(update, user_id, user_message)
            return

        thinking_msg = None

        try:
            # Show thinking indicator
            thinking_msg = await retry_telegram_call(update.message.reply_text, "Думаю...")

            # Send message to backend
            response_text, mcp_used = await self.backend_client.send_message(
                user_id=str(user_id),
                message=user_message
            )

            # Delete thinking message
            await retry_telegram_call(thinking_msg.delete)
            thinking_msg = None

            # Send response
            if response_text:
                await retry_telegram_call(update.message.reply_text, response_text)
            else:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)

        except Exception as e:
            logger.error(f"User {user_id}: Error handling message: {e}", exc_info=True)
            if thinking_msg:
                try:
                    await retry_telegram_call(thinking_msg.delete)
                except Exception:
                    pass
            try:
                await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)
            except Exception:
                logger.error(f"User {user_id}: Failed to send error message")

    async def _handle_profile_update(self, update: Update, user_id: int, message: str) -> None:
        """Handle profile update from JSON message."""
        try:
            profile_data = json.loads(message)
            logger.info(f"User {user_id}: Updating profile with JSON")

            success = await self.backend_client.update_profile(str(user_id), profile_data)

            if success:
                msg = "✅ Профиль успешно обновлен!\n\nПосмотреть: /profile"
            else:
                msg = "❌ Ошибка при обновлении профиля. Проверьте формат JSON."

            await retry_telegram_call(update.message.reply_text, msg)

        except json.JSONDecodeError as e:
            logger.error(f"User {user_id}: Invalid JSON: {e}")
            await retry_telegram_call(
                update.message.reply_text,
                "❌ Неверный формат JSON. Проверьте синтаксис.\n\nПример: /profile_example"
            )
        except Exception as e:
            logger.error(f"User {user_id}: Profile update error: {e}", exc_info=True)
            await retry_telegram_call(update.message.reply_text, "❌ Ошибка при обновлении профиля")

    async def run(self) -> None:
        """Run the Telegram bot."""
        from telegram.request import HTTPXRequest

        request = HTTPXRequest(connection_pool_size=8, connect_timeout=30.0, read_timeout=30.0)
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()

        # Register command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CommandHandler("edit_profile", self.edit_profile_command))
        self.application.add_handler(CommandHandler("profile_example", self.profile_example_command))
        self.application.add_handler(CommandHandler("delete_profile", self.delete_profile_command))

        # Register message handler (must be last)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Starting Telegram bot")
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            logger.info("Telegram bot is running")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        # Close backend client
        await self.backend_client.close()

        if self.application:
            logger.info("Stopping Telegram bot")
            try:
                if self.application.updater and self.application.updater.running:
                    await self.application.updater.stop()
            except Exception as e:
                logger.warning(f"Error stopping updater: {e}")

            try:
                await self.application.stop()
            except Exception as e:
                logger.warning(f"Error stopping application: {e}")

            try:
                await self.application.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down application: {e}")

            logger.info("Telegram bot stopped")
