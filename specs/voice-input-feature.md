# Voice Input Feature Specification

**Date:** 2026-01-27
**Status:** Ready for Implementation
**Priority:** P1 (High)

---

## 1. Overview

### 1.1 Goal
Enable users to send voice messages to the Telegram bot, which will be converted to text and processed by AI with full conversation context, providing text-based responses.

### 1.2 Scope
- Telegram bot voice message handling (client/)
- Audio format conversion (.oga → .mp3)
- Integration with gpt-audio-mini via OpenRouter
- Full conversation history support (voice + text messages)
- Fast-fail error handling
- Observability (latency, cost, errors)

### 1.3 Non-Scope (Explicitly Excluded)
- MCP tools for voice requests (disabled for stability)
- Streaming audio responses
- Pre-validation of audio quality
- Content moderation (rely on LLM built-in safety)
- Feature flags or gradual rollout (full deployment for all users)

---

## 2. Requirements Summary

### 2.1 User-Facing Requirements

| Requirement | Priority | Details |
|-------------|----------|---------|
| Voice message support | **MUST** | Accept voice messages up to 1 minute duration |
| Transcription display | **MUST** | Show "Вы сказали: ..." as separate message (not in history) |
| Russian language only | **MUST** | Hardcoded ru language for STT |
| Quality > Latency | **SHOULD** | Accuracy prioritized over speed (7-15s acceptable) |
| Silent fail on poor audio | **SHOULD** | Return fallback message if audio unusable |

### 2.2 Technical Requirements

| Requirement | Priority | Details |
|-------------|----------|---------|
| gpt-audio-mini via OpenRouter | **MUST** | Use openrouter.ai/openai/gpt-audio-mini/api |
| .oga → .mp3 conversion | **MUST** | Backend ffmpeg conversion |
| FIFO queue per user_id | **MUST** | Sequential processing per user |
| Conversation history support | **MUST** | Send full text history + audio to model |
| 10 MB file size limit | **MUST** | Reject files >10MB |
| No MCP tools for voice | **MUST** | Disable tool calling for audio requests |
| Fast-fail error handling | **MUST** | No retries, immediate fallback message |

### 2.3 Observability Requirements

| Metric | Type | Purpose |
|--------|------|---------|
| Audio processing latency | **Latency** | Track conversion + API time |
| Audio tokens used | **Cost** | Budget control |
| Error rates by type | **Reliability** | Proactive issue detection |

---

## 3. Architecture

### 3.1 System Components

```
┌──────────────────────────────────────────────────────────────┐
│                      Telegram User                           │
└────────────────────────┬─────────────────────────────────────┘
                         │ (voice message .oga)
                         ↓
┌──────────────────────────────────────────────────────────────┐
│                   Telegram Bot (client/bot.py)               │
│  - handle_voice_message() NEW                                │
│  - Download .oga file via get_file()                         │
│  - Send "🎧 Слушаю..." indicator                             │
│  - POST /api/chat-voice (multipart: audio + user_id)        │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│                Backend Server (server/app.py)                │
│                                                              │
│  NEW Endpoint: POST /api/chat-voice                         │
│  ├─ Accept multipart/form-data (audio file + user_id)      │
│  ├─ File size validation (<10MB)                            │
│  ├─ Call audio_service.process_voice_message()             │
│  └─ Return VoiceResponse (transcription + AI response)      │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│           NEW: AudioService (server/audio_service.py)        │
│                                                              │
│  1. Audio Conversion (ffmpeg):                              │
│     - Convert .oga → .mp3 (via subprocess)                  │
│     - Delete temp files after processing                     │
│                                                              │
│  2. OpenRouter Integration:                                 │
│     - Build messages: system + history + audio              │
│     - Call openrouter_client.audio_completion()             │
│     - Extract transcription + response from API             │
│                                                              │
│  3. User Queue Management:                                  │
│     - FIFO queue per user_id (asyncio.Queue)                │
│     - Block concurrent requests from same user              │
│                                                              │
│  4. History Truncation:                                     │
│     - Keep last N messages if context too large             │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│    OpenRouterClient (server/openrouter_client.py) UPDATED   │
│                                                              │
│  NEW: audio_completion(messages, audio_file_path) method:   │
│  - Prepare multipart/form-data request                      │
│  - Send audio + conversation history                         │
│  - Parse response: { transcription, text_response }         │
│  - Return (transcription, response, audio_tokens_used)      │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

#### 3.2.1 Happy Path: Voice Message → AI Response

```
1. User sends voice message (Telegram)
   ↓
