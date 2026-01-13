# EasyPomodoro Project Consultant Bot

Telegram bot for consulting on the EasyPomodoro Android project using MCP (Model Context Protocol) servers.

## Project Overview

This system provides an AI-powered project consultant that can:
1. Browse and analyze project code via GitHub Copilot MCP (HTTP transport)
2. Search project documentation using RAG (Retrieval Augmented Generation)
3. Explore project structure with tree navigation

## Architecture

```
┌─────────────┐
│ Telegram    │
│ User        │
└──────┬──────┘
       │
       ↓
┌─────────────────────────────────────────┐
│ Telegram Bot (client/bot.py)           │
│ - Handles user messages                 │
│ - Manages conversation history          │
│ - Shows "Думаю..." indicator            │
│ - Filters tools to essential set        │
└──────┬──────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────┐
│ OpenRouter API                          │
│ Model: deepseek/deepseek-v3.2           │
│ - Processes natural language            │
│ - Decides when to use tools             │
└──────┬──────────────────────────────────┘
       │ (when tool needed)
       ↓
┌─────────────────────────────────────────┐
│ MCP Manager (mcp_manager.py)            │
│ - Manages 2 MCP server connections      │
│ - Routes tool calls to correct server   │
│ - HTTP transport for GitHub Copilot     │
│ - stdio transport for RAG MCP           │
└──────┬──────────────────────────────────┘
       │
       ├───────────────────────────────────┐
       ↓                                   ↓
┌──────────────────────┐    ┌──────────────────────┐
│ GitHub Copilot MCP   │    │ RAG Specs MCP        │
│ (HTTP Transport)     │    │ (Python/stdio)       │
│                      │    │                      │
│ URL:                 │    │ Tools:               │
│ api.githubcopilot.   │    │ - rag_query          │
│ com/mcp/             │    │ - list_specs         │
│                      │    │ - get_spec_content   │
│ Essential Tools:     │    │ - rebuild_index      │
│ - get_file_contents  │    │ - get_project_       │
│ - list_commits       │    │   structure (tree)   │
│ - get_commit         │    │                      │
│ - list_issues        │    │ Uses:                │
│ - issue_read         │    │ - GitHub API         │
│ - list_pull_requests │    │ - FAISS + Ollama     │
│ - pull_request_read  │    │                      │
└──────────────────────┘    └──────────────────────┘
```

## System Components

### 1. MCP Servers

#### 1.1 GitHub Copilot MCP (HTTP)

**Purpose:** Provide access to GitHub repository via GitHub Copilot's MCP endpoint

**URL:** `https://api.githubcopilot.com/mcp/`

**Transport:** HTTP (Streamable HTTP transport, MCP spec 2025-03-26)

**Essential Tools (filtered for token efficiency):**
- `get_file_contents` - Read file contents from repository
- `list_commits` / `get_commit` - View commit history
- `list_issues` / `issue_read` - Work with issues
- `list_pull_requests` / `pull_request_read` - Work with PRs

**Note:** The server provides 40+ tools, but only essential ones are sent to the model to reduce token usage.

**Authentication:** GitHub Personal Access Token (PAT)

#### 1.2 RAG Specs MCP (Python)

**Purpose:** Search project documentation using RAG and explore project structure

**Location:** `mcp_rag/`

**Files:**
- `server.py` - MCP server with RAG tools
- `github_fetcher.py` - GitHub API client for /specs folder and project structure
- `rag_engine.py` - FAISS + Ollama embeddings

**Tools:**
- `rag_query` - Search documentation with semantic similarity
- `list_specs` - List available specification files
- `get_spec_content` - Get full content of a spec file
- `rebuild_index` - Rebuild the RAG index
- `get_project_structure` - Get directory tree (use FIRST to find file paths)

**Target Repository:** `LebedAlIv2601/EasyPomodoro`
**Specs Path:** `/specs`

### 2. Telegram Bot Client (client/)

