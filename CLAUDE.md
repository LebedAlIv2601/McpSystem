# EasyPomodoro Support System

AI-powered support system for the EasyPomodoro Android app using MCP (Model Context Protocol) servers.

## Project Overview

This system provides:
1. **Telegram Bot** - Interactive support chat for users
2. **REST API** - Backend with MCP integration for AI-powered responses
3. **Ticket Management** - Automatic ticket creation and tracking
4. **FAQ Search** - RAG-based search through documentation and FAQ

## Architecture

```
┌─────────────────┐
│ Telegram User   │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot Client                       │
│                      (client/)                               │
│  - Handles /start command                                    │
│  - Forwards messages to backend with user_id + user_name     │
│  - Shows "Думаю..." indicator                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Backend Server (server/)                  │
│                      FastAPI + MCP                           │
│                                                              │
│  Endpoints:                                                  │
│  ├─ POST /api/chat      - Support chat with ticket mgmt     │
│  ├─ POST /api/review-pr - AI code review for PRs            │
│  └─ GET  /health        - Health check                       │
│                                                              │
│  Components:                                                 │
│  ├─ chat_service.py     - Message processing + tool loops   │
│  ├─ mcp_manager.py      - MCP server connections            │
│  ├─ openrouter_client.py - LLM API integration              │
│  └─ prompts.py          - System prompts                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ↓                               ↓
┌──────────────────────┐    ┌──────────────────────┐
│ Support Tickets MCP  │    │ RAG Specs MCP        │
│ (Python/stdio)       │    │ (Python/stdio)       │
│                      │    │                      │
│ Tools:               │    │ Tools:               │
│ - get_user_tickets   │    │ - rag_query          │
│ - create_ticket      │    │ - list_specs         │
│ - update_ticket_     │    │ - get_spec_content   │
│   status             │    │ - rebuild_index      │
│ - update_ticket_     │    │                      │
│   description        │    │ Uses:                │
│                      │    │ - GitHub API         │
│ Storage:             │    │ - OpenRouter         │
│ - JSON file DB       │    │   Embeddings         │
└──────────────────────┘    └──────────────────────┘
```

## Ticket Management Logic

The AI agent automatically manages support tickets:

1. **First message**: Check user's tickets via `get_user_tickets`
2. **No open tickets + new issue**: Create ticket with status `open`
3. **After first response**:
   - User confirms resolved → `update_ticket_status(closed)`
   - User continues conversation → `update_ticket_status(in_progress)` + `update_ticket_description`
4. **New ticket**: Only created if previous ticket is `closed`

**Ticket statuses:** `open` → `in_progress` → `closed`

## API Endpoints

### POST /api/chat

Support chat endpoint with ticket management.

**Request:**
```json
{
  "user_id": "string",
  "user_name": "string",
  "message": "string"
}
```

**Response:**
```json
{
  "response": "string",
  "tool_calls_count": 0,
  "mcp_used": false
}
```

### POST /api/review-pr

AI-powered code review for pull requests.

**Request:**
```json
{
  "pr_number": 123
}
```

**Response:**
```json
{
  "review": "## Summary\n...",
  "tool_calls_count": 5
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "mcp_connected": true,
  "tools_count": 7
}
```

## System Components

### 1. Backend Server (server/)

**Files:**
- `main.py` - FastAPI application entry point
- `app.py` - API routes and endpoints
- `chat_service.py` - Message processing with MCP tool integration
- `mcp_manager.py` - MCP server connection management
- `openrouter_client.py` - OpenRouter LLM API integration
- `prompts.py` - System prompts for different tasks
- `schemas.py` - Pydantic models for API
- `conversation.py` - Per-user conversation history
- `auth.py` - API key authentication
- `config.py` - Configuration and environment variables
- `logger.py` - Logging configuration

### 2. Telegram Bot Client (client/)

**Files:**
- `main.py` - Application entry point
- `bot.py` - Telegram bot handlers
- `backend_client.py` - HTTP client for backend API
- `config.py` - Bot configuration
- `logger.py` - Logging configuration

### 3. Support Tickets MCP Server (server/mcp_support/)

**Files:**
- `server.py` - MCP server with ticket management tools
- `database.py` - JSON file-based database for users and tickets

**Tools:**
- `get_user_tickets` - Get all tickets for a user
- `create_ticket` - Create new support ticket
- `update_ticket_status` - Update ticket status (open/in_progress/closed)
- `update_ticket_description` - Update ticket description with conversation progress

**Storage:** `server/data/support_db.json`

### 4. RAG MCP Server (server/mcp_rag/)

**Files:**
- `server.py` - MCP server with RAG tools
- `github_fetcher.py` - GitHub API client for /specs folder
- `rag_engine.py` - Vector search with OpenRouter embeddings

**Tools:**
- `rag_query` - Search documentation/FAQ with semantic similarity
- `list_specs` - List available specification files
- `get_spec_content` - Get full content of a spec file
- `rebuild_index` - Rebuild the RAG index

**Target Repository:** `LebedAlIv2601/EasyPomodoro`

### 5. GitHub Copilot MCP (Disabled)

GitHub Copilot MCP is available but currently disabled for the support system.
Can be re-enabled in `server/config.py` if needed.

## Installation

### Prerequisites
- Python 3.11+
- OpenRouter API key
- GitHub Personal Access Token (for RAG)
- Telegram bot token (for client)

### Server Setup

1. **Clone repository:**
```bash
git clone <repo-url>
cd McpSystem
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cd server
cp .env.example .env
# Edit .env:
# BACKEND_API_KEY=your_secure_api_key
# OPENROUTER_API_KEY=your_openrouter_key
# GITHUB_TOKEN=your_github_pat
```

5. **Run server:**
```bash
python main.py
```

### Client Setup

1. **Configure environment:**
```bash
cd client
cp .env.example .env
# Edit .env:
# TELEGRAM_BOT_TOKEN=your_bot_token
# BACKEND_URL=http://localhost:8000
# BACKEND_API_KEY=same_as_server
```

2. **Run client:**
```bash
python main.py
```

## Configuration

### Server Environment Variables

| Variable | Description |
|----------|-------------|
| `BACKEND_API_KEY` | API key for authentication |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `GITHUB_TOKEN` | GitHub Personal Access Token |
| `OPENROUTER_MODEL` | LLM model (default: `deepseek/deepseek-v3.2`) |
| `PORT` | Server port (default: `8000`) |
| `HOST` | Server host (default: `0.0.0.0`) |

### Client Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `BACKEND_URL` | Backend server URL |
| `BACKEND_API_KEY` | API key for backend |

## Technology Stack

- **Python 3.11+** - Main language
- **FastAPI** - Backend API framework
- **python-telegram-bot** - Telegram integration
- **MCP SDK** - Model Context Protocol (stdio transport)
- **httpx** - Async HTTP client
- **OpenRouter** - LLM API access
- **Pydantic** - Data validation
- **FAISS** - Vector similarity search

## Deployment

### Railway

The server is designed for Railway deployment:

1. Connect repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push

### Manual Testing

```bash
# Health check
curl https://your-server.railway.app/health

# Chat (support)
curl -X POST "https://your-server.railway.app/api/chat" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "123", "user_name": "John", "message": "How to configure timer?"}'
```

## Troubleshooting

### Empty responses
- Check logs for tool call errors
- Model may output XML artifacts - these are filtered automatically
- If response is still empty, check `_clean_tool_call_artifacts` function

### Ticket not created
- Verify MCP support server is connected (check logs)
- Check if user already has an open ticket

### RAG not finding answers
- Ensure specs/FAQ files exist in target repository
- Check if RAG index is built (first query triggers build)
- Verify GitHub token has read access

### High latency
- Support queries may take 10-30 seconds due to multiple tool calls
- Check OpenRouter rate limits

## License

This project demonstrates MCP integration for AI-powered support systems.
