# Спецификация: Ассистент по проекту с интеграцией Weeek

## Обзор

Трансформация серверного агента в полноценного ассистента по проекту EasyPomodoro с функциями управления задачами через Weeek API.

## Цели

1. Создать MCP-сервер для Weeek API (mcp_weeek)
2. Интегрировать управление задачами в ассистента
3. Отключить GitHub Copilot MCP (временно)
4. Отключить `get_project_structure` в mcp_rag
5. Адаптировать Telegram-бота под новую функциональность

---

## 1. MCP Weeek Server

### 1.1 Архитектура

- **Тип**: Отдельный stdio MCP-сервер (аналогично mcp_rag)
- **Расположение**: `server/mcp_weeek/`
- **Файловая структура**:
  ```
  server/mcp_weeek/
  ├── __init__.py
  ├── server.py        # MCP server + tool handlers
  ├── weeek_client.py  # HTTP client для Weeek API
  └── config.py        # Конфигурация (можно импортировать из parent)
  ```

### 1.2 Конфигурация (Environment Variables)

| Переменная | Описание |
|------------|----------|
| `WEEEK_API_TOKEN` | Bearer токен для Weeek API (один глобальный) |
| `WEEEK_PROJECT_ID` | ID проекта в Weeek |
| `WEEEK_BOARD_ID` | ID доски в Weeek |
| `WEEEK_COLUMN_OPEN_ID` | ID колонки "Open" |
| `WEEEK_COLUMN_IN_PROGRESS_ID` | ID колонки "In Progress" |
| `WEEEK_COLUMN_DONE_ID` | ID колонки "Done" |

### 1.3 Weeek API Endpoints

Base URL: `https://api.weeek.net/public/v1`

| Операция | Метод | Endpoint |
|----------|-------|----------|
| Список задач | GET | `/tm/tasks?projectId={id}&boardId={id}` |
| Получить задачу | GET | `/tm/tasks/{taskId}` |
| Создать задачу | POST | `/tm/tasks` |
| Обновить задачу | PUT | `/tm/tasks/{taskId}` |

### 1.4 MCP Tools

#### `list_tasks`
Получение списка задач с доски.

```json
{
  "name": "list_tasks",
  "description": "Получить список задач из Weeek. Возвращает все задачи с текущей доски проекта.",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

**Возвращает**: Массив задач с полями: id, title, description, priority, boardColumnId (статус).

#### `get_task_details`
Получение подробностей конкретной задачи.

```json
{
  "name": "get_task_details",
  "description": "Получить детальную информацию о задаче по её ID или точному названию.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "task_id": {
        "type": "integer",
        "description": "ID задачи в Weeek"
      },
      "title": {
        "type": "string",
        "description": "Точное название задачи (альтернатива task_id)"
      }
    },
    "required": []
  }
}
```

#### `create_task`
Создание новой задачи.

```json
{
  "name": "create_task",
  "description": "Создать новую задачу в Weeek. Задача создаётся в статусе Open.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "title": {
        "type": "string",
        "description": "Название задачи"
      },
      "description": {
        "type": "string",
        "description": "Описание задачи"
      },
      "priority": {
        "type": "integer",
        "description": "Приоритет: 0=Low, 1=Medium, 2=High. По умолчанию AI выбирает на основе контекста.",
        "enum": [0, 1, 2]
      }
    },
    "required": ["title"]
  }
}
```

**Логика приоритета**: AI самостоятельно определяет приоритет на основе контекста задачи. Hold (3) не используется.

#### `move_task`
Перемещение задачи между статусами.

```json
{
  "name": "move_task",
  "description": "Переместить задачу в другой статус (Open, In Progress, Done).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "task_id": {
        "type": "integer",
        "description": "ID задачи"
      },
      "title": {
        "type": "string",
        "description": "Точное название задачи (альтернатива task_id)"
      },
      "status": {
        "type": "string",
        "description": "Новый статус задачи",
        "enum": ["Open", "In Progress", "Done"]
      }
    },
    "required": ["status"]
  }
}
```

**Идентификация задачи**: Требуется точное совпадение названия или task_id.

---

## 2. Изменения в Backend Server

### 2.1 config.py

**Добавить переменные**:
```python
# Weeek Configuration
WEEEK_API_TOKEN = os.getenv("WEEEK_API_TOKEN", "")
WEEEK_PROJECT_ID = int(os.getenv("WEEEK_PROJECT_ID", "0"))
WEEEK_BOARD_ID = int(os.getenv("WEEEK_BOARD_ID", "0"))
WEEEK_COLUMN_OPEN_ID = int(os.getenv("WEEEK_COLUMN_OPEN_ID", "0"))
WEEEK_COLUMN_IN_PROGRESS_ID = int(os.getenv("WEEEK_COLUMN_IN_PROGRESS_ID", "0"))
WEEEK_COLUMN_DONE_ID = int(os.getenv("WEEEK_COLUMN_DONE_ID", "0"))
```

**MCP_SERVERS**:
- Удалить вызов `github_copilot` из списка (код оставить)
- Добавить `mcp_weeek` как stdio-сервер

**ESSENTIAL_TOOLS**:
- Удалить `get_project_structure` из списка (код в mcp_rag оставить)
- Удалить все GitHub Copilot tools: `get_file_contents`, `list_commits`, `get_commit`, `list_issues`, `issue_read`, `list_pull_requests`, `pull_request_read`
- Добавить Weeek tools: `list_tasks`, `get_task_details`, `create_task`, `move_task`
- Оставить RAG tools: `rag_query`, `list_specs`, `get_spec_content`

**TOOL_CALL_TIMEOUT**: Оставить 120.0 секунд.

**Max iterations**: Увеличить до 20 (было 10).

### 2.2 chat_service.py

**System Prompt** (обновить в `_process_with_openrouter`):

```
Current date: {current_date}.

Ты — ассистент по проекту EasyPomodoro. Ты помогаешь отвечать на вопросы о проекте и управлять задачами в Weeek.

**КРИТИЧЕСКИ ВАЖНО:**
- НИКОГДА не говори "давай я посмотрю..." или "сейчас проверю..." — просто ВЫЗЫВАЙ инструмент
- Если нужна информация — ВЫЗОВИ инструмент. НЕ описывай намерение.
- НЕ отвечай пока не соберёшь ВСЮ необходимую информацию

**ИНСТРУМЕНТЫ:**
1. **rag_query** — поиск по документации проекта
2. **list_specs** — список документов проекта
3. **get_spec_content** — получить содержимое документа
4. **list_tasks** — список задач из Weeek
5. **get_task_details** — детали задачи
6. **create_task** — создать задачу (title, description, priority)
7. **move_task** — переместить задачу (Open → In Progress → Done)

**WORKFLOW:**
- Вопросы о проекте → rag_query
- Управление задачами → list_tasks, create_task, move_task
- Рекомендация задачи → list_tasks + rag_query (анализ контекста)

**РЕКОМЕНДАЦИИ ЗАДАЧ:**
Давай рекомендации ТОЛЬКО по запросу пользователя. При рекомендации учитывай:
- Приоритеты задач в Weeek (High > Medium > Low)
- Контекст проекта из документации

**ПРИОРИТЕТЫ (при создании задачи):**
Определяй приоритет самостоятельно на основе контекста:
- 2 (High) — критичные баги, срочные фичи
- 1 (Medium) — стандартные задачи
- 0 (Low) — улучшения, рефакторинг

**СОЗДАНИЕ ЗАДАЧ:**
- Спрашивай подтверждение ТОЛЬКО если недостаточно данных
- После создания показывай: название, приоритет, статус

**ПЕРЕМЕЩЕНИЕ ЗАДАЧ:**
- Требуется точное название задачи или ID
- Статусы: Open, In Progress, Done