**Files:**
- `main.py` - Application entry point
- `bot.py` - Telegram bot handlers with tool call loop
- `mcp_manager.py` - MCP server management (HTTP + stdio)
- `mcp_http_transport.py` - HTTP transport for GitHub Copilot MCP
- `openrouter_client.py` - OpenRouter API integration
- `conversation.py` - Per-user conversation history
- `logger.py` - Logging configuration
- `config.py` - Configuration, environment variables, and ESSENTIAL_TOOLS filter

## Installation

### Prerequisites
- Python 3.14+
- Ollama with `nomic-embed-text` model (for RAG)
- Telegram bot token
- OpenRouter API key
- GitHub Personal Access Token

### Setup

1. **Clone repository:**
```bash
cd /path/to/McpSystem
```

2. **Create virtual environment:**
```bash
python3.14 -m venv venv
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
pip install -r mcp_rag/requirements.txt
```

4. **Install Ollama model (for RAG):**
```bash
ollama pull nomic-embed-text
```

5. **Configure environment:**
```bash
cd client
cp .env.example .env
# Edit .env with your credentials:
# TELEGRAM_BOT_TOKEN=your_token
# OPENROUTER_API_KEY=your_key
# GITHUB_TOKEN=your_github_pat
```

### GitHub PAT Scopes

Create a Classic PAT with these scopes:
- `repo` - Full repository access
- `read:org` - Read organization data (optional)
- `read:user` - Read user data

## Running

```bash
cd client
../venv/bin/python main.py
```

The bot will:
1. Connect to GitHub Copilot MCP (HTTP)
2. Start RAG Specs MCP server (Python/stdio)
3. Fetch and filter tools to essential set (~12 tools)
4. Start Telegram bot polling

## Usage

### Commands

- `/start` - Show welcome message

### Example Queries

**Documentation questions:**
- "What is the project architecture?"
- "How does the timer feature work?"
- "List all specification files"

**Code questions:**
- "Show me the main activity code"
- "What files are in the app module?"
- "Get project structure"

**GitHub questions:**
- "Show recent commits"
- "List open issues"
- "What pull requests are pending?"

### Recommended Workflow

For code exploration, the model follows this workflow:
1. `get_project_structure` - Find file paths first
2. `get_file_contents` - Read specific files using exact paths

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `GITHUB_TOKEN` | GitHub Personal Access Token |

### config.py Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENROUTER_MODEL` | `deepseek/deepseek-v3.2` | AI model |
| `GITHUB_OWNER` | `LebedAlIv2601` | Repository owner |
| `GITHUB_REPO` | `EasyPomodoro` | Repository name |
| `SPECS_PATH` | `specs` | Documentation folder |
| `MAX_CONVERSATION_HISTORY` | 50 | Max messages per user |
| `TOOL_CALL_TIMEOUT` | 120.0 | MCP tool timeout (seconds) |
| `ESSENTIAL_TOOLS` | list | Tools to send to model (token optimization) |

## Technology Stack

- **Python 3.14** - Main language
- **python-telegram-bot** - Telegram integration
- **MCP SDK** - Model Context Protocol (HTTP + stdio transports)
- **httpx** - Async HTTP client for GitHub Copilot MCP
- **FAISS** - Vector similarity search
- **Ollama** - Local embeddings (nomic-embed-text)
- **OpenRouter** - AI model access

## Project Statistics

- **MCP Servers:** 2
  - GitHub Copilot MCP (HTTP, ~40 tools available, ~8 essential)
  - RAG Specs MCP (Python/stdio, 5 tools)
- **Essential Tools:** ~12 (filtered for token efficiency)

## Troubleshooting

### GitHub Copilot MCP connection errors
- Verify PAT has correct scopes (`repo`, `read:org`)
- Check token is not expired
- Ensure token is in `.env` file
- Check network connectivity to api.githubcopilot.com

### RAG not working
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check nomic-embed-text model: `ollama list`

### High token usage
- Ensure `ESSENTIAL_TOOLS` filter is applied in config.py
- Check logs for "Filtered tools: X/Y" message

## License

This project demonstrates MCP integration for AI-powered project consultation.
