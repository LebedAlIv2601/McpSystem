# Multi-MCP Telegram Bot System

Complete system for task management and mobile automation via Telegram bot using multiple MCP (Model Context Protocol) servers and OpenRouter AI.

## Project Overview

This project consists of two main components:
1. **Multiple MCP Servers** - Three specialized MCP servers providing different capabilities:
   - Weeek task tracker integration
   - Random facts generator
   - Mobile device automation (Android/iOS)
2. **Telegram Bot Client** - AI-powered bot using OpenRouter that connects to all MCP servers simultaneously

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
│ - Handles /tasks, /fact commands        │
│ - Handles /subscribe command            │
│ - Manages conversation history          │
│ - Shows "Думаю..." indicator            │
└──────┬──────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────┐
│ OpenRouter API                          │
│ Model: nex-agi/deepseek-v3.1            │
│ - Processes natural language            │
│ - Decides when to use tools (21 total)  │
└──────┬──────────────────────────────────┘
       │ (when tool needed)
       ↓
┌─────────────────────────────────────────┐
│ MCP Manager (mcp_manager.py)            │
│ - Manages 3 server subprocesses         │
│ - Routes tool calls to correct server   │
│ - Merges tools from all servers         │
└──────┬──────────────────────────────────┘
       │
       ├──────────────────┬───────────────────────┐
       ↓                  ↓                       ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
│ Weeek Tasks  │  │ Random Facts │  │ Mobile MCP           │
│ MCP Server   │  │ MCP Server   │  │ (Node.js/npx)        │
│ (Python)     │  │ (Python)     │  │ @mobilenext/         │
│              │  │              │  │ mobile-mcp           │
│ Tool:        │  │ Tool:        │  │                      │
│ - get_tasks  │  │ - get_fact   │  │ Tools (19):          │
└──────┬───────┘  └──────────────┘  │ - list_devices       │
       │                             │ - launch_app         │
       ↓                             │ - screenshot         │
┌──────────────┐                     │ - tap/swipe/type     │
│ Weeek API    │                     │ - press_button       │
│              │                     │ - etc.               │
└──────────────┘                     └──────────────────────┘

┌──────────────────────────────────────────┐
│ Parallel Background Process:             │
│                                           │
│ ┌────────────────────────────────────┐   │
│ │ Scheduler (client/scheduler.py)    │   │
│ │ - Fetches tasks every 30 seconds   │   │
│ │ - Sends summaries every 2 minutes  │   │
│ │ - Manages subscriptions            │   │
│ └────────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

## System Components

### 1. MCP Servers

The system integrates three specialized MCP servers that run simultaneously:

#### 1.1 Weeek Tasks MCP Server (mcp_tasks/)

**Purpose:** Provide task data from Weeek task tracker via MCP protocol

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

#### 1.2 Random Facts MCP Server (mcp_facts/)

**Purpose:** Provide random interesting facts via MCP protocol

**Files:**
- `server.py` - Main MCP server with stdio transport
- `requirements.txt` - Server dependencies

**Tool Provided:**
- `get_fact` - Returns a random fact

#### 1.3 Mobile Automation MCP Server (External NPM Package)

**Purpose:** Provide mobile device automation capabilities for Android and iOS

**Package:** `@mobilenext/mobile-mcp@latest` (installed via npx)

**Repository:** https://github.com/mobile-next/mobile-mcp

**Prerequisites:**
- Node.js v22+
- Android Platform Tools (adb) for Android automation
- Xcode Command Line Tools for iOS automation (optional)

**Tools Provided (19 total):**
- `mobile_list_available_devices` - List connected devices/emulators
- `mobile_list_apps` - List installed applications
- `mobile_launch_app` - Launch application by package/bundle ID
- `mobile_terminate_app` - Terminate running application
- `mobile_install_app` - Install application from APK/IPA
- `mobile_uninstall_app` - Uninstall application
- `mobile_get_screen_size` - Get device screen dimensions
- `mobile_click_on_screen_at_coordinates` - Tap at specific coordinates
- `mobile_double_tap_on_screen` - Double tap at coordinates
- `mobile_long_press_on_screen_at_coordinates` - Long press at coordinates
- `mobile_list_elements_on_screen` - List UI elements with coordinates
- `mobile_press_button` - Press hardware buttons (HOME, BACK, VOLUME, etc.)
- `mobile_open_url` - Open URL in browser
- `mobile_swipe_on_screen` - Swipe gesture
- `mobile_type_keys` - Type text input
- `mobile_save_screenshot` - Save screenshot to file
- `mobile_take_screenshot` - Take screenshot and return base64
- `mobile_set_orientation` - Set screen orientation (portrait/landscape)
- `mobile_get_orientation` - Get current screen orientation

**Capabilities:**
- Cross-platform automation (Android & iOS)
- Accessibility-first approach using native view hierarchies
- Screenshot-based automation fallback
- Real device and emulator/simulator support
- Deterministic tool application for reliable automation

### 2. Telegram Bot Client (client/ Directory)

**Purpose:** Provide conversational interface for task management, information, and mobile automation

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
- **Up to 15 chained tool calls per conversation** - Increased from 5 for complex multi-step operations
- "Думаю..." thinking indicator while processing
- `/tasks` command for task queries
- `/fact` command for random facts
- `/docs_embed` command for document embeddings generation
- **Periodic task monitoring** - Background monitoring every 30 seconds
- **AI-generated automatic summaries** - Natural language summaries delivered every 2 minutes
- **Subscription management** - Users can opt-in/opt-out of periodic summaries
- **Mobile automation support** - 19 tools for Android/iOS device control
- **Embeddings generation** - Create vector embeddings from markdown documents using Ollama
- Current date automatically provided to model
- MCP usage indicator ("✓ MCP was used")
- Automatic history clearing on overflow
- Secure credential storage
- Multi-user concurrent support
- Real error messages displayed to user

## Installation

### Prerequisites
- Python 3.14+
- Node.js v22+ (for mobile-mcp server)
- Android Platform Tools (adb) for mobile automation
- Telegram bot token (from @BotFather)
- OpenRouter API key (from openrouter.ai)
- Weeek API access token (configured in mcp_tasks/weeek_api.py)
- **Ollama with nomic-embed-text model** (optional, for `/docs_embed` command)

### Setup Steps

1. **Clone repository and navigate to project:**
```bash
cd /path/to/McpSystem
```

2. **Install Node.js v22+ (if not installed):**
```bash
# Using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.zshrc  # or ~/.bashrc
nvm install 22
nvm use 22

# Verify installation
node --version  # Should show v22.x.x
```

3. **Verify Android Platform Tools (for mobile automation):**
```bash
adb --version  # Should show adb version
```

4. **Create and activate virtual environment:**
```bash
python3.14 -m venv venv
source venv/bin/activate  # On macOS/Linux
```

5. **Install MCP server dependencies:**
```bash
# Install dependencies for Python MCP servers
pip install -r requirements.txt

# mobile-mcp will be automatically installed via npx on first run
```

6. **Install client dependencies:**
```bash
pip install -r client/requirements.txt
```

7. **Configure environment variables:**
```bash
cd client
cp .env.example .env
# Edit .env and add your credentials:
# TELEGRAM_BOT_TOKEN=your_token_here
# OPENROUTER_API_KEY=your_key_here
```

## Running the System

### Start Telegram Bot (Automatically Starts All MCP Servers)

**macOS users:** Add OpenMP workaround to avoid conflicts:
```bash
echo 'export KMP_DUPLICATE_LIB_OK=TRUE' >> ~/.zshrc
source ~/.zshrc
```

**Start the bot:**
```bash
cd client
../venv/bin/python main.py
```

The bot will:
1. Start all 3 MCP servers as subprocesses:
   - Weeek Tasks MCP (Python)
   - Random Facts MCP (Python)
   - Mobile MCP (Node.js via npx)
2. Connect MCP client to all servers via stdio
3. Fetch available tools from all servers (21 total tools)
4. Start Telegram bot polling
5. Start periodic task monitor (30s fetching, 2min summaries)
6. Begin accepting user messages

**Note:** First run may take 30-40 seconds while mobile-mcp downloads and initializes.

### Test MCP Servers Standalone (Optional)

**Weeek Tasks Server:**
```bash
python mcp_tasks/server.py
```

**Random Facts Server:**
```bash
python mcp_facts/server.py
```

**Mobile MCP Server:**
```bash
npx -y @mobilenext/mobile-mcp@latest
```

All servers communicate via stdio (standard input/output).

## Usage

### Telegram Bot Commands

- `/start` - Start conversation and show welcome message
- `/tasks [query]` - Retrieve and query tasks from Weeek task tracker
- `/subscribe` - Enable periodic task summaries every 2 minutes
- `/unsubscribe` - Disable periodic task summaries
- `/rag [true|false|on|off|1|0|yes|no]` - Enable or disable RAG (Retrieval Augmented Generation) mode
- `/docs_embed` - Generate embeddings for all markdown files in docs/ folder and create FAISS index

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

---

**User:** List available Android devices

**Bot:** Думаю...

**Bot:** Here are the available Android devices:

1. emulator-5554 (Android SDK built for x86_64)
   - Status: Online
   - Android Version: 13

✓ MCP was used

---

**User:** Take a screenshot of the device and show me what's on screen

**Bot:** Думаю...

**Bot:** I've taken a screenshot of the device. The screen shows:
- System UI with status bar at the top
- Home screen with app launcher icons
- Navigation bar at the bottom

Screenshot saved.

✓ MCP was used

---

**User:** Open Chrome on the device and navigate to google.com

**Bot:** Думаю...

**Bot:** I've launched Chrome browser and navigated to google.com. The page loaded successfully.

✓ MCP was used

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

## Embeddings Generation

The bot includes a document embeddings generation feature that processes markdown files from the `docs/` folder using local Ollama AI.

### Prerequisites

- **Ollama** must be installed and running on `http://localhost:11434`
- **nomic-embed-text model** must be available in Ollama

To install Ollama and the model:
```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the nomic-embed-text model
ollama pull nomic-embed-text

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### How It Works

1. **User triggers command** - User sends `/docs_embed` to bot
2. **Thinking indicator** - Bot displays "Думаю..." message
3. **Document processing**:
   - Reads all `.md` files from top-level `docs/` directory (no subdirectories)
   - Chunks each file by paragraphs (split by double newlines `\n\n`)
   - Logs chunk processing: `"Processing {filename}: {chunk_count} chunks"`
   - For each chunk, logs: `"Chunk {index}/{total}: {first_50_chars}..."`
4. **Embedding generation**:
   - Sends each chunk to Ollama API at `http://localhost:11434/api/embeddings`
   - Uses `nomic-embed-text` model (768-dimensional embeddings)
   - Receives embedding vector for each chunk
5. **FAISS index creation**:
   - Creates FAISS IndexFlatIP with normalized vectors
   - Saves index to `client/faiss_index.bin`
   - Saves metadata to `client/faiss_metadata.json`
   - Overwrites existing index if present
   - Enables RAG (Retrieval Augmented Generation) functionality
6. **JSON creation**:
   - Creates JSON file with timestamp: `embeddings_YYYY-MM-DD_HH-MM-SS.json`
   - Structure: `[{"text": "chunk content", "embedding": [0.123, ...]}, ...]`
7. **File delivery**:
   - Deletes "Думаю..." thinking indicator
   - Sends JSON file to user via Telegram
   - Cleans up temporary file after sending

### Output Format

The generated JSON file contains an array of objects, each with:
- `text` (string) - The chunk text content
- `embedding` (array of floats) - 768-dimensional embedding vector

