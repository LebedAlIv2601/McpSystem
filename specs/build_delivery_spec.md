# Build Delivery Feature Specification

## Overview

Добавление функциональности автоматической сборки и доставки APK проекта EasyPomodoro через Telegram бота. Пользователь запрашивает сборку в чате, AI распознаёт intent и вызывает MCP tool, после чего система собирает APK на указанной ветке и отправляет файл пользователю.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Flow                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "Собери APK с ветки feature/timer"                                   │
│                    │                                                         │
│                    ▼                                                         │
│  ┌──────────────────────────────────────┐                                   │
│  │         Telegram Bot Client          │                                   │
│  │  - Forwards message to backend       │                                   │
│  └──────────────────┬───────────────────┘                                   │
│                     │ POST /api/chat                                         │
│                     ▼                                                         │
│  ┌──────────────────────────────────────┐                                   │
│  │           Backend Server             │                                   │
│  │  - AI processes message              │                                   │
│  │  - Calls build_apk MCP tool          │                                   │
│  │  - Validates branch existence        │                                   │
│  │  - Triggers GitHub Actions           │                                   │
│  │  - Tracks active builds (in-memory)  │                                   │
│  └──────────────────┬───────────────────┘                                   │
│                     │ Response: {build_request: {workflow_run_id, branch}}  │
│                     ▼                                                         │
│  ┌──────────────────────────────────────┐                                   │
│  │         Telegram Bot Client          │                                   │
│  │  - Sends "Сборка запущена" message   │                                   │
│  │  - Starts polling task               │                                   │
│  │  - Polls GitHub API every 30s        │                                   │
│  │  - Downloads artifact on completion  │                                   │
│  │  - Sends APK to user                 │                                   │
│  └──────────────────────────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Technical Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Build Infrastructure | GitHub Actions | Managed CI/CD, no infrastructure to maintain |
| APK Delivery | GitHub Artifacts API | Native integration, 90-day retention |
| Completion Detection | Polling workflow status | Simple, no webhook setup required |
| Wait UX | One-time message | "Сборка запущена" + final message with APK |
| Cancellation | Not supported | Simplifies implementation |
| Build Type | Debug only | No keystore management needed |
| Branch Input | Free text | AI parses branch from user message |
| Branch Validation | Yes, before trigger | Better UX, immediate feedback on invalid branch |
| Access Control | None | Any bot user can trigger builds |
| Concurrency | Block parallel builds | One active build per user |
| AI Integration | MCP tool → async client task | AI only triggers, client handles polling |
| Token Management | GitHub token in client | Client directly calls GitHub API |
| File Handling | In-memory + temp file | Download to /tmp, send, delete |
| Artifact Format | Gradle structure | app/build/outputs/apk/debug/app-debug.apk in ZIP |
| Error Reporting | Brief message + link | "Сборка упала" + workflow run URL |
| Workflow | Create new | .github/workflows/build-apk.yml |
| Tests in Workflow | No | Only assembleDebug, faster builds |
| Poll Interval | 30 seconds | Balance between responsiveness and API usage |
| Timeout | 15 minutes | Reasonable limit for Android builds |
| APK Naming | Branch + timestamp | EasyPomodoro-feature_login-20240115-1423.apk |
| State Storage | In-memory in backend | Track active builds per user |
| Build History | Not stored | Only active builds in memory |
| JDK Version | JDK 11 | Project requirement |
| APK Size | 20-50MB | Within Telegram 50MB limit |
| PAT Scope | repo (full access) | Simplest setup |
| Default Branch | master | When user doesn't specify |
| Workflow Path | .github/workflows/build-apk.yml | Standard location |
| Repo/Workflow Config | Hardcoded | LebedAlIv2601/EasyPomodoro |
| Extra Info with APK | None | Only APK file |

## Components to Implement

### 1. GitHub Actions Workflow (EasyPomodoro repo)

**File:** `.github/workflows/build-apk.yml`

```yaml
name: Build APK

on:
  workflow_dispatch:
    inputs:
      branch:
        description: 'Branch to build'
        required: true
        default: 'master'

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.inputs.branch }}

      - name: Set up JDK 11
        uses: actions/setup-java@v4
        with:
          java-version: '11'
          distribution: 'temurin'
          cache: gradle

      - name: Grant execute permission for gradlew
        run: chmod +x gradlew

      - name: Build Debug APK
        run: ./gradlew assembleDebug

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: apk
          path: app/build/outputs/apk/debug/app-debug.apk
          retention-days: 7
```

### 2. MCP Tool: build_apk (RAG MCP Server)

**File:** `server/mcp_rag/server.py`

Add new tool `build_apk`:

```python
@server.tool()
async def build_apk(branch: str = "master") -> dict:
    """
    Trigger Android APK build for EasyPomodoro project.

    Args:
        branch: Git branch to build from. Defaults to "master".

    Returns:
        dict with workflow_run_id and branch for client to track.
    """
```

**Tool responsibilities:**
- Validate branch exists via GitHub API
- Check no active build for user (via backend state)
- Trigger workflow_dispatch via GitHub API
- Return workflow_run_id to backend
- Backend includes build_request in /api/chat response

### 3. Backend Changes

**File:** `server/schemas.py`

Extend ChatResponse:

```python
class BuildRequest(BaseModel):
    workflow_run_id: int
    branch: str
    user_id: str

class ChatResponse(BaseModel):
    response: str
    tool_calls_count: int = 0
    mcp_used: bool = False
    build_request: Optional[BuildRequest] = None  # NEW
```

**File:** `server/build_state.py` (NEW)

```python
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ActiveBuild:
    workflow_run_id: int
    branch: str
    started_at: datetime

class BuildStateManager:
    def __init__(self):
        self._active_builds: Dict[str, ActiveBuild] = {}

    def has_active_build(self, user_id: str) -> bool:
        ...

    def start_build(self, user_id: str, workflow_run_id: int, branch: str) -> None:
        ...

    def complete_build(self, user_id: str) -> None:
        ...

    def get_active_build(self, user_id: str) -> Optional[ActiveBuild]:
        ...
```

**File:** `server/chat_service.py`

- Detect build_apk tool call in tool results
- If build_apk was called, include build_request in response
- Check BuildStateManager before allowing build

### 4. Client Changes

**File:** `client/config.py`

Add:
```python
GITHUB_TOKEN: str  # For GitHub API calls
GITHUB_REPO: str = "LebedAlIv2601/EasyPomodoro"
WORKFLOW_FILE: str = "build-apk.yml"
BUILD_POLL_INTERVAL: int = 30  # seconds
BUILD_TIMEOUT: int = 900  # 15 minutes
```

**File:** `client/github_client.py` (NEW)

```python
class GitHubClient:
    async def get_workflow_run_status(self, run_id: int) -> str:
        """Returns: queued, in_progress, completed"""
        ...

    async def get_workflow_run_conclusion(self, run_id: int) -> str:
        """Returns: success, failure, cancelled"""
        ...

    async def download_artifact(self, run_id: int, artifact_name: str) -> bytes:
        """Download and return artifact ZIP content"""
        ...

    async def get_workflow_run_url(self, run_id: int) -> str:
        """Get HTML URL for workflow run"""
        ...
```

**File:** `client/build_handler.py` (NEW)

```python
class BuildHandler:
    def __init__(self, github_client: GitHubClient, bot: Bot):
        ...

    async def handle_build_request(
        self,
        chat_id: int,
        workflow_run_id: int,
        branch: str
    ) -> None:
        """
        1. Send "Сборка запущена, ожидайте" message
        2. Start polling task
        3. On completion: download artifact, extract APK, send to user
        4. On failure: send error message with workflow URL
        5. On timeout: send timeout message
        """

    async def _poll_and_deliver(
        self,
        chat_id: int,
        workflow_run_id: int,
        branch: str
    ) -> None:
        """Background polling task"""
        ...

    def _generate_apk_filename(self, branch: str) -> str:
        """Generate: EasyPomodoro-{branch}-{timestamp}.apk"""
        # Replace / with _ in branch name
        # Format: EasyPomodoro-feature_login-20240115-1423.apk
        ...
```

**File:** `client/bot.py`

Modify message handler:
```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing code ...

    response = await backend_client.send_message(user_id, text)

    # Check for build request
    if response.build_request:
        await build_handler.handle_build_request(
            chat_id=update.effective_chat.id,
            workflow_run_id=response.build_request.workflow_run_id,
            branch=response.build_request.branch
        )

    # Send AI response
    await update.message.reply_text(response.response)
```

## API Flow

### Successful Build

