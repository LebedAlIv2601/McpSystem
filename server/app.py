"""FastAPI router with chat endpoint."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile

from auth import verify_api_key
from schemas import (
    ChatRequest, ChatResponse, HealthResponse, ErrorResponse,
    ReviewPRRequest, ReviewPRResponse,
    ProfileUpdateRequest, ProfileResponse,
    VoiceResponse
)
from chat_service import ChatService
from profile_manager import get_profile_manager
from audio_service import get_audio_service, AudioService

logger = logging.getLogger(__name__)

router = APIRouter()

# Global chat service instance (initialized in main.py)
_chat_service: ChatService = None


def get_chat_service() -> ChatService:
    """Get chat service instance."""
    if _chat_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    return _chat_service


def set_chat_service(service: ChatService) -> None:
    """Set chat service instance."""
    global _chat_service
    _chat_service = service


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Send chat message",
    description="Send a message to the AI assistant and get a response. The assistant has access to MCP tools for code browsing and documentation search."
)
async def chat(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    """
    Process chat message and return AI response.

    Args:
        request: Chat request with user_id and message
        api_key: Validated API key
        chat_service: Chat service instance

    Returns:
        ChatResponse with assistant's response
    """
    logger.info(f"Chat request from user {request.user_id}")

    try:
        response_text, tool_calls_count, mcp_used = await chat_service.process_message(
            user_id=request.user_id,
            message=request.message
        )

        return ChatResponse(
            response=response_text,
            tool_calls_count=tool_calls_count,
            mcp_used=mcp_used
        )

    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/api/review-pr",
    response_model=ReviewPRResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Review Pull Request",
    description="Perform AI-powered code review for a specific pull request. Returns detailed review with file:line references."
)
async def review_pr(
    request: ReviewPRRequest,
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service)
) -> ReviewPRResponse:
    """
    Perform code review for a pull request.

    Args:
        request: Review request with PR number
        api_key: Validated API key
        chat_service: Chat service instance

    Returns:
        ReviewPRResponse with review text and tool call count
    """
    logger.info(f"PR review request for #{request.pr_number}")

    try:
        review_text, tool_calls_count = await chat_service.review_pr(
            pr_number=request.pr_number
        )

        return ReviewPRResponse(
            review=review_text,
            tool_calls_count=tool_calls_count
        )

    except Exception as e:
        logger.error(f"PR review error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the server is healthy and MCP is connected."
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse with service status
    """
    if _chat_service is None:
        return HealthResponse(
            status="unhealthy",
            mcp_connected=False,
            tools_count=0
        )

    return HealthResponse(
        status="healthy",
        mcp_connected=True,
        tools_count=_chat_service.get_tools_count()
    )


@router.get(
    "/api/profile/{user_id}",
    response_model=ProfileResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Profile not found"}
    },
    summary="Get user profile",
    description="Retrieve user profile for personalization."
)
async def get_profile(
    user_id: str,
    api_key: str = Depends(verify_api_key)
) -> ProfileResponse:
    """
    Get user profile by ID.

    Args:
        user_id: User identifier
        api_key: Validated API key

    Returns:
        ProfileResponse with user profile data
    """
    logger.info(f"Get profile request for user {user_id}")

    profile_manager = get_profile_manager()
    profile = profile_manager.get_profile(user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found for user {user_id}"
        )

    return ProfileResponse(
        message="Profile retrieved successfully",
        profile=profile.model_dump(mode="json")
    )


@router.put(
    "/api/profile/{user_id}",
    response_model=ProfileResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        400: {"model": ErrorResponse, "description": "Invalid profile data"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Update user profile",
    description="Create or update user profile. Supports partial updates."
)
async def update_profile(
    user_id: str,
    request: ProfileUpdateRequest,
    api_key: str = Depends(verify_api_key)
) -> ProfileResponse:
    """
    Update user profile.

    Args:
        user_id: User identifier
        request: Profile update data
        api_key: Validated API key

    Returns:
        ProfileResponse with updated profile
    """
    logger.info(f"Update profile request for user {user_id}")

    try:
        profile_manager = get_profile_manager()
        profile = profile_manager.update_profile(user_id, **request.data)

        return ProfileResponse(
            message="Profile updated successfully",
            profile=profile.model_dump(mode="json")
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Profile update error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete(
    "/api/profile/{user_id}",
    response_model=ProfileResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Profile not found"}
    },
    summary="Delete user profile",
    description="Delete user profile and all associated data (GDPR compliance)."
)
async def delete_profile(
    user_id: str,
    api_key: str = Depends(verify_api_key)
) -> ProfileResponse:
    """
    Delete user profile.

    Args:
        user_id: User identifier
        api_key: Validated API key

    Returns:
        ProfileResponse with deletion confirmation
    """
    logger.info(f"Delete profile request for user {user_id}")

    profile_manager = get_profile_manager()
    success = profile_manager.delete_profile(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found for user {user_id}"
        )

    return ProfileResponse(
        message="Profile deleted successfully"
    )


@router.post(
    "/api/chat-voice",
    response_model=VoiceResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid audio file"},
        401: {"model": ErrorResponse, "description": "Invalid API key"},
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
    logger.info(f"Voice request from user {user_id}, file={audio.filename}, size={audio.size if audio.size else 'unknown'}")

    # Validate file size (10MB limit)
    if audio.size and audio.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file exceeds 10MB limit"
        )

    try:
        # Read audio bytes
        audio_bytes = await audio.read()

        # Determine audio format from filename
        audio_format = "oga"
        if audio.filename:
            ext = audio.filename.split('.')[-1].lower()
            if ext in ["mp3", "wav", "oga", "ogg"]:
                audio_format = ext

        # Process voice message
        result = await audio_service.process_voice_message(
            user_id=user_id,
            audio_bytes=audio_bytes,
            audio_format=audio_format
        )

        return VoiceResponse(**result)

    except Exception as e:
        logger.error(f"Voice processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio processing failed: {str(e)}"
        )
