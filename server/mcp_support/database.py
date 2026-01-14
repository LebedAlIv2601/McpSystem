"""JSON-based database for support tickets."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DB_FILE = DATA_DIR / "support_db.json"


class SupportDatabase:
    """JSON file-based database for users and tickets."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_FILE
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Ensure database file and directory exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self._save_data({"users": {}, "tickets": []})
            logger.info(f"Created new database at {self.db_path}")

    def _load_data(self) -> dict:
        """Load data from JSON file."""
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading database: {e}")
            return {"users": {}, "tickets": []}

    def _save_data(self, data: dict) -> None:
        """Save data to JSON file."""
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_user(self, user_id: str, user_name: str = "") -> dict:
        """Get user by ID or create new one."""
        data = self._load_data()

        if user_id not in data["users"]:
            data["users"][user_id] = {
                "id": user_id,
                "name": user_name or f"User_{user_id}"
            }
            self._save_data(data)
            logger.info(f"Created new user: {user_id}")
        elif user_name and data["users"][user_id]["name"] != user_name:
            data["users"][user_id]["name"] = user_name
            self._save_data(data)

        return data["users"][user_id]

    def get_user_tickets(self, user_id: str) -> list[dict]:
        """Get all tickets for a user."""
        data = self._load_data()
        tickets = [t for t in data["tickets"] if t["user_id"] == user_id]
        return sorted(tickets, key=lambda x: x["created_at"], reverse=True)

    def get_open_ticket(self, user_id: str) -> Optional[dict]:
        """Get the currently open or in_progress ticket for a user."""
        tickets = self.get_user_tickets(user_id)
        for ticket in tickets:
            if ticket["status"] in ("open", "in_progress"):
                return ticket
        return None

    def create_ticket(self, user_id: str, user_name: str, description: str) -> dict:
        """Create a new ticket with status 'open'."""
        data = self._load_data()

        self.get_user(user_id, user_name)

        ticket = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "status": "open",
            "description": description,
            "created_at": datetime.now().isoformat()
        }

        data["tickets"].append(ticket)
        self._save_data(data)

        logger.info(f"Created ticket {ticket['id']} for user {user_id}")
        return ticket

    def update_ticket_status(self, ticket_id: str, status: str) -> Optional[dict]:
        """Update ticket status (open, in_progress, closed)."""
        if status not in ("open", "in_progress", "closed"):
            logger.error(f"Invalid status: {status}")
            return None

        data = self._load_data()

        for ticket in data["tickets"]:
            if ticket["id"] == ticket_id:
                ticket["status"] = status
                self._save_data(data)
                logger.info(f"Updated ticket {ticket_id} status to {status}")
                return ticket

        logger.error(f"Ticket not found: {ticket_id}")
        return None

    def update_ticket_description(self, ticket_id: str, description: str) -> Optional[dict]:
        """Update ticket description."""
        data = self._load_data()

        for ticket in data["tickets"]:
            if ticket["id"] == ticket_id:
                ticket["description"] = description
                self._save_data(data)
                logger.info(f"Updated ticket {ticket_id} description")
                return ticket

        logger.error(f"Ticket not found: {ticket_id}")
        return None