2. Bot downloads .oga file
   ↓
3. Bot sends "🎧 Слушаю..." indicator
   ↓
4. Bot POST /api/chat-voice (multipart: audio + user_id)
   ↓
5. Backend validates file size (<10MB)
   ↓
6. AudioService adds request to user's FIFO queue
   ↓
7. AudioService converts .oga → .mp3 (ffmpeg)
   ↓
8. AudioService builds messages:
   - System prompt (no MCP tools)
   - Conversation history (text only)
   - Audio file (multipart)
   ↓
9. OpenRouterClient sends to gpt-audio-mini
   ↓
10. Model returns: { transcription, response, usage }
   ↓
11. AudioService logs metrics (latency, tokens, cost)
   ↓
12. Backend returns VoiceResponse to bot
   ↓
13. Bot deletes "🎧 Слушаю..." indicator
   ↓
14. Bot sends transcription: "Вы сказали: [transcription]"
   ↓
15. Bot sends AI response (text)
   ↓
16. Bot saves transcription to conversation history (NOT transcription message itself)
```

#### 3.2.2 Error Path: Audio Processing Failure

```
1. User sends voice message
   ↓
2. Bot downloads file
   ↓
3. Backend receives request
   ↓
4. [ERROR at any stage: conversion, API, etc.]
   ↓
5. AudioService logs error + metrics
   ↓
6. Backend returns error response
   ↓
7. Bot deletes "🎧 Слушаю..." indicator
   ↓
8. Bot sends: "❌ Не удалось обработать голосовое сообщение. Попробуйте ещё раз или напишите текстом."
   ↓
9. No history update (failed request not saved)
```

---

## 4. API Specification

### 4.1 New Endpoint: POST /api/chat-voice

**Purpose:** Process voice message and return transcription + AI response.

**Request:**
```http
POST /api/chat-voice
Content-Type: multipart/form-data
X-API-Key: <backend_api_key>

Form fields:
- user_id: string (required)
- audio: file (.oga, .mp3, .wav) (required)
```

**Response (Success 200):**
```json
{
  "transcription": "текст распознанной речи",
  "response": "ответ AI модели",
  "latency_ms": 4532,
  "audio_tokens": 1250,
  "cost_usd": 0.00075
}
```

**Response (Error 400):**
```json
{
  "error": "File too large",
  "detail": "Audio file exceeds 10MB limit"
}
```

**Response (Error 500):**
```json
{
  "error": "Audio processing failed",
  "detail": "ffmpeg conversion error: ..."
}
```

### 4.2 Updated Schema: VoiceRequest / VoiceResponse

**schemas.py additions:**

```python
class VoiceRequest(BaseModel):
    """Request model for voice endpoint."""
    user_id: str = Field(..., description="Unique user identifier")
    # audio: file upload via multipart (not in Pydantic model)

class VoiceResponse(BaseModel):
    """Response model for voice endpoint."""
    transcription: str = Field(..., description="Recognized text from audio")
    response: str = Field(..., description="AI assistant response")
    latency_ms: int = Field(..., description="Processing time in milliseconds")
    audio_tokens: int = Field(default=0, description="Audio tokens consumed")
    cost_usd: float = Field(default=0.0, description="Estimated cost in USD")
