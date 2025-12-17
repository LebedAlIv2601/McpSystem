"""User subscription management module."""

import json
import logging
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


class SubscriberManager:
    """Manages user subscriptions for periodic task summaries."""

    def __init__(self, subscribers_file: str = "subscribers.json"):
        """Initialize subscriber manager.

        Args:
            subscribers_file: Name of the JSON file to store subscriber data
        """
        self.subscribers_path = Path(__file__).parent / subscribers_file
        logger.info(f"Subscriber manager initialized with file: {self.subscribers_path}")

    def load_subscribers(self) -> dict:
        """Load subscriber data from JSON file.

        Returns:
            Dictionary with 'all_users' and 'subscribed_users' sets
        """
        if not self.subscribers_path.exists():
            logger.debug("Subscribers file does not exist, returning empty data")
            return {"all_users": set(), "subscribed_users": set()}

        try:
            with open(self.subscribers_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Convert lists back to sets
            result = {
                "all_users": set(data.get("all_users", [])),
                "subscribed_users": set(data.get("subscribed_users", []))
            }
            logger.debug(f"Loaded {len(result['all_users'])} total users, "
                        f"{len(result['subscribed_users'])} subscribed")
            return result
        except Exception as e:
            logger.error(f"Failed to load subscribers: {e}")
            return {"all_users": set(), "subscribed_users": set()}

    def save_subscribers(self, all_users: Set[int], subscribed_users: Set[int]) -> None:
        """Save subscriber data to JSON file.

        Args:
            all_users: Set of all user IDs who have ever interacted
            subscribed_users: Set of user IDs who are subscribed to summaries
        """
        try:
            # Convert sets to lists for JSON serialization
            data = {
                "all_users": list(all_users),
                "subscribed_users": list(subscribed_users)
            }
            with open(self.subscribers_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(all_users)} total users, {len(subscribed_users)} subscribed")
        except Exception as e:
            logger.error(f"Failed to save subscribers: {e}")

    def track_user_interaction(self, user_id: int) -> None:
        """Record that a user has interacted with the bot.

        Args:
            user_id: Telegram user ID
        """
        data = self.load_subscribers()
        if user_id not in data["all_users"]:
            data["all_users"].add(user_id)
            self.save_subscribers(data["all_users"], data["subscribed_users"])
            logger.info(f"New user tracked: {user_id}")

    def add_subscriber(self, user_id: int) -> None:
        """Add user to subscription list.

        Args:
            user_id: Telegram user ID
        """
        data = self.load_subscribers()
        data["all_users"].add(user_id)
        data["subscribed_users"].add(user_id)
        self.save_subscribers(data["all_users"], data["subscribed_users"])
        logger.info(f"User {user_id} subscribed to summaries")

    def remove_subscriber(self, user_id: int) -> None:
        """Remove user from subscription list.

        Args:
            user_id: Telegram user ID
        """
        data = self.load_subscribers()
        if user_id in data["subscribed_users"]:
            data["subscribed_users"].remove(user_id)
            self.save_subscribers(data["all_users"], data["subscribed_users"])
            logger.info(f"User {user_id} unsubscribed from summaries")

    def is_subscribed(self, user_id: int) -> bool:
        """Check if user is subscribed to summaries.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is subscribed, False otherwise
        """
        data = self.load_subscribers()
        return user_id in data["subscribed_users"]

    def get_subscribed_users(self) -> Set[int]:
        """Get all subscribed user IDs.

        Returns:
            Set of subscribed user IDs
        """
        data = self.load_subscribers()
        return data["subscribed_users"]
