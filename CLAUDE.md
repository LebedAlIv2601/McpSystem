# EasyPomodoro Project Consultant Bot

Telegram bot for consulting on the EasyPomodoro Android project using MCP (Model Context Protocol) servers.

## Project Overview

This system provides an AI-powered project consultant that can:
1. Browse and analyze project code via GitHub MCP (100+ tools)
2. Search project documentation using RAG (Retrieval Augmented Generation)

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
└──────┬──────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────┐
│ OpenRouter API                          │
│ Model: nvidia/nemotron-3-nano-30b-a3b   │
│ - Processes natural language            │
│ - Decides when to use tools             │
└──────┬──────────────────────────────────┘
       │ (when tool needed)
       ↓
┌─────────────────────────────────────────┐
│ MCP Manager (mcp_manager.py)            │
│ - Manages 2 MCP server connections      │
│ - Routes tool calls to correct server   │
│ - All servers use stdio transport       │
└──────┬──────────────────────────────────┘
       │
       ├───────────────────────────────────┐
       ↓                                   ↓
┌──────────────────────┐    ┌──────────────────────┐
│ GitHub MCP Server    │    │ RAG Specs MCP        │
│ (Docker)             │    │ (Python)             │
│                      │    │                      │
│ Image:               │    │ Tools:               │
│ ghcr.io/github/      │    │ - rag_query          │
│ github-mcp-server    │    │ - list_specs         │
│                      │    │ - get_spec_content   │
│ Tools: 100+          │    │ - rebuild_index      │
│ - get_file_contents  │    │                      │
│ - search_code        │    │ Uses:                │
│ - list_commits       │    │ - GitHub API         │
│ - list_issues        │    │ - FAISS + Ollama     │
│ - list_pull_requests │    │                      │
│ - And many more...   │    │                      │
└──────────────────────┘    └──────────────────────┘
```

## System Components

### 1. MCP Servers

#### 1.1 GitHub MCP Server (Docker)

**Purpose:** Provide access to GitHub repository (100+ tools)

**Image:** `ghcr.io/github/github-mcp-server`

**Transport:** stdio (via Docker)

**Key Tools:**
- `get_file_contents` - Read file contents from repository
- `search_code` - Search code in repository
- `list_commits` - View commit history
- `get_issue` / `list_issues` - Work with issues
- `get_pull_request` / `list_pull_requests` - Work with PRs
- `create_issue` / `create_pull_request` - Create issues/PRs
- And 90+ more tools for complete GitHub integration

**Authentication:** GitHub Personal Access Token (PAT)

#### 1.2 RAG Specs MCP (Python)

**Purpose:** Search project documentation using RAG

**Location:** `mcp_rag/`

**Files:**
- `server.py` - MCP server with RAG tools
- `github_fetcher.py` - GitHub API client for /specs folder
- `rag_engine.py` - FAISS + Ollama embeddings

**Tools:**
- `rag_query` - Search documentation with semantic similarity
- `list_specs` - List available specification files
- `get_spec_content` - Get full content of a spec file
- `rebuild_index` - Rebuild the RAG index

**Target Repository:** `LebedAlIv2601/EasyPomodoro`
**Specs Path:** `/specs`

### 2. Telegram Bot Client (client/)

**Files:**
- `main.py` - Application entry point
- `bot.py` - Telegram bot handlers
- `mcp_manager.py` - MCP server management (stdio only)
- `openrouter_client.py` - OpenRouter API integration
- `conversation.py` - Per-user conversation history
- `logger.py` - Logging configuration
- `config.py` - Configuration and environment variables

## Installation

### Prerequisites
- Python 3.14+
- Docker (for GitHub MCP server)
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

4. **Pull Docker image:**
```bash
docker pull ghcr.io/github/github-mcp-server
```

5. **Install Ollama model (for RAG):**
```bash
ollama pull nomic-embed-text
```

6. **Configure environment:**
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
1. Start GitHub MCP server (Docker container)
2. Start RAG Specs MCP server (Python)
3. Fetch available tools from both servers (100+ total)
4. Start Telegram bot polling

**Note:** First run may take longer while Docker pulls the image.

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
- "Search for timer implementation"
- "What files are in the app module?"

**GitHub questions:**
- "Show recent commits"
- "List open issues"
- "What pull requests are pending?"

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
| `OPENROUTER_MODEL` | `nvidia/nemotron-3-nano-30b-a3b:free` | AI model |
| `GITHUB_OWNER` | `LebedAlIv2601` | Repository owner |
| `GITHUB_REPO` | `EasyPomodoro` | Repository name |
| `SPECS_PATH` | `specs` | Documentation folder |
| `MAX_CONVERSATION_HISTORY` | 50 | Max messages per user |
| `TOOL_CALL_TIMEOUT` | 120.0 | MCP tool timeout (seconds) |

## Technology Stack

- **Python 3.14** - Main language
- **Docker** - GitHub MCP server container
- **python-telegram-bot** - Telegram integration
- **MCP SDK** - Model Context Protocol
- **FAISS** - Vector similarity search
- **Ollama** - Local embeddings (nomic-embed-text)
- **OpenRouter** - AI model access

## Project Statistics

- **MCP Servers:** 2
  - GitHub MCP (Docker, 100+ tools)
  - RAG Specs MCP (Python, 4 tools)
- **Total MCP Tools:** 100+

## Troubleshooting

### Docker not starting
```bash
# Check Docker is running
docker ps

# Pull image manually
docker pull ghcr.io/github/github-mcp-server
```

### GitHub authentication errors
- Verify PAT has correct scopes (`repo`, `read:org`)
- Check token is not expired
- Ensure token is in `.env` file

### RAG not working
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check nomic-embed-text model: `ollama list`

## License

This project demonstrates MCP integration for AI-powered project consultation.
