"""User profile models for personalization."""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class CommunicationPreferences(BaseModel):
    """User's communication style preferences."""

    response_style: Literal["concise", "detailed", "balanced"] = Field(
        default="balanced",
        description="Preferred level of detail in responses"
    )
    tone: Literal["professional", "casual", "formal"] = Field(
        default="professional",
        description="Preferred tone of communication"
    )
    use_emojis: bool = Field(
        default=False,
        description="Whether to use emojis in responses"
    )
    preferred_greeting: Optional[str] = Field(
        default=None,
        description="Custom greeting phrase"
    )


class DevelopmentPreferences(BaseModel):
    """User's development style and preferences."""

    primary_language: str = Field(
        ...,
        description="Primary programming language"
    )
    secondary_languages: List[str] = Field(
        default_factory=list,
        description="Additional programming languages"
    )
    architecture_style: Optional[str] = Field(
        default=None,
        description="Preferred architecture pattern (e.g., Clean Architecture, MVI)"
    )
    code_style: Optional[str] = Field(
        default=None,
        description="Code style preferences (e.g., idiomatic_kotlin, pep8)"
    )
    testing_approach: Optional[str] = Field(
        default=None,
        description="Testing methodology (e.g., unit_tests_required, tdd)"
    )
    preferred_libraries: List[str] = Field(
        default_factory=list,
        description="Favorite libraries and frameworks"
    )


class WorkHabits(BaseModel):
    """User's work schedule and habits."""

    working_hours: Optional[str] = Field(
        default=None,
        description="Working hours (e.g., '10:00-19:00 MSK')"
    )
    break_time: Optional[str] = Field(
        default=None,
        description="Break time (e.g., '14:00-15:00')"
    )
    focus_periods: List[str] = Field(
        default_factory=list,
        description="Peak productivity periods (e.g., ['10:00-12:00', '16:00-18:00'])"
    )
    preferred_review_time: Optional[str] = Field(
        default=None,
        description="Preferred time for code reviews (e.g., 'morning', 'afternoon')"
    )


class ProjectContext(BaseModel):
    """User's current project context."""

    current_projects: List[str] = Field(
        default_factory=list,
        description="List of active projects"
    )
    main_responsibilities: List[str] = Field(
        default_factory=list,
        description="Key responsibilities in projects"
    )
    pain_points: List[str] = Field(
        default_factory=list,
        description="Current challenges or pain points"
    )


class AIAssistantPreferences(BaseModel):
    """AI assistant behavior preferences."""

    explain_code: Literal["brief", "step_by_step", "detailed"] = Field(
        default="step_by_step",
        description="How to explain code"
    )
    code_comments: Literal["minimal", "standard", "verbose"] = Field(
        default="minimal",
        description="Level of code comments to generate"
    )
    suggest_alternatives: bool = Field(
        default=True,
        description="Whether to suggest alternative approaches"
    )
    ask_before_refactoring: bool = Field(
        default=True,
        description="Whether to ask before major refactoring"
    )
    auto_format_code: bool = Field(
        default=True,
        description="Whether to automatically format code"
    )
    include_tests: Literal["always", "on_request", "never"] = Field(
        default="on_request",
        description="When to include tests with code"
    )


class UserProfile(BaseModel):
    """Complete user profile for personalization."""

    # Required fields
    name: str = Field(..., description="User's name")
    language: str = Field(default="en", description="Preferred language (ISO 639-1)")
    timezone: str = Field(default="UTC", description="User's timezone")

    # Optional personal info (flexible dict for custom fields)
    personal_info: Optional[dict] = Field(
        default=None,
        description="Additional personal information (role, experience, company, etc.)"
    )

    # Structured preferences
    communication_preferences: CommunicationPreferences = Field(
        default_factory=CommunicationPreferences
    )
    development_preferences: Optional[DevelopmentPreferences] = Field(
        default=None,
        description="Development preferences (required for developers)"
    )
    work_habits: Optional[WorkHabits] = Field(
        default=None,
        description="Work schedule and habits"
    )
    project_context: Optional[ProjectContext] = Field(
        default=None,
        description="Current project context"
    )
    ai_assistant_preferences: AIAssistantPreferences = Field(
        default_factory=AIAssistantPreferences
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Profile creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Last update timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Александр",
                "language": "ru",
                "timezone": "Europe/Moscow",
                "personal_info": {
                    "role": "Senior Android Developer",
                    "experience_years": 8
                },
                "development_preferences": {
                    "primary_language": "Kotlin",
                    "architecture_style": "Clean Architecture + MVI",
                    "preferred_libraries": ["Jetpack Compose", "Coroutines"]
                }
            }
        }