**Example structure:**
```json
[
  {
    "text": "This is the first paragraph from the markdown file.\n\nIt contains some information.",
    "embedding": [0.123, -0.456, 0.789, ...]
  },
  {
    "text": "This is the second paragraph.\n\nIt contains different information.",
    "embedding": [0.234, -0.567, 0.890, ...]
  }
]
```

### Error Handling

The `/docs_embed` command handles errors gracefully:

1. **Ollama not available**:
   - Deletes thinking indicator
   - Sends: `"❌ Failed to connect to Ollama at http://localhost:11434. Please ensure Ollama is running with the nomic-embed-text model."`

2. **No markdown files found**:
   - Deletes thinking indicator
   - Sends: `"❌ No markdown files found in docs/ directory."`

3. **Other errors**:
   - Deletes thinking indicator
   - Sends: `"❌ Error generating embeddings: {error_message}"`
   - Logs full traceback for debugging

### Logging

The embeddings module logs:
- **INFO**: File discovery, chunk counts, processing summary
- **DEBUG**: Individual chunk processing (first 50 characters only)
- **ERROR**: API failures, file errors, exceptions

**Example log output:**
```
2025-12-22 15:30:45 - INFO - Found 2 markdown files in docs/
2025-12-22 15:30:45 - INFO - Processing history1.md: 5 chunks
2025-12-22 15:30:45 - DEBUG - Chunk 1/5: This is the first paragraph from the markdo...
2025-12-22 15:30:46 - DEBUG - Chunk 2/5: This is the second paragraph. It contains...
2025-12-22 15:30:50 - INFO - Processing history2.md: 3 chunks
2025-12-22 15:30:52 - INFO - Successfully generated 8 embeddings
2025-12-22 15:30:52 - INFO - Saved embeddings to /path/to/embeddings_2025-12-22_15-30-52.json
```

### Use Cases

Generated embeddings can be used for:
- **Semantic search** - Find relevant documents by meaning, not just keywords
- **Document similarity** - Compare documents by content similarity
- **RAG systems** - Retrieval-Augmented Generation for AI chatbots
- **Clustering** - Group similar documents together
- **Question answering** - Build knowledge bases for question-answering systems

## RAG (Retrieval Augmented Generation)

The bot includes a RAG system that enhances AI responses with context from your document embeddings. When enabled, the bot retrieves relevant document chunks and includes them in the query to provide more contextual, informed answers.

### Prerequisites

- **Ollama** must be installed and running on `http://localhost:11434`
- **nomic-embed-text model** must be available in Ollama
- **Document embeddings** must be generated first using `/docs_embed`
- **FAISS index** is created automatically by `/docs_embed` command
- **sentence-transformers** library for cross-encoder reranking (`pip install sentence-transformers>=2.2.0`)

### How RAG Works (4-Stage Pipeline)

The RAG system uses a sophisticated 4-stage retrieval pipeline with filtering and reranking:

**Stage 1: Query Embedding Generation**
1. User enables RAG mode with `/rag true`
2. User sends a query to the bot
3. Bot generates 768-dimensional embedding using Ollama's `nomic-embed-text` model

**Stage 2: FAISS Retrieval & Filtering**
4. Bot searches FAISS index for top-10 most similar document chunks
5. Applies cosine similarity threshold filter (≥ 0.71)
6. Only chunks passing the threshold proceed to reranking
7. If no chunks pass filter, falls back to standard query

**Stage 3: Cross-Encoder Reranking**
8. Filtered chunks are reranked using BGE reranker model (`BAAI/bge-reranker-base`)
9. Cross-encoder computes relevance scores for each query-document pair
10. Chunks are reordered by relevance (most relevant first)
11. Top-3 reranked chunks are selected for context

**Stage 4: Query Augmentation**
12. Selected chunks are prepended to the query:
   ```
   Context: [[chunk1]] [[chunk2]] [[chunk3]]

   Query: [[user's original message]]
   ```
13. Augmented query is sent to OpenRouter AI model
14. Model generates response using both query and retrieved context
15. Only the original user message (not augmented version) is stored in conversation history

### RAG State Management

- **Per-user state** - RAG mode is tracked separately for each user
- **Persistent state** - RAG preferences survive bot restarts (stored in `client/rag_state.json`)
- **Independent control** - Each user can enable/disable RAG independently

### FAISS Index

- **Storage location** - `client/faiss_index.bin` (FAISS binary) and `client/faiss_metadata.json` (chunk texts)
- **Index type** - `IndexFlatIP` (Inner Product) with normalized vectors for cosine similarity
- **Similarity metric** - Cosine similarity (values from -1 to 1, where 1 = identical)
- **Top-k retrieval** - Retrieves top-10 chunks (configurable via `RAG_RETRIEVAL_TOP_K`)
- **Similarity threshold** - Filters chunks with cosine similarity < 0.71 (configurable via `SIMILARITY_THRESHOLD`)
- **Regeneration** - Index is overwritten each time `/docs_embed` is called

### RAG Commands

**Enable RAG:**
```
/rag true
/rag on
/rag 1
/rag yes
```

**Disable RAG:**
```
/rag false
/rag off
/rag 0
/rag no
```

### RAG Workflow Example

**Step 1: Generate embeddings**
```
User: /docs_embed
Bot: Думаю...
Bot: [Sends embeddings JSON file]
```
*This creates both JSON file and FAISS index*

**Step 2: Enable RAG**
```
User: /rag true
Bot: ✅ RAG mode enabled. Your queries will use document context.
```

**Step 3: Ask questions with context**
```
User: How does the task monitoring system work?
Bot: Думаю...
Bot: Based on the documentation, the task monitoring system works as follows:
[Detailed answer using context from docs/]
```

### RAG Behavior

**When RAG is enabled:**
- Bot retrieves top-10 similar chunks from FAISS index
- Filters chunks with similarity score ≥ 0.71
- Reranks filtered chunks using cross-encoder
- Selects top-3 reranked chunks for context
- Chunks are prepended to user query
- AI model receives both context and query
- Responses are more accurate and contextual

**When RAG is disabled:**
- Bot sends queries directly to AI model
- No document context is retrieved
- Standard conversational mode (default behavior)

**When RAG is enabled but no embeddings exist:**
- Bot logs warning: `"RAG enabled but no FAISS index found"`
- Query is sent without context (fallback to standard mode)
- No error shown to user

**When no chunks pass similarity threshold:**
- Bot logs warning: `"No chunks passed similarity threshold"`
- Query is sent without context (fallback to standard mode)
- Detailed logging shows which chunks were filtered

### Error Handling

**Ollama unavailable during query:**
- Logs error and falls back to standard query
- Warning: `"Falling back to standard query due to Ollama error"`
- User receives normal response without RAG context

**FAISS index corrupted:**
- Logs error and falls back to standard query
- User may need to regenerate embeddings with `/docs_embed`

**Reranking fails:**
- Logs error: `"Reranking failed: {error}"`
- Falls back to FAISS-ranked chunks (uses top-3 from similarity search)
- User receives response with FAISS-ranked context
- Common causes: model not downloaded, sentence-transformers not installed

**No embeddings when enabling RAG:**
- Bot warns: `"⚠️ RAG mode enabled, but no embeddings found. Use /docs_embed first, or queries will be sent without context."`
- RAG mode is still enabled, but queries fall back to standard mode until embeddings are created

**sentence-transformers not installed:**
- Reranker initialization fails on first query
- Error: `"sentence-transformers not installed"`
- Install with: `pip install sentence-transformers>=2.2.0`
- Falls back to FAISS-ranked chunks until installed

### Logging

**Comprehensive 4-Stage Pipeline Logging:**

The RAG system includes detailed logging for each pipeline stage with actual data:

**Stage 1 - Query Embedding:**
- Ollama endpoint and model
- Embedding dimension (768)
- Embedding sample values (first 10)
- L2 norm of embedding vector

**Stage 2 - FAISS Retrieval & Filtering:**
- Retrieval parameters (top_k=10, threshold=0.71)
- Raw search results with similarity scores
- Filtering results (chunks passed/filtered)
- Pass rate percentage
- Score range and mean for passed chunks

**Stage 3 - Cross-Encoder Reranking:**
- Reranker model name (BAAI/bge-reranker-base)
- Input chunk count
- Cross-encoder relevance scores for all chunks
- Reranked order with scores
- Top-3 selection with final scores

**Stage 4 - Query Augmentation:**
- Original query length
- Context length
- Augmented query length
- Expansion ratio
- Full augmented query text

**Pipeline Completion:**
- Summary of all 4 stages
- Chunk counts at each stage
- Ready-to-send status

**Logging levels:**
- INFO: Pipeline stages, summaries, chunk counts
- DEBUG: Full chunk texts, embedding vectors, detailed scores
- ERROR: Failures with full stack traces

**Example log output:**
```
================================================================================
User 12345: RAG PIPELINE STARTED
================================================================================
────────────────────────────────────────────────────────────────
User 12345: STEP 1 - QUERY EMBEDDING GENERATION
────────────────────────────────────────────────────────────────
User 12345: ✓ Embedding generated successfully
User 12345: Embedding dimension: 768
────────────────────────────────────────────────────────────────
User 12345: STEP 2 - FAISS RETRIEVAL & FILTERING
────────────────────────────────────────────────────────────────
FAISS: Retrieved 6 chunks (after filtering threshold >= 0.71)
FAISS: Pass rate: 60.0%
────────────────────────────────────────────────────────────────
User 12345: STEP 3 - CROSS-ENCODER RERANKING
────────────────────────────────────────────────────────────────
RERANKER: ✓ Reranking complete
RERANKER: Score range: [0.156789, 0.945678]
────────────────────────────────────────────────────────────────
User 12345: STEP 4 - QUERY AUGMENTATION
────────────────────────────────────────────────────────────────
User 12345: Augmentation statistics:
  - context_chunks: 3
  - expansion_ratio: 42.87x
================================================================================
User 12345: RAG PIPELINE COMPLETED SUCCESSFULLY
================================================================================
```

### Use Cases

**Documentation Q&A:**
- Enable RAG after indexing project documentation
- Ask questions about system architecture, APIs, workflows
- Get answers grounded in actual documentation

**Code assistance:**
- Index code documentation and technical specs
- Ask implementation questions
- Receive contextually accurate guidance

**Knowledge base:**
- Index company policies, procedures, guides
- Query specific information
- Get answers directly from indexed sources

### Technical Details

**Embedding model:**
- `nomic-embed-text` via Ollama
- 768-dimensional vectors
- L2 normalization for cosine similarity

**Chunking strategy:**
- Documents split by paragraphs (double newlines `\n\n`)
- Each chunk embedded independently
- Chunks stored with full text in metadata

**Retrieval algorithm (Stage 2):**
- Top-10 chunks retrieved per query (configurable via `RAG_RETRIEVAL_TOP_K`)
- Cosine similarity via FAISS IndexFlatIP
- Similarity threshold filter: ≥ 0.71 (configurable via `SIMILARITY_THRESHOLD`)
- Only chunks passing threshold proceed to reranking

**Reranking algorithm (Stage 3):**
- Model: `BAAI/bge-reranker-base` (~280MB)
- Architecture: Cross-encoder (query-document pairs)
- Framework: sentence-transformers library
- Scores: Relevance scores (higher = more relevant)
- Selection: Top-3 highest scoring chunks (configurable via `RAG_FINAL_TOP_K`)
- Lazy initialization: Model downloads on first use
- Fallback: Uses FAISS ranking if reranking fails

