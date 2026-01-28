"""Audio processing service for voice messages."""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional
from collections import defaultdict

from fastapi import HTTPException

from conversation import ConversationManager
from openrouter_client import OpenRouterClient
from profile_manager import get_profile_manager
from config import MCP_USED_INDICATOR

logger = logging.getLogger(__name__)


class AudioService:
    """Service for processing voice messages with two-stage processing:
    1. Audio model (gpt-audio-mini) - transcription/summary
    2. Text model (via chat_service) - response generation with MCP tools
    """

    def __init__(self, mcp_manager=None):
        logger.info("Initializing AudioService...")

        try:
            self.conversation_manager = ConversationManager()
            logger.info("ConversationManager initialized")

            self.openrouter_client = OpenRouterClient()
            logger.info("OpenRouterClient initialized")

            # Per-user locks for sequential processing (FIFO)
            self.user_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
            logger.info("User locks initialized")

            logger.info("AudioService initialization complete (two-stage processing: audio → text)")
        except Exception as e:
            logger.error(f"AudioService initialization failed: {e}", exc_info=True)
            raise

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
        error_type = None

        try:
            # Step 1: Save input audio to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}") as temp_input:
                temp_input.write(audio_bytes)
                temp_input_path = temp_input.name

            logger.info(f"User {user_id}: Audio saved to {temp_input_path} ({len(audio_bytes)} bytes)")

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

            # Step 5: Get transcription from audio model (NO tools)
            logger.info(f"User {user_id}: Step 1/2 - Audio transcription")
            audio_prompt = self._build_audio_transcription_prompt()

            _, audio_response, audio_tokens, _ = await self.openrouter_client.audio_completion(
                messages=[audio_prompt] + conversation_history,
                audio_file_path=audio_file_path,
                language="ru",
                tools=None,  # NO tools for audio model
                tool_choice=None
            )

            if not audio_response:
                logger.error(f"User {user_id}: Audio transcription failed")
                return {
                    "transcription": None,
                    "response": "Извините, не удалось распознать голосовое сообщение.",
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "audio_tokens": audio_tokens,
                    "cost_usd": self._calculate_cost(audio_tokens)
                }

            logger.info(f"User {user_id}: Transcription (from audio model): {audio_response[:100]}...")

            # Step 6: Process transcription with text model + MCP tools
            logger.info(f"User {user_id}: Step 2/2 - Text processing with MCP tools")

            # Import here to avoid circular dependency
            from app import get_chat_service

            chat_service = get_chat_service()
            final_response, tool_calls_count, mcp_was_used = await chat_service.process_message(
                user_id=user_id,
                message=audio_response
            )

            # Step 7: Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)
            cost_usd = self._calculate_cost(audio_tokens)

            logger.info(
                f"METRIC: voice_processing user_id={user_id} latency_ms={latency_ms} "
                f"audio_tokens={audio_tokens} cost_usd={cost_usd:.6f} tool_calls={tool_calls_count} "
                f"mcp_used={mcp_was_used} error=none"
            )

            return {
                "transcription": audio_response,  # What audio model understood
                "response": final_response or "Извините, не удалось обработать голосовое сообщение.",
                "latency_ms": latency_ms,
                "audio_tokens": audio_tokens,
                "cost_usd": cost_usd
            }

        except Exception as e:
            error_type = type(e).__name__
            latency_ms = int((time.time() - start_time) * 1000)

            logger.error(f"User {user_id}: Audio processing error: {e}", exc_info=True)
            logger.info(
                f"METRIC: voice_processing user_id={user_id} latency_ms={latency_ms} "
                f"audio_tokens=0 cost_usd=0.0 error={error_type}"
            )
            raise

        finally:
            # Cleanup temp files
            if temp_input_path and os.path.exists(temp_input_path):
                try:
                    os.remove(temp_input_path)
                    logger.debug(f"Cleaned up temp file: {temp_input_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {temp_input_path}: {e}")

            if temp_output_path and os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                    logger.debug(f"Cleaned up temp file: {temp_output_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {temp_output_path}: {e}")

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
            error_msg = stderr.decode() if stderr else "Unknown ffmpeg error"
            logger.error(f"ffmpeg error: {error_msg}")
            raise RuntimeError(f"Audio conversion failed: {error_msg}")

        logger.info(f"Audio converted successfully: {output_path}")

    def _build_audio_transcription_prompt(self) -> Dict:
        """Build system prompt for audio transcription/summary."""
        return {
            "role": "system",
            "content": """You are a voice message transcription assistant.

Your task is to:
1. Listen to the user's voice message
2. Transcribe it accurately
3. Create a brief summary of the main question or request

Respond ONLY with the transcribed text or a brief summary of what the user asked.
Be concise and clear. Use Russian language."""
        }

    def _calculate_cost(self, audio_tokens: int) -> float:
        """Calculate cost in USD based on audio tokens."""
        # gpt-audio-mini pricing: $0.60 per 1M audio tokens
        cost_per_token = 0.60 / 1_000_000
        return audio_tokens * cost_per_token


# Global service instance (initialized in main.py)
_audio_service: Optional[AudioService] = None


def get_audio_service() -> Optional[AudioService]:
    """Get audio service instance."""
    if _audio_service is None:
        raise HTTPException(
            status_code=503,
            detail="Voice input service not available"
        )
    return _audio_service


def set_audio_service(service: AudioService) -> None:
    """Set audio service instance."""
    global _audio_service
    _audio_service = service