```
1. User → Telegram: "Собери APK с ветки feature/timer"

2. Client → Backend: POST /api/chat
   {
     "user_id": "123456",
     "message": "Собери APK с ветки feature/timer"
   }

3. Backend → MCP: build_apk(branch="feature/timer")

4. MCP → GitHub API: GET /repos/{owner}/{repo}/branches/feature/timer
   (validate branch exists)

5. MCP → Backend: Check no active build for user

6. MCP → GitHub API: POST /repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches
   {
     "ref": "feature/timer",
     "inputs": {"branch": "feature/timer"}
   }

7. MCP → GitHub API: GET /repos/{owner}/{repo}/actions/runs?event=workflow_dispatch
   (get workflow_run_id)

8. Backend → Client:
   {
     "response": "Запускаю сборку с ветки feature/timer...",
     "build_request": {
       "workflow_run_id": 12345,
       "branch": "feature/timer",
       "user_id": "123456"
     }
   }

9. Client → Telegram: "Сборка запущена, ожидайте..."

10. Client → GitHub API: (polling every 30s)
    GET /repos/{owner}/{repo}/actions/runs/12345

11. (After ~5-10 minutes) Status: completed, conclusion: success

12. Client → GitHub API: GET /repos/{owner}/{repo}/actions/runs/12345/artifacts

13. Client → GitHub API: GET /repos/{owner}/{repo}/actions/artifacts/{id}/zip

14. Client: Extract APK from ZIP

15. Client → Telegram: Send document "EasyPomodoro-feature_timer-20240115-1423.apk"

16. Client → Backend: Notify build complete (to clear state)
```

### Failed Build

```
... steps 1-10 same ...

11. Status: completed, conclusion: failure

12. Client → GitHub API: GET /repos/{owner}/{repo}/actions/runs/12345
    (get html_url)

13. Client → Telegram: "Сборка упала. Детали: https://github.com/.../actions/runs/12345"

14. Client → Backend: Notify build complete (to clear state)
```

### Parallel Build Blocked

```
1. User → Telegram: "Собери APK"

2. Client → Backend: POST /api/chat

3. Backend: Check BuildStateManager.has_active_build("123456") → True

4. Backend → Client:
   {
     "response": "У вас уже есть активная сборка. Дождитесь её завершения.",
     "build_request": null
   }

5. Client → Telegram: "У вас уже есть активная сборка. Дождитесь её завершения."
```

## Environment Variables

### Backend (.env)
```
# Existing
BACKEND_API_KEY=...
OPENROUTER_API_KEY=...
GITHUB_TOKEN=...  # Already exists, used for MCP

# No new variables needed (repo/workflow hardcoded)
```

### Client (.env)
```
# Existing
TELEGRAM_BOT_TOKEN=...
BACKEND_URL=...
BACKEND_API_KEY=...

# New
GITHUB_TOKEN=ghp_...  # For GitHub API (artifacts, polling)
```

## Error Handling

| Scenario | Handler | User Message |
|----------|---------|--------------|
| Invalid branch | MCP tool | "Ветка 'xyz' не найдена в репозитории" |
| Active build exists | Backend | "У вас уже есть активная сборка" |
| Workflow trigger failed | MCP tool | "Не удалось запустить сборку: {error}" |
| Build failed | Client | "Сборка упала. Детали: {url}" |
| Build timeout (15 min) | Client | "Сборка превысила таймаут 15 минут. Детали: {url}" |
| Artifact download failed | Client | "Не удалось скачать APK: {error}" |
| Telegram upload failed | Client | "Не удалось отправить APK: {error}" |

## Testing Checklist

- [ ] Trigger build on master branch
- [ ] Trigger build on feature branch
- [ ] Trigger build on non-existent branch (should fail fast)
- [ ] Request build while another is in progress (should be blocked)
- [ ] Build failure handling (introduce compile error)
- [ ] Timeout handling (can simulate with long workflow)
- [ ] APK file naming convention
- [ ] APK successfully received in Telegram and installable

## Security Considerations

1. **GitHub PAT in client:** Token has `repo` scope. Stored in Railway env vars.
2. **No user restriction:** Any bot user can trigger builds. Acceptable for private bot.
3. **No rate limiting:** Relies on GitHub Actions quota. Could be abused if bot goes public.

## Future Improvements (Out of Scope)

- Release builds with signing
- Build flavors support
- Rate limiting per user
- Build queue with multiple concurrent builds
- Webhook-based completion instead of polling
- Build caching
- APK size optimization (ProGuard, etc.)
