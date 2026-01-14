"""FastAPI router with chat endpoint."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from auth import verify_api_key
from schemas import ChatRequest, ChatResponse, HealthResponse, ErrorResponse, ReviewPRRequest, ReviewPRResponse
from chat_service import ChatService

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
