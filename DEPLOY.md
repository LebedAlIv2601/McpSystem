# Инструкция по деплою Backend на Railway

## Обзор

Данная инструкция описывает развёртывание MCP Backend сервиса на платформе [Railway](https://railway.app).

## Структура проекта после рефакторинга

```
McpSystem/
├── server/                    # Backend сервис (деплоится на Railway)
│   ├── main.py               # FastAPI entry point
│   ├── app.py                # API роутер
│   ├── auth.py               # API key аутентификация
│   ├── config.py             # Конфигурация
│   ├── chat_service.py       # Логика обработки чата
│   ├── mcp_manager.py        # MCP подключения
│   ├── mcp_http_transport.py # HTTP транспорт для GitHub Copilot MCP
│   ├── openrouter_client.py  # OpenRouter API клиент
│   ├── conversation.py       # Управление историей
│   ├── mcp_rag/              # RAG MCP сервер
│   │   ├── server.py
│   │   ├── rag_engine.py     # FAISS + OpenRouter embeddings
│   │   └── github_fetcher.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
└── client/                   # Telegram бот (запускается отдельно)
    ├── main.py
    ├── bot.py
    ├── backend_client.py     # HTTP клиент для backend
    ├── config.py
    ├── logger.py
    ├── requirements.txt
    └── .env.example
```

---

## Деплой на Railway

### Шаг 1: Подготовка репозитория

1. Убедитесь, что все изменения закоммичены:
```bash
git add .
git commit -m "Refactor: separate backend and client"
git push origin master
```

### Шаг 2: Создание проекта в Railway

1. Зайдите на [railway.app](https://railway.app) и авторизуйтесь через GitHub
2. Нажмите **"New Project"**
3. Выберите **"Deploy from GitHub repo"**
4. Выберите ваш репозиторий `McpSystem`

### Шаг 3: Настройка сервиса

Railway автоматически определит, что это Python проект. Необходимо настроить:

1. **Перейдите в Settings сервиса**

2. **Укажите Root Directory:**
   ```
   server
   ```

3. **Build Command** (оставьте пустым или):
   ```
   pip install -r requirements.txt
   ```

4. **Start Command:**
   ```
   python main.py
   ```

### Шаг 4: Настройка переменных окружения

Перейдите в раздел **Variables** и добавьте:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `BACKEND_API_KEY` | Секретный ключ для API | `my-super-secret-key-12345` |
| `OPENROUTER_API_KEY` | API ключ OpenRouter | `sk-or-v1-...` |
| `GITHUB_TOKEN` | GitHub Personal Access Token | `ghp_...` |
| `GITHUB_OWNER` | Владелец репозитория | `LebedAlIv2601` |
| `GITHUB_REPO` | Название репозитория | `EasyPomodoro` |
| `SPECS_PATH` | Путь к документации | `specs` |
| `PORT` | Порт (Railway задаёт автоматически) | `8000` |

**Важно:** `BACKEND_API_KEY` — это ваш секретный ключ, который будет использоваться для аутентификации запросов от Telegram бота. Сгенерируйте надёжный ключ:
```bash
openssl rand -hex 32
```

### Шаг 5: Деплой

1. Railway автоматически начнёт деплой после настройки
2. Дождитесь завершения билда (обычно 2-3 минуты)
3. Скопируйте URL сервиса из раздела **Deployments**

URL будет выглядеть примерно так:
```
https://your-project-name.up.railway.app
```

### Шаг 6: Проверка работоспособности

```bash
# Health check
curl https://your-project-name.up.railway.app/health

# Ожидаемый ответ:
# {"status":"healthy","mcp_connected":true,"tools_count":11}
```

---

## Настройка Telegram бота (клиент)

### Шаг 1: Настройка окружения клиента

1. Перейдите в директорию `client/`:
```bash
cd client
```

2. Создайте `.env` файл:
```bash
cp .env.example .env
```

3. Заполните `.env`:
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Backend API Configuration
BACKEND_URL=https://your-project-name.up.railway.app
BACKEND_API_KEY=my-super-secret-key-12345
```

**Важно:** `BACKEND_API_KEY` должен совпадать с тем, что указан в Railway!

### Шаг 2: Установка зависимостей

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Шаг 3: Запуск бота

```bash
python main.py
```

---

## API Endpoints

### POST /api/chat

Отправка сообщения и получение ответа от AI.

**Headers:**
```
X-API-Key: your-backend-api-key
Content-Type: application/json
```

**Request:**
```json
{
    "user_id": "123456",
    "message": "What is the project architecture?"
}
```

**Response:**
```json
{
    "response": "The EasyPomodoro project...",
    "tool_calls_count": 2,
    "mcp_used": true
}
```

### GET /health

Проверка состояния сервиса.

**Response:**
```json
{
    "status": "healthy",
    "mcp_connected": true,
    "tools_count": 11
}
```

---

## Troubleshooting

### Ошибка "Cannot connect to backend"
- Проверьте, что `BACKEND_URL` указан правильно
- Убедитесь, что сервис Railway запущен
- Проверьте логи в Railway Dashboard

### Ошибка "Invalid API key"
- Убедитесь, что `BACKEND_API_KEY` одинаковый на сервере и клиенте
- Проверьте, что нет лишних пробелов в переменных

### MCP не подключается
- Проверьте `GITHUB_TOKEN` — он должен иметь права на чтение репозитория
- Проверьте логи в Railway для деталей ошибки

### RAG не работает
- Проверьте `OPENROUTER_API_KEY`
- Убедитесь, что у вас есть доступ к модели `google/gemini-embedding-001`

---

## Мониторинг

### Railway Dashboard

1. Перейдите в ваш проект на Railway
2. Откройте раздел **Deployments** для просмотра логов
3. Используйте **Metrics** для мониторинга ресурсов

### Логи

Логи доступны в Railway Dashboard в реальном времени. Для поиска ошибок используйте фильтр по уровню `ERROR`.

---

## Обновление

Для обновления сервиса:

1. Внесите изменения в код
2. Закоммитьте и запушьте:
```bash
git add .
git commit -m "Update: description"
git push origin master
```
3. Railway автоматически задеплоит новую версию

---

## Стоимость

Railway предоставляет:
- **Hobby Plan**: $5/месяц с $5 кредитами
- **Free Tier**: $5 кредитов в месяц (достаточно для тестирования)

Примерное потребление этого сервиса:
- ~0.5 GB RAM
- Минимальное CPU
- ~$2-3/месяц при активном использовании

---

## Безопасность

1. **Никогда не коммитьте `.env` файлы**
2. **Используйте сильные API ключи** (минимум 32 символа)
3. **Ограничьте доступ к Railway проекту**
4. **Регулярно ротируйте API ключи**

---

## Альтернативные платформы

Если Railway не подходит, можно использовать:

- **Render.com** — аналогичный процесс, бесплатный tier
- **Fly.io** — требует настройки fly.toml
- **DigitalOcean App Platform** — более enterprise решение
- **Heroku** — классический вариант (теперь платный)