```

---

## 5. Implementation Details

### 5.1 Client-Side Changes (client/bot.py)

#### 5.1.1 New Handler: handle_voice_message()

```python
async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages from users."""
    user_id = update.effective_user.id
    voice = update.message.voice

    logger.info(f"User {user_id}: Received voice message (duration={voice.duration}s, size={voice.file_size}B)")

    # Validate duration (max 1 minute)
    if voice.duration > 60:
        await retry_telegram_call(
            update.message.reply_text,
            "❌ Голосовое сообщение слишком длинное. Максимум 1 минута."
        )
        return

    thinking_msg = None

    try:
        # Show processing indicator
        thinking_msg = await retry_telegram_call(update.message.reply_text, "🎧 Слушаю...")

        # Download voice file
        voice_file = await voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()

        # Send to backend
        transcription, response_text = await self.backend_client.send_voice_message(
            user_id=str(user_id),
            audio_bytes=voice_bytes,
            audio_format="oga"  # Telegram voice messages are .oga
        )

        # Delete thinking message
        await retry_telegram_call(thinking_msg.delete)
        thinking_msg = None

        # Send transcription (separate message, not saved to history)
        if transcription:
            await retry_telegram_call(
                update.message.reply_text,
                f"Вы сказали: {transcription}"
            )

        # Send AI response
        if response_text:
            await retry_telegram_call(update.message.reply_text, response_text)
        else:
            await retry_telegram_call(update.message.reply_text, ERROR_MESSAGE)

    except Exception as e:
        logger.error(f"User {user_id}: Error handling voice message: {e}", exc_info=True)
        if thinking_msg:
            try:
                await retry_telegram_call(thinking_msg.delete)
            except Exception:
                pass
        try:
            await retry_telegram_call(
                update.message.reply_text,
                "❌ Не удалось обработать голосовое сообщение. Попробуйте ещё раз или напишите текстом."
            )
        except Exception:
            logger.error(f"User {user_id}: Failed to send error message")
```

#### 5.1.2 Register Handler in run()

```python
# In TelegramBot.run(), after text handler:
self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
```

### 5.2 Backend Client Changes (client/backend_client.py)

#### 5.2.1 New Method: send_voice_message()

```python
async def send_voice_message(
    self,
    user_id: str,
    audio_bytes: bytes,
    audio_format: str = "oga"
) -> Tuple[Optional[str], Optional[str]]:
    """
    Send voice message to backend for processing.

    Args:
        user_id: User identifier
        audio_bytes: Audio file bytes
        audio_format: Audio format (oga, mp3, wav)

    Returns:
        Tuple of (transcription, response_text)
    """
    url = f"{self.backend_url}/api/chat-voice"

    # Prepare multipart form data
    files = {
        "audio": (f"voice.{audio_format}", audio_bytes, f"audio/{audio_format}")
    }
    data = {
        "user_id": user_id
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                url,
                headers={"X-API-Key": self.api_key},
                files=files,
                data=data
            )
            response.raise_for_status()
            result = response.json()

        transcription = result.get("transcription")
        response_text = result.get("response")

        logger.info(f"Voice message processed: latency={result.get('latency_ms')}ms, tokens={result.get('audio_tokens')}")

        return transcription, response_text

    except httpx.HTTPStatusError as e:
        logger.error(f"Backend error: {e.response.status_code} - {e.response.text}")
        return None, None
    except Exception as e:
        logger.error(f"Voice message error: {e}", exc_info=True)
        return None, None
```

### 5.3 Backend Server Changes (server/app.py)

#### 5.3.1 New Endpoint: POST /api/chat-voice

```python
from fastapi import File, Form, UploadFile
from schemas import VoiceResponse
from audio_service import get_audio_service

@router.post(
    "/api/chat-voice",
    response_model=VoiceResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid audio file"},
        500: {"model": ErrorResponse, "description": "Audio processing error"}
    },
    summary="Process voice message",
    description="Convert voice to text and generate AI response with conversation history."
)
async def chat_voice(
    user_id: str = Form(...),
    audio: UploadFile = File(...),
    api_key: str = Depends(verify_api_key),
    audio_service: AudioService = Depends(get_audio_service)
) -> VoiceResponse:
    """
    Process voice message and return transcription + AI response.

    Args:
        user_id: User identifier
        audio: Audio file (.oga, .mp3, .wav)
        api_key: Validated API key
        audio_service: Audio service instance

    Returns:
        VoiceResponse with transcription and response
    """
    logger.info(f"Voice request from user {user_id}, file={audio.filename}, size={audio.size}")

    # Validate file size (10MB limit)
    if audio.size and audio.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file exceeds 10MB limit"
        )

    try:
        # Read audio bytes
        audio_bytes = await audio.read()

        # Process voice message
        result = await audio_service.process_voice_message(
            user_id=user_id,
            audio_bytes=audio_bytes,
            audio_format=audio.filename.split('.')[-1] if audio.filename else "oga"
        )

        return VoiceResponse(**result)

    except Exception as e:
        logger.error(f"Voice processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio processing failed: {str(e)}"
        )
```

### 5.4 New Module: AudioService (server/audio_service.py)

```python
"""Audio processing service for voice messages."""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from collections import defaultdict

from conversation import ConversationManager
from openrouter_client import OpenRouterClient
from profile_manager import get_profile_manager
from config import VOICE_MAX_DURATION_SEC, VOICE_MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)


class AudioService:
    """Service for processing voice messages with audio-to-text and AI response."""

    def __init__(self):
        self.conversation_manager = ConversationManager()
        self.openrouter_client = OpenRouterClient()

        # Per-user FIFO queues for sequential processing
        self.user_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self.user_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def process_voice_message(
        self,
        user_id: str,
        audio_bytes: bytes,
        audio_format: str = "oga"
    ) -> Dict:
        """
        Process voice message: convert audio, send to LLM, return response.

        Args:
            user_id: User identifier
            audio_bytes: Audio file bytes
            audio_format: Audio format (oga, mp3, wav)

        Returns:
            Dict with transcription, response, latency_ms, audio_tokens, cost_usd
        """
        start_time = time.time()

        # Use user-specific lock to ensure FIFO processing
        async with self.user_locks[user_id]:
            return await self._process_voice_internal(user_id, audio_bytes, audio_format, start_time)

    async def _process_voice_internal(
        self,
        user_id: str,
        audio_bytes: bytes,
        audio_format: str,
        start_time: float
    ) -> Dict:
        """Internal processing with temp file management."""
        temp_input_path = None
        temp_output_path = None

        try:
            # Step 1: Save input audio to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}") as temp_input:
                temp_input.write(audio_bytes)
                temp_input_path = temp_input.name

            logger.info(f"User {user_id}: Audio saved to {temp_input_path}")

            # Step 2: Convert to .mp3 if needed
            if audio_format != "mp3":
                temp_output_path = tempfile.mktemp(suffix=".mp3")
                await self._convert_audio_to_mp3(temp_input_path, temp_output_path)
                audio_file_path = temp_output_path
            else:
                audio_file_path = temp_input_path

            logger.info(f"User {user_id}: Audio ready at {audio_file_path}")

            # Step 3: Get conversation history
            conversation_history = self.conversation_manager.get_history(user_id)

            # Step 4: Truncate history if too large (keep last 20 messages)
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]
                logger.info(f"User {user_id}: Truncated history to 20 messages")

            # Step 5: Build system prompt (NO MCP tools)
            system_prompt = self._build_system_prompt(user_id)

            # Step 6: Call OpenRouter with audio + history
            transcription, response_text, audio_tokens = await self.openrouter_client.audio_completion(
                messages=[system_prompt] + conversation_history,
                audio_file_path=audio_file_path,
                language="ru"
            )

            # Step 7: Save transcription to conversation history (NOT the display message)
            if transcription:
                self.conversation_manager.add_message(user_id, "user", transcription)

            if response_text:
                self.conversation_manager.add_message(user_id, "assistant", response_text)

            # Step 8: Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)
            cost_usd = self._calculate_cost(audio_tokens)

            logger.info(f"User {user_id}: Voice processed - latency={latency_ms}ms, tokens={audio_tokens}, cost=${cost_usd:.6f}")

            return {
                "transcription": transcription or "",
                "response": response_text or "Извините, не удалось обработать голосовое сообщение.",
                "latency_ms": latency_ms,
                "audio_tokens": audio_tokens,
                "cost_usd": cost_usd
            }

        except Exception as e:
            logger.error(f"User {user_id}: Audio processing error: {e}", exc_info=True)
            raise

        finally:
            # Cleanup temp files
            if temp_input_path and os.path.exists(temp_input_path):
                os.remove(temp_input_path)
            if temp_output_path and os.path.exists(temp_output_path):
                os.remove(temp_output_path)

    async def _convert_audio_to_mp3(self, input_path: str, output_path: str) -> None:
        """Convert audio file to MP3 using ffmpeg."""
        logger.info(f"Converting {input_path} -> {output_path}")

        # Run ffmpeg in subprocess
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i", input_path,
            "-acodec", "libmp3lame",
            "-ar", "16000",  # 16kHz sample rate (optimal for speech)
            "-ac", "1",  # Mono
            "-b:a", "32k",  # 32 kbps bitrate (sufficient for speech)
            "-y",  # Overwrite output
            output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"ffmpeg error: {stderr.decode()}")
            raise RuntimeError(f"Audio conversion failed: {stderr.decode()}")

        logger.info(f"Audio converted successfully: {output_path}")

    def _build_system_prompt(self, user_id: str) -> Dict:
        """Build system prompt with user personalization (NO MCP tools)."""
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        base_content = f"""Current date: {current_date}.

You are a project consultant for EasyPomodoro Android app (repo: LebedAlIv2601/EasyPomodoro).

**IMPORTANT:** This is a voice input request. You DO NOT have access to code browsing tools.
- Answer based on your general knowledge and the conversation history
- Be concise and helpful
- If you need specific code details, ask the user to send a text message instead

Respond in user's language (Russian)."""

        # Add personalization context if profile exists
        profile_manager = get_profile_manager()
        profile_context = profile_manager.build_context(user_id)
        if profile_context:
            base_content += "\n\n" + profile_context

        return {
            "role": "system",
            "content": base_content
        }

    def _calculate_cost(self, audio_tokens: int) -> float:
        """Calculate cost in USD based on audio tokens."""
        # gpt-audio-mini pricing: $0.60 per 1M audio tokens
        cost_per_token = 0.60 / 1_000_000
        return audio_tokens * cost_per_token


# Global service instance (initialized in main.py)
_audio_service: Optional[AudioService] = None


def get_audio_service() -> AudioService:
    """Get audio service instance."""
    if _audio_service is None:
        raise RuntimeError("Audio service not initialized")
    return _audio_service


def set_audio_service(service: AudioService) -> None:
    """Set audio service instance."""
    global _audio_service
    _audio_service = service
```

### 5.5 OpenRouter Client Updates (server/openrouter_client.py)

#### 5.5.1 New Method: audio_completion()

```python
async def audio_completion(
    self,
    messages: List[Dict[str, str]],
    audio_file_path: str,
    language: str = "ru"
) -> Tuple[Optional[str], Optional[str], int]:
    """
    Send audio completion request to OpenRouter (gpt-audio-mini).

    Args:
        messages: Conversation history (text only)
        audio_file_path: Path to audio file (.mp3)
        language: Language code for transcription

    Returns:
        Tuple of (transcription, response_text, audio_tokens_used)
    """
    headers = {
        "Authorization": f"Bearer {self.api_key}"
    }

    # Build multipart form data
    # According to OpenAI API spec for audio models:
    # - messages: JSON-encoded conversation history
    # - audio: audio file
    # - language: transcription language

    with open(audio_file_path, "rb") as audio_file:
        files = {
            "file": ("audio.mp3", audio_file, "audio/mpeg")
        }

        data = {
            "model": "openai/gpt-audio-mini",  # Specific audio model
            "messages": json.dumps(messages),
            "language": language
        }

        logger.info(f"OpenRouter audio request: model=gpt-audio-mini, messages={len(messages)}, language={language}")

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    files=files,
                    data=data
                )
                response.raise_for_status()
                result = response.json()

            logger.debug(f"OpenRouter audio response: {json.dumps(result, indent=2)}")

            if "choices" not in result or not result["choices"]:
                logger.error("Invalid OpenRouter audio response: no choices")
                return None, None, 0

            choice = result["choices"][0]
            message = choice.get("message", {})

            # Extract transcription and response
            # (Format depends on OpenRouter's implementation of gpt-audio-mini)
            transcription = message.get("transcription") or message.get("content")
            response_text = message.get("content")

            # Extract usage
            usage = result.get("usage", {})
            audio_tokens = usage.get("audio_tokens", 0) or usage.get("prompt_tokens", 0)

            logger.info(f"Audio completion: transcription_len={len(transcription) if transcription else 0}, response_len={len(response_text) if response_text else 0}, tokens={audio_tokens}")

            return transcription, response_text, audio_tokens

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter audio HTTP error: {e}")
            logger.error(f"Response body: {e.response.text}")
            raise

        except Exception as e:
            logger.error(f"OpenRouter audio error: {e}", exc_info=True)
            raise
