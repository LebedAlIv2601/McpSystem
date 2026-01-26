"""Profile manager for personalization logic."""

import logging
from typing import Optional
from user_profile import UserProfile
from profile_storage import ProfileStorage

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages user profiles and generates personalized context."""

    def __init__(self, storage: Optional[ProfileStorage] = None):
        """Initialize profile manager."""
        self.storage = storage or ProfileStorage()

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile by ID."""
        return self.storage.load_profile(user_id)

    def update_profile(self, user_id: str, **kwargs) -> UserProfile:
        """Update user profile with provided fields."""
        # Load existing or create new profile
        profile = self.storage.load_profile(user_id)

        if profile:
            # Update existing profile
            profile_dict = profile.model_dump()
            profile_dict.update(kwargs)
            profile = UserProfile(**profile_dict)
        else:
            # Create new profile
            if "name" not in kwargs:
                raise ValueError("name is required for new profile")
            profile = UserProfile(**kwargs)

        # Save and return
        self.storage.save_profile(user_id, profile)
        logger.info(f"Updated profile for user_id: {user_id}")
        return profile

    def delete_profile(self, user_id: str) -> bool:
        """Delete user profile."""
        return self.storage.delete_profile(user_id)

    def profile_exists(self, user_id: str) -> bool:
        """Check if profile exists."""
        return self.storage.profile_exists(user_id)

    def build_context(self, user_id: str) -> str:
        """
        Build structured context from user profile.
        Model will decide which parts to use based on the question.
        """
        profile = self.get_profile(user_id)
        if not profile:
            return ""

        # Build structured context
        context_parts = []

        # Header
        context_parts.append("===== USER PROFILE =====\n")

        # Personal Information (always)
        context_parts.append("Personal Information:")
        context_parts.append(f"- Name: {profile.name}")
        context_parts.append(f"- Preferred Language: {profile.language}")
        context_parts.append(f"- Timezone: {profile.timezone}")

        if profile.personal_info:
            for key, value in profile.personal_info.items():
                context_parts.append(f"- {key.replace('_', ' ').title()}: {value}")

        context_parts.append("")

        # Communication Preferences (always apply)
        comm = profile.communication_preferences
        context_parts.append("Communication Preferences (always apply):")
        context_parts.append(f"- Response Style: {comm.response_style}")
        context_parts.append(f"- Tone: {comm.tone}")
        context_parts.append(f"- Use Emojis: {comm.use_emojis}")
        if comm.preferred_greeting:
            context_parts.append(f"- Preferred Greeting: {comm.preferred_greeting}")
        context_parts.append("")

        # Development Context (use when discussing code/architecture)
        if profile.development_preferences:
            dev = profile.development_preferences
            context_parts.append("Development Context (use when discussing code/architecture):")
            context_parts.append(f"- Primary Language: {dev.primary_language}")
            if dev.secondary_languages:
                context_parts.append(f"- Secondary Languages: {', '.join(dev.secondary_languages)}")
            if dev.architecture_style:
                context_parts.append(f"- Architecture Style: {dev.architecture_style}")
            if dev.code_style:
                context_parts.append(f"- Code Style: {dev.code_style}")
            if dev.testing_approach:
                context_parts.append(f"- Testing Approach: {dev.testing_approach}")
            if dev.preferred_libraries:
                context_parts.append(f"- Preferred Libraries: {', '.join(dev.preferred_libraries)}")
            context_parts.append("")

        # Work Habits (use when relevant)
        if profile.work_habits:
            work = profile.work_habits
            context_parts.append("Work Habits (reference when relevant):")
            if work.working_hours:
                context_parts.append(f"- Working Hours: {work.working_hours}")
            if work.break_time:
                context_parts.append(f"- Break Time: {work.break_time}")
            if work.focus_periods:
                context_parts.append(f"- Focus Periods: {', '.join(work.focus_periods)}")
            if work.preferred_review_time:
                context_parts.append(f"- Preferred Review Time: {work.preferred_review_time}")
            context_parts.append("")

        # Project Context (use when discussing projects)
        if profile.project_context:
            proj = profile.project_context
            context_parts.append("Project Context (use when discussing projects):")
            if proj.current_projects:
                context_parts.append(f"- Current Projects: {', '.join(proj.current_projects)}")
            if proj.main_responsibilities:
                context_parts.append(f"- Main Responsibilities: {', '.join(proj.main_responsibilities)}")
            if proj.pain_points:
                context_parts.append(f"- Pain Points: {', '.join(proj.pain_points)}")
            context_parts.append("")

        # AI Assistant Behavior (always apply)
        ai = profile.ai_assistant_preferences
        context_parts.append("AI Assistant Behavior (always apply):")
        context_parts.append(f"- Code Explanation Style: {ai.explain_code}")
        context_parts.append(f"- Code Comments Level: {ai.code_comments}")
        context_parts.append(f"- Suggest Alternatives: {ai.suggest_alternatives}")
        context_parts.append(f"- Ask Before Refactoring: {ai.ask_before_refactoring}")
        context_parts.append(f"- Include Tests: {ai.include_tests}")
        context_parts.append("")

        # Footer with instructions
        context_parts.append("===== END PROFILE =====\n")
        context_parts.append("Instructions:")
        context_parts.append(f"- Always respond in the user's preferred language ({profile.language})")
        context_parts.append("- Apply communication preferences and AI behavior settings to all responses")
        context_parts.append("- Use development/project context when relevant to the user's question")
        context_parts.append("- Respect the user's work habits and preferences")

        return "\n".join(context_parts)


# Global instance
_profile_manager = None


def get_profile_manager() -> ProfileManager:
    """Get or create global profile manager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager
