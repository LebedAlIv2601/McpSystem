# Multi-MCP Telegram Bot System

AI-powered Telegram bot with task management and mobile automation via multiple MCP (Model Context Protocol) servers.

## Overview

This system integrates three specialized MCP servers with a Telegram bot powered by OpenRouter AI, providing a unified conversational interface for:
- **Task Management** - Weeek task tracker integration
- **Information** - Random facts generator
- **Mobile Automation** - Android/iOS device control

## Features

### 🤖 AI-Powered Telegram Bot
- Natural language interface via OpenRouter (deepseek-v3.1)
- Supports up to 15 chained tool calls per conversation
- Per-user conversation history (max 50 messages)
- Real-time "Думаю..." thinking indicator
- Automatic MCP usage indicator

### 📋 Task Management (Weeek MCP)
- Retrieve tasks with states: Backlog, In Progress, Done
- Periodic task monitoring (every 30 seconds)
- AI-generated summaries every 2 minutes
- User subscription management for summaries

### 📱 Mobile Automation (mobile-mcp)
19 tools for comprehensive mobile device control:
- Device & app management
- Screen interaction (tap, swipe, type)
- Screenshots and UI element listing
- Hardware button simulation
- Orientation control

### 🎲 Random Facts (facts-mcp)
- On-demand interesting facts via `/fact` command

## Architecture

```
Telegram User
    ↓
Telegram Bot (Python) → OpenRouter AI (21 tools)
    ↓
MCP Manager (AsyncExitStack)
    ├─→ Weeek Tasks MCP (Python)
    ├─→ Random Facts MCP (Python)
    └─→ Mobile MCP (Node.js/npx)
```

## Prerequisites

- **Python 3.14+**
- **Node.js v22+** (for mobile-mcp)
- **Android Platform Tools** (adb) for mobile automation
- **Telegram Bot Token** (from @BotFather)
- **OpenRouter API Key** (from openrouter.ai)
- **Weeek API Token** (configured in mcp_tasks/weeek_api.py)

## Installation

### 1. Clone and Navigate
```bash
cd /path/to/McpSystem
```

### 2. Install Node.js v22+ (if needed)
```bash
# Using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.zshrc  # or ~/.bashrc
nvm install 22
nvm use 22
node --version  # Should show v22.x.x
```

### 3. Verify Android Platform Tools
```bash
adb --version  # Should show adb version
```

### 4. Setup Python Environment
```bash
python3.14 -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
pip install -r client/requirements.txt
```

### 5. Configure Environment Variables
```bash
cd client
cp .env.example .env
# Edit .env:
# TELEGRAM_BOT_TOKEN=your_token_here
# OPENROUTER_API_KEY=your_key_here
```

## Running the System

### Start All MCP Servers + Bot
```bash
cd client
../venv/bin/python main.py
```

**First run:** May take 30-40 seconds while mobile-mcp downloads and initializes.

### Test Individual MCP Servers (Optional)
```bash
# Weeek Tasks
python mcp_tasks/server.py

# Random Facts
python mcp_facts/server.py

# Mobile MCP
npx -y @mobilenext/mobile-mcp@latest
```

## Usage

### Telegram Commands
- `/start` - Welcome message
- `/tasks [query]` - Query Weeek tasks
- `/fact` - Get random fact
- `/subscribe` - Enable periodic task summaries
- `/unsubscribe` - Disable summaries

### Natural Language Examples
```
"List available Android devices"
"Take a screenshot of the device"
"Show me tasks in progress"
"Launch Chrome and navigate to google.com"
"What tasks are done?"
```

## System Configuration

### client/config.py
- `MAX_CONVERSATION_HISTORY` - Message limit per user (default: 50)
- `TOOL_CALL_TIMEOUT` - MCP tool timeout (default: 30s)
- `TASK_FETCH_INTERVAL` - Task monitoring interval (default: 30s)
- `SUMMARY_INTERVAL` - Summary delivery interval (default: 120s)
- `MCP_SERVERS` - List of MCP server configurations

### client/bot.py
- `max_iterations` - Max chained tool calls (default: 15)

## Project Statistics

- **Languages:** Python 3.14, Node.js v22+
- **MCP Servers:** 3 (Weeek Tasks, Random Facts, Mobile MCP)
- **Total Tools:** 21
  - 1 task management (get_tasks)
  - 1 information (get_fact)
  - 19 mobile automation (mobile_*)
- **API Integrations:** Telegram, OpenRouter, Weeek
- **Transport:** stdio (MCP), HTTPS (APIs)

## Project Structure

```
McpSystem/
├── mcp_tasks/              # Weeek task tracker MCP server
│   ├── server.py
│   └── weeek_api.py
├── mcp_facts/              # Random facts MCP server
│   └── server.py
├── client/                 # Telegram bot client
│   ├── main.py            # Entry point
│   ├── bot.py             # Bot handlers
│   ├── mcp_manager.py     # Multi-MCP connection manager
│   ├── openrouter_client.py
│   ├── scheduler.py       # Periodic task monitoring
│   ├── config.py          # Configuration
│   └── .env               # Credentials (not in git)
├── CLAUDE.md              # Detailed documentation
└── README.md              # This file
```

## Troubleshooting

### Bot Conflict Error
```
Conflict: terminated by other getUpdates request
```
**Solution:** Only one bot instance can run at a time. Kill all instances:
```bash
pkill -9 -f "Python main.py"
```

### Mobile MCP Connection Errors
- Verify Node.js v22+: `node --version`
- Verify adb: `adb --version`
- Check device connected: `adb devices`
- First run takes 30-40 seconds (downloading package)

### MCP Server Errors
- Check logs for initialization errors
- Verify all prerequisites installed
- Ensure environment variables configured correctly

## Technology Stack

### MCP Servers
- **MCP SDK (Python)** - Model Context Protocol implementation
- **httpx** - Async HTTP client for Weeek API
- **@mobilenext/mobile-mcp** - Node.js mobile automation

### Client
- **python-telegram-bot** - Telegram bot framework
- **MCP SDK** - MCP client implementation
- **httpx** - OpenRouter API client
- **AsyncExitStack** - Multi-context manager for MCP connections

### External Tools
- **Node.js v22+** - Runtime for mobile-mcp
- **npx** - Package runner
- **Android Platform Tools (adb)** - Device communication

## Recent Updates

### v2.0 - Mobile Automation Integration
- ✅ Added mobile-mcp server (19 Android/iOS automation tools)
- ✅ Refactored MCP manager with AsyncExitStack for stable multi-server connections
- ✅ Increased tool call iteration limit from 5 to 15
- ✅ Fixed environment variable inheritance for Node.js processes
- ✅ Updated documentation with mobile automation examples

## Credits

- [Weeek API](https://weeek.net/) - Task management data
- [Anthropic](https://anthropic.com/) - MCP protocol specification
- [OpenRouter](https://openrouter.ai/) - AI model access
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram integration
- [mobile-mcp](https://github.com/mobile-next/mobile-mcp) - Mobile automation capabilities

## License

This project demonstrates MCP integration with AI-powered conversational interfaces.