```

### 5.6 Configuration Updates (server/config.py)

```python
# Voice input settings
VOICE_MAX_DURATION_SEC = 60  # 1 minute
VOICE_MAX_FILE_SIZE_MB = 10
```

### 5.7 Main Application Updates (server/main.py)

```python
from audio_service import AudioService, set_audio_service

# In startup():
async def startup():
    # ... existing MCP initialization ...

    # Initialize audio service
    audio_service = AudioService()
    set_audio_service(audio_service)
    logger.info("Audio service initialized")
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Audio conversion .oga → .mp3 | Valid .oga file | .mp3 file created successfully |
| File size validation | 15 MB file | HTTP 400 error |
| Duration validation | 90 second voice | Error message to user |
| Empty audio | Silence (no speech) | Fallback message from LLM |
| FIFO queue per user | 3 concurrent requests from user A | Processed sequentially |
| Conversation history truncation | 50 messages + audio | Last 20 messages used |

### 6.2 Integration Tests

| Test Case | Scenario | Expected Behavior |
|-----------|----------|-------------------|
| Clean Russian speech | Male/female speakers | Accurate transcription + relevant response |
| Background noise | Café/street noise | Best-effort transcription or silent fail |
| Very short message (<3s) | "Привет" | Transcription + contextual response |
| Max duration (60s) | Full 1-minute speech | Full processing without truncation |
| Network failure | OpenRouter timeout | Fast fail + error message to user |
| Concurrent users | User A & B send voice simultaneously | Both processed (different queues) |

