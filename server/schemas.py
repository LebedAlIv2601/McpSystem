"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    user_id: str = Field(..., description="Unique user identifier")
    message: str = Field(..., min_length=1, description="User message text")


class BuildRequest(BaseModel):
    """Build request info returned when AI triggers a build."""

    workflow_run_id: int = Field(..., description="GitHub Actions workflow run ID")
    branch: str = Field(..., description="Git branch being built")
    user_id: str = Field(..., description="User who requested the build")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str = Field(..., description="Assistant response text")
    tool_calls_count: int = Field(default=0, description="Number of tool calls made")
    mcp_used: bool = Field(default=False, description="Whether MCP tools were used")
    build_request: Optional[BuildRequest] = Field(default=None, description="Build request if AI triggered a build")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(default="healthy")
    mcp_connected: bool = Field(default=False)
    tools_count: int = Field(default=0)


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
