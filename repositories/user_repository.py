from typing import Any, Dict
from datetime import datetime
from .base_repository import BaseRepository

class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__("users", "Users")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")),
            "username": data.get("username", ""),
            "preferred_genres": data.get("preferred_genres", ""),
            "disliked_genres": data.get("disliked_genres", ""),
            "preferred_language": data.get("preferred_language", ""),
            "preferred_era": data.get("preferred_era", ""),
            "watch_context": data.get("watch_context", ""),
            "avg_rating_preference": data.get("avg_rating_preference"),
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Chat ID": int(data["chat_id"]) if str(data["chat_id"]).isdigit() else 0,
            "Username": data.get("username", ""),
            "Preferred Genres": data.get("preferred_genres", ""),
            "Disliked Genres": data.get("disliked_genres", ""),
            "Preferred Language": data.get("preferred_language", ""),
            "Preferred Era": data.get("preferred_era", ""),
            "Watch Context": data.get("watch_context", ""),
            "Avg Rating Preference": data.get("avg_rating_preference"),
            "Updated At": datetime.utcnow().isoformat() + "Z"
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def _map_from_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(record.get("Chat ID", "")),
            "username": record.get("Username", ""),
            "preferred_genres": record.get("Preferred Genres", ""),
            "disliked_genres": record.get("Disliked Genres", ""),
            "preferred_language": record.get("Preferred Language", ""),
            "preferred_era": record.get("Preferred Era", ""),
            "watch_context": record.get("Watch Context", ""),
            "avg_rating_preference": record.get("Avg Rating Preference"),
            "updated_at": record.get("Updated At", "")
        }