### 6.3 Manual Testing Checklist

- [ ] Send voice message in Russian (clear speech)
- [ ] Send voice with background noise
- [ ] Send voice >1 minute (should reject)
- [ ] Send voice while previous still processing (FIFO test)
- [ ] Check transcription accuracy
- [ ] Verify AI response uses conversation history
- [ ] Confirm "Вы сказали: ..." message appears
- [ ] Verify transcription NOT saved as separate message in history
- [ ] Check latency (should be 7-15s for 30s audio)
- [ ] Verify no MCP tools called (check logs)
- [ ] Test error handling (disconnect WiFi mid-request)
- [ ] Check cost metrics logged correctly

---

## 7. Observability & Monitoring

### 7.1 Metrics to Log

```python
# In audio_service.py after each request:
logger.info(f"METRIC: voice_processing user_id={user_id} latency_ms={latency_ms} audio_tokens={audio_tokens} cost_usd={cost_usd:.6f} error={error_type or 'none'}")
```

**Logged fields:**
- `user_id`: User identifier
- `latency_ms`: Total processing time
- `audio_tokens`: Tokens consumed
- `cost_usd`: Estimated cost
- `error`: Error type if failed (conversion_error, api_error, timeout, etc.)

### 7.2 Dashboards (Future)

- **Latency Distribution:** P50, P95, P99 processing times
- **Cost Tracking:** Daily/weekly audio token spend
- **Error Rate:** Percentage of failed requests by error type
- **Usage Patterns:** Voice vs text message ratio per user

