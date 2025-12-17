# Weather Forecast MCP System

Complete system for weather forecasting via Telegram bot using MCP (Model Context Protocol) server and OpenRouter AI.

## Project Overview

This project consists of two main components:
1. **MCP Server** - Local weather forecast server providing weather data via Open-Meteo API
2. **Telegram Bot Client** - AI-powered bot using OpenRouter that connects to MCP server

## Architecture

```
┌─────────────┐
│ Telegram    │
│ User        │
└──────┬──────┘
       │
       ↓
┌─────────────────────────────────┐
│ Telegram Bot (client/bot.py)   │
│ - Handles user messages         │
│ - Manages conversation history  │
│ - Shows "Думаю..." indicator    │
└──────┬──────────────────────────┘
       │
       ↓
┌─────────────────────────────────┐
│ OpenRouter API                  │
│ Model: kwaipilot/kat-coder-pro  │
│ - Processes natural language    │
│ - Decides when to use tools     │
└──────┬──────────────────────────┘
       │ (when tool needed)
       ↓
┌─────────────────────────────────┐
│ MCP Client (mcp_manager.py)     │
│ - Manages server subprocess     │
│ - Executes tool calls           │
└──────┬──────────────────────────┘
       │
       ↓
┌─────────────────────────────────┐
│ MCP Server (server.py)          │
│ - Geocoding (city → coords)     │
│ - Weather API integration       │
└──────┬──────────────────────────┘
       │
       ↓
┌─────────────────────────────────┐
│ Open-Meteo Weather API          │
│ - Geocoding API                 │
│ - Weather Forecast API          │
└─────────────────────────────────┘
```

## System Components

### 1. MCP Server (Root Directory)

**Purpose:** Provide weather forecast data via MCP protocol

**Files:**
- `server.py` - Main MCP server with stdio transport
- `geocoding.py` - Location geocoding (city name → coordinates)
- `weather.py` - Weather API integration
- `requirements.txt` - Server dependencies

**Tool Provided:**
- `get_weather_forecast` - Returns weather data for location and date range

**Input:**
```json
{
  "location": "Moscow" or "Moscow, Russia",
  "start_date": "2025-12-17",
  "end_date": "2025-12-18"
}
```

**Output:**
```json
{
  "location": "Moscow, Russia",
  "forecast": [
    {
      "date": "2025-12-17",
      "temperature_2m": {"min": -5, "max": 2, "unit": "°C"},
      "precipitation": {"total": 0.5, "unit": "mm"},
      "cloud_cover": {"average": 75, "unit": "%"},
      "relative_humidity_2m": {"average": 85, "unit": "%"},
      "wind_speed_10m": {"max": 15, "unit": "km/h"}
    }
  ]
}
```

### 2. Telegram Bot Client (client/ Directory)

**Purpose:** Provide conversational interface for weather queries

**Files:**
- `main.py` - Application entry point and lifecycle management
- `bot.py` - Telegram bot handlers and message processing
- `mcp_manager.py` - MCP server subprocess and client management
- `openrouter_client.py` - OpenRouter API integration
- `conversation.py` - Per-user conversation history manager
- `logger.py` - Logging configuration
- `config.py` - Configuration and environment variables
- `.env` - Environment variables (not in git)
- `.env.example` - Environment variables template

**Features:**
- Per-user isolated conversation history (max 50 messages)
- "Думаю..." thinking indicator while processing
- Current date automatically provided to model
- MCP usage indicator ("✓ MCP was used")
- Automatic history clearing on overflow
- Secure credential storage
- Multi-user concurrent support

## Installation

### Prerequisites
- Python 3.14+
- Telegram bot token (from @BotFather)
- OpenRouter API key (from openrouter.ai)

### Setup Steps

1. **Clone repository and navigate to project:**
```bash
cd /path/to/McpSystem
```

2. **Create and activate virtual environment:**
```bash
python3.14 -m venv venv
source venv/bin/activate  # On macOS/Linux
```

3. **Install server dependencies:**
```bash
pip install -r requirements.txt
```

4. **Install client dependencies:**
```bash
pip install -r client/requirements.txt
```

5. **Configure environment variables:**
```bash
cd client
cp .env.example .env
# Edit .env and add your credentials:
# TELEGRAM_BOT_TOKEN=your_token_here
# OPENROUTER_API_KEY=your_key_here
```

## Running the System

### Start Telegram Bot (Automatically Starts MCP Server)

```bash
cd client
../venv/bin/python main.py
```

The bot will:
1. Start MCP server as subprocess
2. Connect MCP client via stdio
3. Fetch available tools from server
4. Start Telegram bot polling
5. Begin accepting user messages

### Test MCP Server Standalone (Optional)

```bash
python server.py
```

Server communicates via stdio (standard input/output).

## Usage

### Telegram Bot Commands

- `/start` - Start conversation and show welcome message

### Example Conversations

**User:** What's the weather in Moscow today?

**Bot:** Думаю...

**Bot:** The weather in Moscow today is partly cloudy with temperatures between -5°C and 2°C. There's a slight chance of precipitation (0.5mm) with humidity around 85% and wind speeds up to 15 km/h.

✓ MCP was used

---

**User:** How about tomorrow in Paris?

**Bot:** Думаю...

**Bot:** Tomorrow in Paris, expect mostly cloudy conditions with temperatures ranging from 8°C to 12°C. Light rain is expected (2.3mm) with 78% humidity and winds up to 20 km/h.

✓ MCP was used

## Configuration

### Server Configuration

Edit `server.py` constants:
- Tool parameters
- API endpoints
- Validation rules

### Client Configuration

Edit `client/config.py`:
- `OPENROUTER_MODEL` - AI model to use
- `MAX_CONVERSATION_HISTORY` - Message limit per user (default: 50)
- `TOOL_CALL_TIMEOUT` - MCP tool timeout (default: 30s)
- `WELCOME_MESSAGE` - Bot greeting
- `MCP_USED_INDICATOR` - Tool usage indicator

### Environment Variables

Required in `client/.env`:
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `OPENROUTER_API_KEY` - OpenRouter API key

## Logging

### Log Levels
- INFO: Normal operations, user messages, API calls
- DEBUG: Detailed request/response data
- ERROR: Exceptions and failures

### Log Output Example
```
2025-12-17 01:45:23 - INFO - User 12345: Received message: weather in Moscow
2025-12-17 01:45:24 - INFO - === MCP SERVER CALL ===
2025-12-17 01:45:24 - INFO - Tool: get_weather_forecast
2025-12-17 01:45:24 - INFO - Arguments: {'location': 'Moscow', 'start_date': '2025-12-17', 'end_date': '2025-12-17'}
2025-12-17 01:45:26 - INFO - MCP server response received
```

## Error Handling

### User-Facing Errors
- Generic message: "Sorry, something went wrong. Please try again."
- MCP errors: "No data, ask something other"

### Logged Errors
- Full exception traceback
- Request/response context
- User and session information

## Security

### Credentials
- Never commit `.env` file to git
- All credentials loaded from environment variables
- `.gitignore` excludes sensitive files

### MCP Server
- Runs locally as subprocess
- No external network access
- Stdio transport only

## Technology Stack

### Server
- **MCP SDK** - Model Context Protocol implementation
- **httpx** - Async HTTP client
- **pydantic** - Data validation

### Client
- **python-telegram-bot** - Telegram bot framework
- **MCP SDK** - MCP client implementation
- **httpx** - OpenRouter API client
- **python-dotenv** - Environment variable management

## Conversation Flow

1. User sends message to Telegram bot
2. Bot shows "Думаю..." indicator
3. Bot adds message to user's history
4. Bot checks if history limit reached (50 messages)
5. Bot prepends system prompt with current date
6. Bot sends conversation to OpenRouter with available tools
7. OpenRouter decides if tool call needed
8. If tool needed:
   - Bot calls MCP server via subprocess
   - Server geocodes location
   - Server fetches weather data
   - Server returns formatted result
   - Bot sends result back to OpenRouter
   - OpenRouter generates final response
9. Bot deletes "Думаю..." indicator
10. Bot sends final response to user
11. If MCP was used, appends "✓ MCP was used"
12. Bot stores assistant response in history

## System Prompt

Every request to OpenRouter includes:
```
Current date: YYYY-MM-DD. All dates must be calculated relative to this date.
```

This ensures the model has temporal context for queries like "tomorrow" or "next week".

## Shutdown

Graceful shutdown on Ctrl+C:
1. Stop Telegram bot polling
2. Close MCP client connection
3. Terminate MCP server subprocess
4. Clean up resources

## Troubleshooting

### Bot not responding
- Check `.env` file exists with valid credentials
- Verify internet connection
- Check logs for errors

### MCP server errors
- Verify server.py runs standalone
- Check Open-Meteo API availability
- Review MCP server logs

### Tool calls failing
- Check MCP server subprocess is running
- Verify tool arguments format
- Review timeout settings

## Project Statistics

- **Languages:** Python 3.14
- **Total Files:** 13 Python modules
- **MCP Tools:** 1 (get_weather_forecast)
- **API Integrations:** 3 (Telegram, OpenRouter, Open-Meteo)
- **Transport:** stdio (MCP), HTTPS (APIs)

## Future Enhancements

Potential improvements:
- Add more MCP tools (forecast charts, alerts, historical data)
- Support multiple languages
- Add weather alerts and notifications
- Implement caching for repeated queries
- Add user preferences storage
- Support location favorites
- Add weather trend analysis

## License

This project demonstrates MCP integration with AI-powered conversational interfaces.

## Credits

- Open-Meteo API for weather data
- Anthropic for MCP protocol specification
- OpenRouter for AI model access
- Python-telegram-bot for Telegram integration
