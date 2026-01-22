"""FastAPI router with chat endpoint."""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from auth import verify_api_key
from schemas import (
    ChatRequest, ChatResponse, HealthResponse, ErrorResponse,
    ReviewPRRequest, ReviewPRResponse, AsyncChatRequest,
    AsyncChatResponse, TaskStatusResponse
)
from chat_service import ChatService
from ollama_manager import OllamaManager
from task_manager import task_manager, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances (initialized in main.py)
_chat_service: ChatService = None
_ollama_manager: Optional[OllamaManager] = None


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


def set_ollama_manager(manager: OllamaManager) -> None:
    """Set Ollama manager instance."""
    global _ollama_manager
    _ollama_manager = manager


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

    # Check if model is ready
    if _ollama_manager and not _ollama_manager.is_model_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model is still downloading. Please try again in a few minutes. Check /health for status."
        )

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
    "/api/chat/async",
    response_model=AsyncChatResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Send chat message (async)",
    description="Submit a chat message for asynchronous processing. Returns task_id immediately. Use GET /api/tasks/{task_id} to poll for results."
)
async def chat_async(
    request: AsyncChatRequest,
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service)
) -> AsyncChatResponse:
    """
    Submit chat message for async processing and return task ID immediately.

    Args:
        request: Chat request with user_id and message
        api_key: Validated API key
        chat_service: Chat service instance

    Returns:
        AsyncChatResponse with task_id
    """
    logger.info(f"Async chat request from user {request.user_id}")

    # Check if model is ready
    if _ollama_manager and not _ollama_manager.is_model_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model is still downloading. Please try again in a few minutes. Check /health for status."
        )

    try:
        # Create task
        task_id = task_manager.create_task(request.user_id, request.message)

        # Start processing in background
        asyncio.create_task(chat_service.process_message_async(task_id, request.user_id, request.message))

        return AsyncChatResponse(
            task_id=task_id,
            status=TaskStatus.PENDING.value
        )

    except Exception as e:
        logger.error(f"Async chat submission error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/api/tasks/{task_id}",
    response_model=TaskStatusResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get task status",
    description="Poll for task status and results. Task is automatically deleted 5 minutes after completion."
)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
) -> TaskStatusResponse:
    """
    Get task status and result (if completed).

    Args:
        task_id: Task ID from /api/chat/async
        api_key: Validated API key

    Returns:
        TaskStatusResponse with status and result
    """
    task = task_manager.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found (may have expired)"
        )

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status.value,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        result=task.result,
        error=task.error
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

    # Check if model is ready
    if _ollama_manager and not _ollama_manager.is_model_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model is still downloading. Please try again in a few minutes. Check /health for status."
        )

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
    description="Check if the server is healthy, MCP is connected, and LLM model is ready."
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse with service status, MCP connection, tools count, and model readiness
    """
    model_ready = _ollama_manager.is_model_ready() if _ollama_manager else False

    if _chat_service is None:
        return HealthResponse(
            status="starting" if not model_ready else "unhealthy",
            mcp_connected=False,
            tools_count=0,
            model_ready=model_ready
        )

    return HealthResponse(
        status="healthy" if model_ready else "starting",
        mcp_connected=True,
        tools_count=_chat_service.get_tools_count(),
        model_ready=model_ready
    )