---

## 8. Edge Cases & Error Handling

| Edge Case | Handling Strategy |
|-----------|-------------------|
| Audio with no speech | LLM returns generic response or "не удалось распознать" |
| Multiple voices in audio | Best-effort transcription (model limitation) |
| Non-Russian speech | Transcription may fail → fallback message |
| Corrupted audio file | ffmpeg conversion fails → HTTP 500 + error log |
| OpenRouter rate limit | Fast fail → user sees error immediately |
| Extremely long history | Truncate to last 20 messages before API call |
| Concurrent voice + text | FIFO queue ensures text processed after voice |

---

## 9. Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Latency (30s audio) | 7-15 seconds | Quality > Speed (user requirement) |
| Error rate | <5% | Acceptable for MVP |
| Cost per request | <$0.001 | Budget-friendly (~$1 per 1000 requests) |
| Concurrent users | 100+ | Railway server can handle (async I/O) |

---

## 10. Deployment Plan

### 10.1 Prerequisites

**Server (Railway):**
- ffmpeg installed (check: `ffmpeg -version`)
- If missing: add buildpack or Dockerfile with ffmpeg

**Environment variables:**
- No new variables required (using existing `OPENROUTER_API_KEY`)

### 10.2 Deployment Steps

1. **Install ffmpeg on Railway:**
   ```bash
   # Add to railway.toml or use nixpacks
   # Railway should have ffmpeg by default, verify in logs
   ```

2. **Deploy backend updates:**
   ```bash
   git add server/audio_service.py server/app.py server/openrouter_client.py server/schemas.py
   git commit -m "feat: add voice input support with gpt-audio-mini"
   git push origin master
   # Railway auto-deploys
   ```

3. **Deploy client updates:**
   ```bash
   git add client/bot.py client/backend_client.py
   git commit -m "feat: add voice message handling in Telegram bot"
   git push origin master
   # Restart client manually
   ```

4. **Health check:**
   ```bash
   curl https://your-server.railway.app/health
   # Should return: {"status": "healthy", "mcp_connected": true, ...}
   ```

5. **Test voice endpoint:**
   ```bash
   curl -X POST "https://your-server.railway.app/api/chat-voice" \
     -H "X-API-Key: YOUR_API_KEY" \
     -F "user_id=test_user" \
     -F "audio=@test_voice.mp3"
   ```

### 10.3 Rollback Plan

If critical bugs detected:
1. Revert commits: `git revert HEAD`
2. Push to trigger redeploy
3. Bot will fall back to text-only (voice handler removed)

---

## 11. Future Enhancements (Out of Scope)

- **Streaming STT:** Real-time transcription for faster feedback
- **Voice responses:** TTS (text-to-speech) for audio replies
- **Multi-language support:** Auto-detect language or per-user setting
- **MCP tools for voice:** Enable code browsing if model improves function calling
- **Audio caching:** Cache audio files for replay/debugging
- **Quality metrics:** Track transcription accuracy (WER - Word Error Rate)

---

## 12. Dependencies

### 12.1 New Python Packages

**server/requirements.txt additions:**
```txt
# (No new packages required - ffmpeg is system-level)
```

### 12.2 System Dependencies

**Railway server:**
- `ffmpeg` (audio conversion)
  - Verify: `ffmpeg -version`
  - If missing: use Dockerfile or nixpacks config

---

## 13. Security Considerations

| Risk | Mitigation |
|------|------------|
| Large file upload DoS | 10 MB file size limit enforced |
| Malicious audio files | ffmpeg sandboxing + error handling |
| API cost abuse | No rate limiting (rely on OpenRouter provider limits) |
| Audio storage | Temp files deleted immediately after processing |
| Transcription leakage | No audio files stored permanently |

