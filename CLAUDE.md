# Task Tracker MCP System

Complete system for task management via Telegram bot using MCP (Model Context Protocol) server and OpenRouter AI.

## Project Overview

This project consists of two main components:
1. **MCP Server** - Local task tracker server providing task data via Weeek API
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
│ - Handles /tasks command        │
│ - Handles /subscribe command    │
│ - Manages conversation history  │
│ - Shows "Думаю..." indicator    │
└──────┬──────────────────────────┘
       │
       ↓
┌─────────────────────────────────┐
│ OpenRouter API                  │
│ Model: nex-agi/deepseek-v3.1    │
│ - Processes natural language    │
│ - Decides when to use tools     │
└──────┬──────────────────────────┘
       │ (when tool needed)
       ↓
┌─────────────────────────────────┐
│ MCP Client (mcp_manager.py)     │◄──────────┐
│ - Manages server subprocess     │           │
│ - Executes tool calls           │           │
└──────┬──────────────────────────┘           │
       │                                       │
       ↓                                       │
┌─────────────────────────────────┐           │
│ MCP Server (server.py)          │           │
│ - Task retrieval integration    │           │
└──────┬──────────────────────────┘           │
       │                                       │
       ↓                                       │
┌─────────────────────────────────┐           │
│ Weeek API                       │           │
│ - Task Tracker API              │           │
└─────────────────────────────────┘           │
                                               │
┌──────────────────────────────────────────────┘
│
│ Parallel Background Process:
│
│ ┌────────────────────────────────────┐
│ │ Scheduler (client/scheduler.py)    │
│ │ - Fetches tasks every 30 seconds   │
│ │ - Sends summaries every 2 minutes  │
│ │ - Manages subscriptions            │
│ └────────────────────────────────────┘
```

## System Components

### 1. MCP Server (Root Directory)

**Purpose:** Provide task data via MCP protocol

**Files:**
- `server.py` - Main MCP server with stdio transport
- `weeek_api.py` - Weeek task tracker API integration
- `requirements.txt` - Server dependencies

**Tool Provided:**
- `get_tasks` - Returns all tasks from Weeek task tracker

**Input:**
```json
{}
```

**Output:**
```json
{
  "tasks": [
    {
      "id": 12345,
      "title": "Implement authentication",
      "state": "In progress"
    },
    {
      "id": 12346,
      "title": "Write documentation",
      "state": "Backlog"
    },
    {
      "id": 12347,
      "title": "Deploy to production",
      "state": "Done"
    }
  ]
}
```

**State Mapping:**
- `boardColumnId: 1` → "Backlog"
- `boardColumnId: 2` → "In progress"
- `boardColumnId: 3` → "Done"

### 2. Telegram Bot Client (client/ Directory)

**Purpose:** Provide conversational interface for task management queries

**Files:**
- `main.py` - Application entry point and lifecycle management
- `bot.py` - Telegram bot handlers and message processing
- `mcp_manager.py` - MCP server subprocess and client management
- `openrouter_client.py` - OpenRouter API integration
- `conversation.py` - Per-user conversation history manager
- `scheduler.py` - Periodic task monitoring and AI-generated summary delivery
- `task_state_manager.py` - Task state persistence and change detection
- `subscribers.py` - User subscription management for periodic summaries
- `summary_formatter.py` - Legacy template-based formatter (not used, kept for fallback)
- `logger.py` - Logging configuration
- `config.py` - Configuration and environment variables
- `.env` - Environment variables (not in git)
- `.env.example` - Environment variables template

**Features:**
- Per-user isolated conversation history (max 50 messages)
- "Думаю..." thinking indicator while processing
- `/tasks` command for task queries
- **Periodic task monitoring** - Background monitoring every 30 seconds
- **AI-generated automatic summaries** - Natural language summaries delivered every 2 minutes
- **Subscription management** - Users can opt-in/opt-out of periodic summaries
- Current date automatically provided to model
- MCP usage indicator ("✓ MCP was used")
- Automatic history clearing on overflow
- Secure credential storage
- Multi-user concurrent support
- Real error messages displayed to user

## Installation

### Prerequisites
- Python 3.14+
- Telegram bot token (from @BotFather)
- OpenRouter API key (from openrouter.ai)
- Weeek API access token (configured in weeek_api.py)

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
5. Start periodic task monitor (30s fetching, 2min summaries)
6. Begin accepting user messages

### Test MCP Server Standalone (Optional)

```bash
python server.py
```

Server communicates via stdio (standard input/output).

## Usage

### Telegram Bot Commands

- `/start` - Start conversation and show welcome message
- `/tasks [query]` - Retrieve and query tasks from Weeek task tracker
- `/subscribe` - Enable periodic task summaries every 2 minutes
- `/unsubscribe` - Disable periodic task summaries

### Command Behavior

The `/tasks` command:
- Extracts user query after the command
- Does NOT add `/tasks` itself to conversation history
- Adds only the query to conversation history
- Instructs the model to use the `get_tasks` tool
- Displays real error messages from API failures

### Example Conversations

**User:** `/tasks show me what's in progress`

**Bot:** Думаю...

**Bot:** You have 1 task in progress:
- Implement authentication (ID: 12345)

✓ MCP was used

---

**User:** `/tasks list all my tasks`

**Bot:** Думаю...

**Bot:** Here are all your tasks:

**Backlog:**
- Write documentation (ID: 12346)

**In progress:**
- Implement authentication (ID: 12345)

**Done:**
- Deploy to production (ID: 12347)

✓ MCP was used

---

**User:** `/tasks what tasks are done?`

**Bot:** Думаю...

**Bot:** You have 1 completed task:
- Deploy to production (ID: 12347)

✓ MCP was used

---

**User:** `/subscribe`

**Bot:** ✅ You will now receive task summaries every 2 minutes.

---

**User:** receives automatic summary after 2 minutes

**Bot:** 📊 Task Updates (Last 2 minutes):

✨ New tasks:
  • Fix login bug (ID: 12348) - Backlog

🔄 State changes:
  • Implement authentication (ID: 12345): In progress → Done

No title or deletion changes detected.

## Periodic Task Monitoring

The bot includes a background monitoring system that tracks task changes in real-time:

### How It Works

1. **Background Fetching (Every 30 seconds)**
   - Bot automatically calls `get_tasks` via MCP
   - Saves task snapshot to `client/tasks_snapshot.json` **only if snapshot doesn't exist**
   - This preserves the baseline state for the full 2-minute comparison period
   - Fails silently on errors (logs but doesn't notify users)

2. **Summary Generation (Every 2 minutes)**
   - Compares current state with previous snapshot
   - Detects all changes:
     - New tasks created
     - Tasks deleted
     - State changes (Backlog → In Progress → Done)
     - Title changes
   - **Sends changes to AI model (OpenRouter) for natural language summary**
   - AI generates concise, friendly summary with context
   - Sends summary to all subscribed users
   - Clears snapshot after delivery (fresh start)

3. **User Subscription**
   - All users who interact with bot are tracked
   - Users must explicitly `/subscribe` to receive summaries
   - Users can `/unsubscribe` to stop summaries
   - Subscription state persisted in `client/subscribers.json`

### Summary Message Format

Summaries are **generated by AI** using the OpenRouter model. The AI receives structured change data and produces natural language summaries.

**Example AI-generated summary:**
```
📊 Task Updates (Last 2 minutes):

✨ New tasks:
  • Fix login bug (ID: 12348) - Backlog

🔄 State changes:
  • Implement authentication (ID: 12345): In Progress → Done

Great progress! One task completed and a new bug logged for tracking.
```

**If no changes detected:**
```
📊 Task Updates (Last 2 minutes):

No changes in the last 2 minutes.
```

The AI adapts the summary style based on the changes, providing context and insights beyond just listing changes.

### Key Features

- **Always-on monitoring** - Runs automatically in background
- **Always sends summaries** - Even if no changes detected
- **Silent failures** - MCP errors logged but users not notified
- **Fresh start on restart** - No state loaded from previous run
- **Per-user opt-in** - Users control their own subscriptions

## Configuration

### Server Configuration

Edit `weeek_api.py` constants:
- `WEEEK_API_BASE_URL` - Weeek API base URL
- `WEEEK_API_TOKEN` - Bearer token for authentication
- `BOARD_COLUMN_STATE_MAP` - Mapping from boardColumnId to state names

### Client Configuration

Edit `client/config.py`:
- `OPENROUTER_MODEL` - AI model to use
- `MAX_CONVERSATION_HISTORY` - Message limit per user (default: 50)
- `TOOL_CALL_TIMEOUT` - MCP tool timeout (default: 30s)
- `WELCOME_MESSAGE` - Bot greeting
- `MCP_USED_INDICATOR` - Tool usage indicator
- `TASK_FETCH_INTERVAL` - Seconds between task fetches (default: 30)
- `SUMMARY_INTERVAL` - Seconds between summaries (default: 120)
- `TASKS_SNAPSHOT_FILE` - Task snapshot JSON file name
- `SUBSCRIBERS_FILE` - Subscribers JSON file name

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
2025-12-18 01:45:23 - INFO - User 12345: /tasks command: /tasks show me what's in progress
2025-12-18 01:45:24 - INFO - User 12345: Executing tool get_tasks
2025-12-18 01:45:24 - INFO - Fetching tasks from Weeek API
2025-12-18 01:45:26 - INFO - Successfully retrieved 3 tasks
```

## Error Handling

### User-Facing Errors
- Real error messages from Weeek API are shown to the user
- Example: "HTTP 401: Unauthorized - Invalid API token"
- Example: "Network error: Connection timeout"

### Logged Errors
- Full exception traceback
- Request/response context
- User and session information
- API error details

## Security

### Credentials
- Never commit `.env` file to git
- All credentials loaded from environment variables
- Weeek API token hardcoded in `weeek_api.py` (for this implementation)
- `.gitignore` excludes sensitive files

### MCP Server
- Runs locally as subprocess
- Accesses Weeek API via HTTPS
- Stdio transport only

## Technology Stack

### Server
- **MCP SDK** - Model Context Protocol implementation
- **httpx** - Async HTTP client for Weeek API

### Client
- **python-telegram-bot** - Telegram bot framework
- **MCP SDK** - MCP client implementation
- **httpx** - OpenRouter API client
- **python-dotenv** - Environment variable management

## Conversation Flow

### Standard Message Flow
1. User sends message to Telegram bot
2. Bot shows "Думаю..." indicator
3. Bot adds message to user's history
4. Bot checks if history limit reached (50 messages)
5. Bot prepends system prompt with current date
6. Bot sends conversation to OpenRouter with available tools
7. OpenRouter decides if tool call needed
8. If tool needed:
   - Bot calls MCP server via subprocess
   - Server calls Weeek API
   - Server maps boardColumnId to state names
   - Server returns formatted result
   - Bot sends result back to OpenRouter
   - OpenRouter generates final response
9. Bot deletes "Думаю..." indicator
10. Bot sends final response to user
11. If MCP was used, appends "✓ MCP was used"
12. Bot stores assistant response in history

### /tasks Command Flow
1. User sends `/tasks [query]` to Telegram bot
2. Bot extracts query (text after `/tasks`)
3. Bot does NOT add `/tasks` to conversation history
4. Bot adds only the query to conversation history
5. Bot shows "Думаю..." indicator
6. Bot sends conversation to OpenRouter with force_tool_use=True
7. System prompt instructs model to use get_tasks tool
8. Model calls get_tasks tool
9. MCP server fetches tasks from Weeek API
10. Bot sends result back to OpenRouter
11. OpenRouter generates formatted response
12. Bot deletes "Думаю..." indicator
13. Bot sends response with "✓ MCP was used" indicator
14. Bot stores assistant response in history

## System Prompt

### For /tasks Command:
```
Current date: YYYY-MM-DD. All dates must be calculated relative to this date.

IMPORTANT INSTRUCTIONS:
- You are a task management assistant with access to the user's tasks via the get_tasks tool.
- ALWAYS use the get_tasks tool when the user asks about their tasks.
- The tool provides real-time task data from Weeek task tracker.
- After retrieving tasks, present them in a clear, organized format.
- Tasks have three states: Backlog, In progress, and Done.
- Use the tool immediately to get current task information.
```

### For Regular Messages:
```
Current date: YYYY-MM-DD. All dates must be calculated relative to this date.

You are a helpful assistant with access to task management tools. If the user asks about tasks, use the get_tasks tool to retrieve current task information.
```

This ensures the model has temporal context and knows when to use task tools.

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
- Check Weeek API availability and token validity
- Review MCP server logs

### Tool calls failing
- Check MCP server subprocess is running
- Verify Weeek API token is correct
- Check network connectivity to api.weeek.net
- Review timeout settings

### Authentication errors
- Verify WEEEK_API_TOKEN in weeek_api.py is correct
- Check token has not expired
- Ensure token has proper permissions in Weeek workspace

## Project Statistics

- **Languages:** Python 3.14
- **Total Files:** 11 Python modules
- **MCP Tools:** 1 (get_tasks)
- **API Integrations:** 3 (Telegram, OpenRouter, Weeek)
- **Transport:** stdio (MCP), HTTPS (APIs)

## Future Enhancements

Potential improvements:
- Add more MCP tools (create task, update task, delete task)
- Support filtering by project/workspace
- Add task search by keyword
- Implement task assignment and reassignment
- Add due date management
- Support task priority levels
- Add task comments and attachments
- Implement task notifications
- Support custom task fields
- Add task analytics and reporting

## License

This project demonstrates MCP integration with AI-powered conversational interfaces.

## Credits

- Weeek API for task management data
- Anthropic for MCP protocol specification
- OpenRouter for AI model access
- Python-telegram-bot for Telegram integration