Отвечай на русском языке.
```

**max_iterations**: Изменить с 10 на 20.

### 2.3 Обработка ошибок Weeek API

- **Показывать полные детали ошибок** пользователю (HTTP-коды, сообщения API)
- **Без ретрая** — одна попытка, при ошибке сразу сообщать
- **Без валидации** перед move_task — возвращать ошибку API как есть
- **Без кэширования** — всегда свежие данные из Weeek

---

## 3. Изменения в mcp_rag/server.py

**Отключить `get_project_structure`**:
- Удалить из `list_tools()` (закомментировать или убрать из return)
- Оставить функцию `handle_get_project_structure` для возможного включения

---

## 4. Изменения в Telegram Bot (client/)

### 4.1 config.py

**WELCOME_MESSAGE** (обновить):

```python
WELCOME_MESSAGE = """Привет! Я ассистент по проекту EasyPomodoro.

Я могу:
- Отвечать на вопросы о проекте и архитектуре
- Создавать задачи в Weeek
- Показывать список задач и их статус
- Перемещать задачи по доске (Open → In Progress → Done)
- Рекомендовать, какую задачу взять в работу

Примеры:
- Как устроена архитектура приложения?
- Покажи список задач
- Создай задачу "Добавить тёмную тему"
- Переведи задачу "Исправить баг X" в Done
- Какую задачу мне взять?"""
```

### 4.2 bot.py

- Без изменений в коде обработки (текстовый диалог)
- Команды Telegram: только /start (естественный язык для всего остального)

---

## 5. Структура ответов ассистента

### При создании задачи:
```
✓ Задача создана

Название: {title}
Описание: {description}
Приоритет: {High/Medium/Low}
Статус: Open
```

### При перемещении задачи:
```
✓ Задача перемещена

"{title}" теперь в статусе {новый_статус}
```

### При показе списка задач:
```
Задачи в Weeek:

Open:
• {title} (High)
• {title} (Medium)

In Progress:
• {title} (Low)

Done:
• {title}
```

### При рекомендации задачи:
```
Рекомендую взять: "{title}"

Причина: {обоснование на основе приоритета и контекста проекта}
```

---

## 6. Технические детали

### Weeek API Request Format

**Create Task**:
```json
POST /tm/tasks
{
  "title": "string",
  "description": "string | null",
  "priority": 0 | 1 | 2,
  "locations": [
    {
      "projectId": WEEEK_PROJECT_ID,
      "boardColumnId": WEEEK_COLUMN_OPEN_ID
    }
  ]
}
```

**Update Task (move)**:
```json
PUT /tm/tasks/{taskId}
{
  "boardColumnId": WEEEK_COLUMN_X_ID
}
```

**Get Tasks**:
```
GET /tm/tasks?projectId={WEEEK_PROJECT_ID}&boardId={WEEEK_BOARD_ID}
```

### Mapping статусов

| Название | boardColumnId |
|----------|---------------|
| Open | WEEEK_COLUMN_OPEN_ID |
| In Progress | WEEEK_COLUMN_IN_PROGRESS_ID |
| Done | WEEEK_COLUMN_DONE_ID |

---

## 7. Файлы для создания/изменения

### Создать:
- `server/mcp_weeek/__init__.py`
- `server/mcp_weeek/server.py`
- `server/mcp_weeek/weeek_client.py`

### Изменить:
- `server/config.py` — добавить Weeek config, изменить MCP_SERVERS и ESSENTIAL_TOOLS
- `server/chat_service.py` — обновить system prompt, max_iterations = 20
- `server/mcp_rag/server.py` — убрать get_project_structure из list_tools
- `client/config.py` — обновить WELCOME_MESSAGE

---

## 8. Не реализовывать

- Удаление задач
- Назначение исполнителей (assignee)
- Дедлайны
- Теги/метки
- Подзадачи
- Комментарии
- Фильтрация задач
- Inline-кнопки в Telegram
- Специальные команды (/tasks, /newtask)
- Кэширование
- Ретрай при ошибках
- Юнит-тесты
- Аудит-логирование

---

## 9. Критерии приёмки

1. MCP Weeek сервер запускается как stdio-процесс
2. Все 4 тула (list_tasks, get_task_details, create_task, move_task) работают
3. GitHub Copilot MCP отключен, код сохранён
4. `get_project_structure` отключен в mcp_rag, код сохранён
5. Ассистент отвечает на русском языке
6. Telegram бот показывает обновлённое приветствие
7. Ассистент может:
   - Отвечать на вопросы о проекте (через RAG)
   - Показывать список задач
   - Создавать задачи с автоматическим определением приоритета
   - Перемещать задачи между статусами
   - Рекомендовать задачу по запросу
