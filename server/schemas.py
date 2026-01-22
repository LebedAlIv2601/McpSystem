"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    user_id: str = Field(..., description="Unique user identifier")
    message: str = Field(..., min_length=1, description="User message text")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str = Field(..., description="Assistant response text")
    tool_calls_count: int = Field(default=0, description="Number of tool calls made")
    mcp_used: bool = Field(default=False, description="Whether MCP tools were used")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(default="healthy")
    mcp_connected: bool = Field(default=False)
    tools_count: int = Field(default=0)
    model_ready: bool = Field(default=False, description="Whether LLM model is ready for inference")


class ErrorResponse(BaseModel):
    """Response model for error cases."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


class ReviewPRRequest(BaseModel):
    """Request model for PR review endpoint."""

    pr_number: int = Field(..., description="Pull Request number to review")


class ReviewPRResponse(BaseModel):
    """Response model for PR review endpoint."""

    review: str = Field(..., description="Code review text with file:line references")
    tool_calls_count: int = Field(default=0, description="Number of MCP tool calls made")


class AsyncChatRequest(BaseModel):
    """Request model for async chat endpoint."""

    user_id: str = Field(..., description="Unique user identifier")
    message: str = Field(..., min_length=1, description="User message text")


class AsyncChatResponse(BaseModel):
    """Response model for async chat endpoint."""

    task_id: str = Field(..., description="Task ID for polling")
    status: str = Field(..., description="Initial task status (pending)")


class TaskStatusResponse(BaseModel):
    """Response model for task status endpoint."""

    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status: pending, processing, completed, failed")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Task last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