---

## 14. Acceptance Criteria

### 14.1 Must Have (P0)

- [x] User can send voice message via Telegram
- [x] Bot shows "🎧 Слушаю..." while processing
- [x] Bot displays transcription: "Вы сказали: ..."
- [x] Bot returns AI text response with full conversation context
- [x] Transcription saved to history, NOT the display message
- [x] Voice duration limited to 60 seconds
- [x] File size limited to 10 MB
- [x] .oga → .mp3 conversion working
- [x] FIFO queue per user (no concurrent processing)
- [x] Fast-fail error handling (no retries)
- [x] Metrics logged (latency, tokens, cost, errors)

### 14.2 Should Have (P1)

- [x] MCP tools disabled for voice requests
- [x] Conversation history truncated to 20 messages if needed
- [x] Russian language hardcoded for STT
- [x] Clean temp files after processing
- [x] User personalization applied (if profile exists)

### 14.3 Nice to Have (P2)

- [ ] Better error messages (distinguish conversion vs API errors)
- [ ] Audio quality pre-check (energy level detection)
- [ ] Retry logic for transient OpenRouter errors

---

## 15. Open Questions (Resolved During Interview)

| Question | Answer | Decision |
|----------|--------|----------|
| Use STT service or audio model? | **Audio model (gpt-audio-mini)** | Simpler architecture, fewer API calls |
| Where to convert .oga? | **Backend (ffmpeg)** | Centralized logic, client stays simple |
| Show transcription to user? | **Yes (separate message)** | Transparency, user can verify accuracy |
| Save transcription message to history? | **No** | Only transcription text, not the display message |
| Support MCP tools for voice? | **No** | Stability & simplicity prioritized |
| Rate limiting? | **None** | Rely on OpenRouter provider limits |
| Retry on errors? | **No (fast fail)** | Better UX than long delays |
| Multi-language support? | **No (Russian only)** | Simplifies MVP |

---

## 16. Success Metrics (Post-Launch)

**Week 1:**
- Voice messages sent: Target >50
- Average latency: <10 seconds
- Error rate: <10%

**Month 1:**
- Voice adoption: >20% of active users
- Cost per voice message: <$0.001
- User feedback: Positive (via Telegram bot survey)

---

## 17. Documentation Updates Required

- [x] Update `CLAUDE.md` with voice input feature description
- [x] Add voice endpoint to API documentation section
- [x] Update client/README with new voice handler
- [x] Add troubleshooting section for ffmpeg issues

---

## 18. Reference Materials

**Sources used during specification:**
- [OpenAI GPT-4o Audio Model Documentation](https://platform.openai.com/docs/models/gpt-4o-audio-preview)
- [OpenRouter API Reference](https://openrouter.ai/docs)
- [Audio API Reference](https://platform.openai.com/docs/api-reference/audio/)
- [GPT Audio Preliminary Review](https://medium.com/@leucopsis/gpt-audio-preliminary-review-5dec93297df0)

**Audio format support:**
- gpt-audio-mini supports: wav, mp3, flac, opus, pcm16
- Telegram voice format: .oga (Ogg Audio with Opus codec)
- **Decision:** Convert .oga → .mp3 on backend using ffmpeg

**API pricing (OpenRouter):**
- Input tokens: $0.60/M
- Output tokens: $2.40/M
- Audio tokens: $0.60/M

---

## 19. Glossary

| Term | Definition |
|------|------------|
| **STT** | Speech-to-Text (audio transcription) |
| **gpt-audio-mini** | OpenAI's compact audio-capable model via OpenRouter |
| **FIFO queue** | First-In-First-Out queue (sequential processing per user) |
| **Truncation** | Removing old messages from history to stay within context limits |
| **Fast-fail** | Immediate error response without retries |
| **MCP** | Model Context Protocol (tools for code browsing, RAG, etc.) |
| **Multipart form-data** | HTTP request format for file uploads |

---

**END OF SPECIFICATION**