**Context format:**
- Chunks wrapped in double brackets: `[[chunk text]]`
- Concatenated with spaces between
- Prepended to query with "Context:" and "Query:" labels

**Performance characteristics:**
- FAISS search: ~5-10ms for 100 chunks
- Reranking: ~50-200ms for 10 chunks (depends on chunk length)
- Total pipeline: ~100-300ms end-to-end
- First query slower (~2-3s) due to model download

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

**RAG Configuration:**
- `RERANKER_MODEL` - Reranker model name (default: "bge-reranker-base")
- `SIMILARITY_THRESHOLD` - Minimum cosine similarity (default: 0.71)
- `RAG_RETRIEVAL_TOP_K` - Initial FAISS retrieval count (default: 10)
- `RAG_FINAL_TOP_K` - Final chunks after reranking (default: 3)

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

### MCP Servers
- **MCP SDK (Python)** - Model Context Protocol implementation for Python servers
- **httpx** - Async HTTP client for Weeek API
- **@mobilenext/mobile-mcp** - Node.js-based mobile automation MCP server

### Client
- **python-telegram-bot** - Telegram bot framework
- **MCP SDK (Python)** - MCP client implementation
- **httpx** - OpenRouter API client
- **python-dotenv** - Environment variable management

### External Tools
- **Node.js v22+** - Runtime for mobile-mcp server
- **npx** - Package runner for @mobilenext/mobile-mcp
- **Android Platform Tools (adb)** - Android device communication

## Technical Implementation Notes

### Multi-MCP Connection Management

The system uses `AsyncExitStack` from Python's `contextlib` to manage multiple MCP server connections simultaneously. This approach ensures:

1. **Stable Connections**: All server contexts remain active throughout the bot's lifetime
2. **Clean Lifecycle**: Automatic cleanup when the manager exits
3. **Error Resilience**: Individual server failures don't crash the entire system
4. **Scalability**: Easy to add/remove MCP servers via configuration

**Key implementation (client/mcp_manager.py:25-66):**
```python
async with AsyncExitStack() as stack:
    for server_config in MCP_SERVERS:
        # Enter stdio_client context
        read, write = await stack.enter_async_context(stdio_client(params))
        # Enter ClientSession context
        session = await stack.enter_async_context(ClientSession(read, write))
        self.sessions[server_name] = session
```

This replaces the previous recursive context manager approach that caused premature connection closures.

### Tool Call Iteration Management

The bot supports up to **15 chained tool calls** per user message (configurable in `client/bot.py:329`). This enables complex multi-step operations like:
- List devices → Launch app → Take screenshot → Analyze UI
- Get tasks → Filter by state → Generate summary → Send notification

The iteration limit prevents infinite loops while allowing sophisticated automation workflows.

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

### Mobile MCP errors
- Verify Node.js v22+ is installed: `node --version`
- Ensure adb is accessible: `adb --version`
- Check Android device/emulator is connected: `adb devices`
- First run may take 30-40 seconds while downloading mobile-mcp package
- Mobile-mcp logs appear in stderr during startup
- If mobile tools not available, check MCP manager logs for initialization errors

## Project Statistics

- **Languages:** Python 3.14, Node.js v22+
- **Total Files:** 13+ modules (11 Python, mobile-mcp via npm)
- **MCP Servers:** 3 (Weeek Tasks, Random Facts, Mobile Automation)
- **MCP Tools:** 21 total
  - 1 task management tool (get_tasks)
  - 1 information tool (get_fact)
  - 19 mobile automation tools (mobile_*)
- **API Integrations:** 3 (Telegram, OpenRouter, Weeek)
- **Transport:** stdio (MCP), HTTPS (APIs)
- **Supported Platforms:** Android (via adb), iOS (via Xcode - optional)

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
- mobile-next/mobile-mcp for mobile automation capabilities (https://github.com/mobile-next/mobile-mcp)
