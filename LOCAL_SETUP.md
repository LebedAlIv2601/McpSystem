# Локальный запуск сервера

Инструкция для запуска MCP Backend сервера локально на вашей машине.

## Зачем запускать локально?

- **Отладка и тестирование** - моментальная проверка изменений без деплоя
- **Разработка новых функций** - безопасная среда для экспериментов
- **Обход проблем Railway** - когда облачный деплой не работает
- **Работа без интернета** - разработка offline (кроме API запросов)
- **Экономия** - не расходуете кредиты Railway при разработке

## Требования

- **Python 3.12+** (рекомендуется 3.14)
- **ffmpeg** (для обработки голосовых сообщений)
- **Homebrew** (для установки ffmpeg на macOS)

## Установка зависимостей

### 1. Установить ffmpeg (если еще не установлен)

```bash
# macOS
brew install ffmpeg

# Проверить установку
ffmpeg -version
```

### 2. Установить Python пакеты

```bash
cd /Users/aleksandrlebed/PycharmProjects/McpSystem

# Создать виртуальное окружение (если еще нет)
python3 -m venv venv

# Активировать
source venv/bin/activate

# Установить зависимости
cd server
pip install -r requirements.txt
```

## Настройка переменных окружения

### 1. Проверить `.env` файл

```bash
cd server
cat .env
```

**Обязательные переменные:**
- `BACKEND_API_KEY` - API ключ для аутентификации
- `OPENROUTER_API_KEY` - ключ от OpenRouter
- `GITHUB_TOKEN` - GitHub Personal Access Token

### 2. Синхронизировать ключи с клиентом

```bash
# Проверить что ключи совпадают
grep BACKEND_API_KEY server/.env
grep BACKEND_API_KEY client/.env

# Если не совпадают - обновить client/.env
```

### 3. Настроить клиент на локальный сервер

```bash
# Открыть client/.env
nano client/.env

# Установить:
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=<тот же ключ что в server/.env>
```

## Запуск сервера

### Терминал 1: Backend Server

```bash
cd /Users/aleksandrlebed/PycharmProjects/McpSystem/server
source ../venv/bin/activate
python main.py
```

**Ожидаемый вывод:**
```
2026-01-28 00:00:00 - INFO - === MCP Backend Server Starting ===
2026-01-28 00:00:01 - INFO - MCP servers connected successfully
2026-01-28 00:00:01 - INFO - Audio service initialized successfully
2026-01-28 00:00:01 - INFO - === MCP Backend Server Ready ===
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Терминал 2: Telegram Bot Client

```bash
cd /Users/aleksandrlebed/PycharmProjects/McpSystem/client
source ../venv/bin/activate
python main.py
```

**Ожидаемый вывод:**
```
2026-01-28 00:00:00 - INFO - Starting Telegram bot client...
2026-01-28 00:00:00 - INFO - Backend URL: http://localhost:8000
2026-01-28 00:00:01 - INFO - Bot started successfully
```

## Проверка работоспособности

### 1. Health Check

```bash
curl http://localhost:8000/health | jq .
```

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "mcp_connected": true,
  "tools_count": 11
}
```

### 2. Тест Chat API

```bash
curl -X POST 'http://localhost:8000/api/chat' \
  -H 'X-API-Key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test","message":"ping"}'
```

### 3. Тест через Telegram

Отправьте текстовое или голосовое сообщение боту - должен прийти ответ.

## Остановка сервера

### Мягкая остановка (CTRL+C в терминале)

```bash
# В терминале где запущен main.py
CTRL+C
```

### Жесткая остановка (если завис)

```bash
# Найти процесс на порту 8000
lsof -ti:8000

# Убить процесс
lsof -ti:8000 | xargs kill -9

# Или по имени
pkill -f "python main.py"
```

## Перезапуск сервера (после изменений в коде)

```bash
# 1. Остановить
lsof -ti:8000 | xargs kill -9

# 2. Подождать 2 секунды
sleep 2

# 3. Запустить снова
cd /Users/aleksandrlebed/PycharmProjects/McpSystem/server
source ../venv/bin/activate
python main.py
```

## Логи и отладка

### Просмотр логов сервера

Логи выводятся в stdout где запущен `main.py`.

### Уровень детализации

По умолчанию: `INFO`

Для более подробных логов измените в `main.py`:
```python
setup_logging(level=logging.DEBUG)
```

### Проверка ошибок

```bash
# В терминале сервера ищите строки с ERROR:
# 2026-01-28 00:00:00 - ERROR - ...
```

## Частые проблемы

### Порт 8000 занят

**Ошибка:** `[Errno 48] address already in use`

**Решение:**
```bash
lsof -ti:8000 | xargs kill -9
```

### ffmpeg не найден

**Ошибка:** `No such file or directory: 'ffmpeg'`

**Решение:**
```bash
brew install ffmpeg
```

### Invalid API key

**Ошибка:** `{"detail":"Invalid API key"}`

**Причина:** Ключи в `server/.env` и `client/.env` не совпадают

**Решение:**
```bash
# Скопировать ключ из server в client
grep BACKEND_API_KEY server/.env
# Обновить client/.env с этим ключом
```

### MCP connection timeout

**Ошибка:** `MCP connection timeout after 30s`

**Причина:** GitHub token невалидный или нет интернета

**Решение:**
- Проверить `GITHUB_TOKEN` в `.env`
- Проверить интернет соединение
- Сервер продолжит работу без MCP tools

### OpenRouter API error

**Ошибка:** `404 Not Found` или `500 Internal Server Error`

**Причина:**
- Неправильный формат запроса
- Модель не поддерживает указанную функцию
- Закончились кредиты на OpenRouter

**Решение:**
- Проверить баланс на openrouter.ai
- Проверить что модель поддерживает нужную функцию
- Посмотреть подробности в логах сервера

## Переключение между локальным и удаленным сервером

### На локальный сервер

```bash
# Изменить client/.env
BACKEND_URL=http://localhost:8000
```

### На удаленный сервер (Railway)

```bash
# Изменить client/.env
BACKEND_URL=https://your-app.railway.app
```

**Перезапустить бота после изменения!**

## Разработка новых функций

1. **Остановить сервер** (CTRL+C)
2. **Внести изменения** в код
3. **Перезапустить сервер**
4. **Протестировать** через Telegram или curl
5. **Проверить логи** на ошибки
6. **Закоммитить** изменения

## Деплой на Railway после локальной разработки

```bash
# 1. Убедиться что все работает локально
# 2. Закоммитить изменения
git add .
git commit -m "описание изменений"

# 3. Запушить (Railway автоматически задеплоит)
git push origin master
```

## Полезные команды

```bash
# Проверить запущен ли сервер
curl -s http://localhost:8000/health

# Посмотреть процессы на порту 8000
lsof -i:8000

# Посмотреть все Python процессы
ps aux | grep python

# Проверить версию ffmpeg
ffmpeg -version

# Проверить версию Python
python --version

# Посмотреть установленные пакеты
pip list | grep -E "fastapi|mcp|httpx"
```

## Backup конфигурации

Перед изменениями сделайте копию `.env` файлов:

```bash
cp server/.env server/.env.backup
cp client/.env client/.env.backup
```

## Следующие шаги

После успешного локального запуска:
1. Протестируйте все эндпоинты
2. Проверьте voice input функцию
3. Убедитесь что MCP tools работают
4. При необходимости настройте профиль пользователя

---

**Документация:** См. README.md и CLAUDE.md для полной информации о проекте.
