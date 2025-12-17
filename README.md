# Task Tracker MCP Server

Local MCP server providing task data via Weeek API.

## Features

- Single tool: `get_tasks`
- Returns task ID, title, and state (Backlog, In progress, Done)
- No input parameters required
- Stdio transport for local integration

## Requirements

- Python 3.14+
- Dependencies listed in `requirements.txt`
- Weeek API access token (configured in `weeek_api.py`)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the Server

```bash
python server.py
```

The server runs on stdio transport and communicates via standard input/output.

## Tool Specification

### `get_tasks`

**Description:** Retrieves all tasks from Weeek task tracker.

**Input Parameters:**
- None (empty object)

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

**Error Response:**
```json
{
  "error": "HTTP 401: Unauthorized - Invalid API token"
}
```

## Project Structure

```
.
├── server.py           # Main MCP server
├── weeek_api.py        # Weeek task tracker API integration
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Integration

This server is designed for integration with MCP clients (e.g., Telegram bots with OpenRouter models) running on the same machine via stdio transport.
