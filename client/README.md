# Telegram Weather Bot Client

Telegram bot integrated with OpenRouter AI and MCP weather forecast server.

## Features

- Telegram bot interface for weather queries
- OpenRouter AI integration (model: kwaipilot/kat-coder-pro:free)
- MCP tool usage for weather data retrieval
- "Думаю" (thinking) indicator while processing requests
- Current date context automatically provided to model
- Per-user conversation history (max 50 messages)
- Automatic history clearing on overflow
- MCP usage indicator in responses
- Console logging for requests/responses
- Multi-user concurrent support
- Secure credential storage via environment variables

## Architecture

```
Telegram User
    ↓
Telegram Bot (bot.py)
    ↓
OpenRouter API (openrouter_client.py)
    ↓ (when tool needed)
MCP Client (mcp_manager.py)
    ↓
MCP Server Subprocess (../server.py)
    ↓
Open-Meteo Weather API
```

## Requirements

- Python 3.14+
- MCP weather server (in parent directory)
- Valid Telegram bot token
- Valid OpenRouter API key

## Installation

```bash
# Navigate to client directory
cd client

# Install dependencies (assuming venv from parent directory)
../venv/bin/python -m pip install -r requirements.txt
```

## Configuration

### Environment Variables Setup

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your credentials:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

3. Get your credentials:
   - **Telegram Bot Token**: Create a bot via [@BotFather](https://t.me/botfather) on Telegram
   - **OpenRouter API Key**: Sign up at [OpenRouter.ai](https://openrouter.ai/)

**SECURITY NOTE**:
- Never commit `.env` file to version control
- `.env` is already excluded in `.gitignore`
- All credentials are loaded from environment variables only

### Other Configuration

Edit `config.py` to update:
- Model name
- Conversation history limit
- API endpoints
- Timeout values

## Running

```bash
# From client directory
../venv/bin/python main.py
```

## Usage

1. Start bot: Send `/start` command in Telegram
2. Ask weather questions: "What's the weather in Moscow tomorrow?"
3. Bot uses MCP server automatically when needed
4. Responses include "✓ MCP was used" indicator when tools are called

## Conversation History

- Each user has isolated conversation history
- Maximum 50 messages per user
- History cleared automatically when limit reached
- Start command message not included in history

## Logging

Console logging shows:
- Bot startup/shutdown events
- User message reception
- OpenRouter API requests/responses
- MCP tool calls and results
- Error details with tracebacks

## Error Handling

- User sees: "Sorry, something went wrong. Please try again."
- Logs contain: Full error details and stack traces

## Project Structure

```
client/
├── main.py                    # Application entry point
├── bot.py                     # Telegram bot handler
├── mcp_manager.py            # MCP client and subprocess manager
├── openrouter_client.py      # OpenRouter API integration
├── conversation.py           # Per-user history manager
├── logger.py                 # Logging configuration
├── config.py                 # Configuration constants
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not in git)
├── .env.example              # Environment variables template
└── README.md                 # This file
```

## Shutdown

- Press Ctrl+C for graceful shutdown
- Bot stops accepting messages
- MCP server subprocess terminated
- All connections closed cleanly
