"""JSON file storage for user profiles."""

import json
import logging
import os
from pathlib import Path
from typing import Optional
from filelock import FileLock
from user_profile import UserProfile

logger = logging.getLogger(__name__)


class ProfileStorage:
    """Thread-safe JSON storage for user profiles."""

    def __init__(self, data_dir: str = "data"):
        """Initialize storage with data directory."""
        self.data_dir = Path(__file__).parent / data_dir
        self.data_dir.mkdir(exist_ok=True)

        self.profiles_file = self.data_dir / "user_profiles.json"
        self.lock_file = self.data_dir / "user_profiles.lock"

        # Create empty profiles file if it doesn't exist
        if not self.profiles_file.exists():
            self._write_profiles({})
            logger.info(f"Created new profiles file: {self.profiles_file}")

    def _read_profiles(self) -> dict:
        """Read all profiles from file (thread-safe)."""
        with FileLock(str(self.lock_file)):
            try:
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted profiles file, returning empty dict")
                return {}
            except Exception as e:
                logger.error(f"Error reading profiles: {e}")
                return {}

    def _write_profiles(self, profiles: dict) -> None:
        """Write all profiles to file (thread-safe)."""
        with FileLock(str(self.lock_file)):
            try:
                with open(self.profiles_file, "w", encoding="utf-8") as f:
                    json.dump(profiles, f, ensure_ascii=False, indent=2, default=str)
            except Exception as e:
                logger.error(f"Error writing profiles: {e}")
                raise

    def load_profile(self, user_id: str) -> Optional[UserProfile]:
        """Load user profile by ID."""
        profiles = self._read_profiles()
        profile_data = profiles.get(user_id)

        if not profile_data:
            logger.debug(f"No profile found for user_id: {user_id}")
            return None

        try:
            profile = UserProfile(**profile_data)
            logger.debug(f"Loaded profile for user_id: {user_id}")
            return profile
        except Exception as e:
            logger.error(f"Error parsing profile for user_id {user_id}: {e}")
            return None

    def save_profile(self, user_id: str, profile: UserProfile) -> None:
        """Save user profile."""
        profiles = self._read_profiles()

        # Update timestamp
        from datetime import datetime
        profile.updated_at = datetime.now()

        # Convert to dict and save
        profiles[user_id] = profile.model_dump(mode="json")
        self._write_profiles(profiles)

        logger.info(f"Saved profile for user_id: {user_id}")

    def delete_profile(self, user_id: str) -> bool:
        """Delete user profile."""
        profiles = self._read_profiles()

        if user_id not in profiles:
            logger.warning(f"Profile not found for deletion: {user_id}")
            return False

        del profiles[user_id]
        self._write_profiles(profiles)

        logger.info(f"Deleted profile for user_id: {user_id}")
        return True

    def profile_exists(self, user_id: str) -> bool:
        """Check if profile exists."""
        profiles = self._read_profiles()
        return user_id in profiles

    def list_user_ids(self) -> list[str]:
        """List all user IDs with profiles."""
        profiles = self._read_profiles()
        return list(profiles.keys())
