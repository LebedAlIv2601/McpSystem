# EasyPomodoro Project Consultant

AI-powered system for consulting on the EasyPomodoro Android project using MCP (Model Context Protocol) servers.

## Project Overview

This system provides:
1. **Telegram Bot** - Interactive chat for project questions
2. **REST API** - Backend with MCP integration for AI-powered responses
3. **PR Code Review** - Automated pull request reviews via API
4. Browse and analyze project code via GitHub Copilot MCP
5. Search project documentation using RAG (Retrieval Augmented Generation)

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│ Telegram User   │     │ GitHub Actions  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ↓                       ↓
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot Client                       │
│                      (client/)                               │
│  - Handles /start command                                    │
│  - Forwards messages to backend                              │
│  - Shows "Думаю..." indicator                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Backend Server (server/)                  │
│                      FastAPI + MCP                           │
│                                                              │
│  Endpoints:                                                  │
│  ├─ POST /api/chat      - General chat with AI              │
│  ├─ POST /api/review-pr - AI code review for PRs            │
│  └─ GET  /health        - Health check                       │
│                                                              │
│  Components:                                                 │
│  ├─ chat_service.py     - Message processing + tool loops   │
│  ├─ mcp_manager.py      - MCP server connections            │
│  ├─ openrouter_client.py - LLM API integration              │
│  └─ prompts.py          - System prompts (PR review, etc)   │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ↓                               ↓
┌──────────────────────┐    ┌──────────────────────┐
│ GitHub Copilot MCP   │    │ RAG Specs MCP        │
│ (HTTP Transport)     │    │ (Python/stdio)       │
│                      │    │                      │
│ URL:                 │    │ Tools:               │
│ api.githubcopilot.   │    │ - rag_query          │
│ com/mcp/             │    │ - list_specs         │
│                      │    │ - get_spec_content   │
│ Tools:               │    │ - rebuild_index      │
│ - get_file_contents  │    │ - get_project_       │
│ - list_commits       │    │   structure          │
│ - get_commit         │    │                      │
│ - list_issues        │    │ Uses:                │
│ - issue_read         │    │ - GitHub API         │
│ - list_pull_requests │    │ - OpenRouter         │
│ - pull_request_read  │    │   Embeddings         │
└──────────────────────┘    └──────────────────────┘
```

## API Endpoints

### POST /api/chat

General chat endpoint for project questions.

**Request:**
```json
{
  "user_id": "string",
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

**Review includes:**
- Documentation compliance check (via RAG)
- Architecture and design patterns review
- Kotlin/Android best practices
- Security analysis
- Performance considerations
- File-by-file findings with line numbers
- Verdict: APPROVE / REQUEST_CHANGES / COMMENT

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "mcp_connected": true,
  "tools_count": 11
}
```

## GitHub Actions Integration

Use the PR review endpoint in your CI/CD pipeline:

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Request AI Review
        id: review
        run: |
          RESPONSE=$(curl -s -X POST "${{ secrets.MCP_SERVER_URL }}/api/review-pr" \
            -H "X-API-Key: ${{ secrets.MCP_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{"pr_number": ${{ github.event.pull_request.number }}}')

          echo "$RESPONSE" | jq -r '.review' > review.md

      - name: Post Review Comment
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const review = fs.readFileSync('review.md', 'utf8');
            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: '## AI Code Review\n\n' + review
            });
```

**Required secrets:**
- `MCP_SERVER_URL` - Backend server URL (e.g., `https://your-server.railway.app`)
- `MCP_API_KEY` - API key for authentication

## System Components

### 1. Backend Server (server/)

**Files:**
- `main.py` - FastAPI application entry point
- `app.py` - API routes and endpoints
- `chat_service.py` - Message processing with MCP tool integration
- `mcp_manager.py` - MCP server connection management
- `mcp_http_transport.py` - HTTP transport for GitHub Copilot MCP
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

### 3. RAG MCP Server (server/mcp_rag/)

**Files:**
- `server.py` - MCP server with RAG tools
- `github_fetcher.py` - GitHub API client for /specs folder
- `rag_engine.py` - Vector search with OpenRouter embeddings

### 4. MCP Servers

#### GitHub Copilot MCP (HTTP)

**URL:** `https://api.githubcopilot.com/mcp/`

**Transport:** HTTP (Streamable HTTP transport, MCP spec 2025-03-26)

**Essential Tools:**
- `get_file_contents` - Read file contents from repository
- `list_commits` / `get_commit` - View commit history
- `list_issues` / `issue_read` - Work with issues
- `list_pull_requests` / `pull_request_read` - Work with PRs

**Authentication:** GitHub Personal Access Token (PAT)

#### RAG Specs MCP (Python/stdio)

**Tools:**
- `rag_query` - Search documentation with semantic similarity
- `list_specs` - List available specification files
- `get_spec_content` - Get full content of a spec file
- `rebuild_index` - Rebuild the RAG index
- `get_project_structure` - Get directory tree

**Target Repository:** `LebedAlIv2601/EasyPomodoro`

## Installation

### Prerequisites
- Python 3.14+
- OpenRouter API key
- GitHub Personal Access Token
- Telegram bot token (for client)

### Server Setup

1. **Clone repository:**
```bash
git clone <repo-url>
cd McpSystem
```

2. **Create virtual environment:**
```bash
python3.14 -m venv venv
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

### GitHub PAT Scopes

Create a Classic PAT with these scopes:
- `repo` - Full repository access
- `read:org` - Read organization data (optional)
- `read:user` - Read user data

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

- **Python 3.14** - Main language
- **FastAPI** - Backend API framework
- **python-telegram-bot** - Telegram integration
- **MCP SDK** - Model Context Protocol (HTTP + stdio transports)
- **httpx** - Async HTTP client
- **OpenRouter** - LLM API access
- **Pydantic** - Data validation

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

# Chat
curl -X POST "https://your-server.railway.app/api/chat" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "What is the project structure?"}'

# PR Review
curl -X POST "https://your-server.railway.app/api/review-pr" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"pr_number": 1}'
```

## Troubleshooting

### GitHub Copilot MCP connection errors
- Verify PAT has correct scopes (`repo`, `read:org`)
- Check token is not expired
- Check network connectivity to api.githubcopilot.com

### Empty responses from PR review
- Check logs for tool call errors
- Verify `tool_choice: required` is set for first iteration
- Model may not support function calling well - try different model

### High latency
- PR review may take 30-60 seconds due to multiple tool calls
- Check OpenRouter rate limits

## License

This project demonstrates MCP integration for AI-powered project consultation.
