from typing import Any, Dict
from datetime import datetime
from .base_repository import BaseRepository

class FeedbackRepository(BaseRepository):
    """Repository for user feedback (Likes/Dislikes) with full mirroring and background safety."""

    def __init__(self):
        super().__init__("feedback", "Feedback")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")),
            "movie_id": str(data.get("movie_id", "")),
            "reaction_type": str(data.get("reaction_type", "")).lower(),
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat() + "Z"
        }

    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Chat ID": int(data["chat_id"]) if str(data["chat_id"]).isdigit() else 0,
            "Movie ID": str(data.get("movie_id", "")),
            "Reaction Type": str(data.get("reaction_type", "")).title(),
            "Timestamp": data.get("timestamp") or datetime.utcnow().isoformat() + "Z"
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def _map_from_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(record.get("Chat ID", "")),
            "movie_id": record.get("Movie ID", ""),
            "reaction_type": str(record.get("Reaction Type", "")).lower(),
            "timestamp": record.get("Timestamp", "")
        }

    def log_reaction(self, chat_id: str, movie_id: str, reaction: str):
        """Logs a 'like' or 'dislike' reaction safely."""
        payload = {
            "chat_id": chat_id,
            "movie_id": movie_id,
            "reaction_type": reaction,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        # Reactions are unique per user+movie. Handled via upsert in background thread.
        try:
            self.upsert(chat_id, payload, id_field="chat_id,movie_id")
        except Exception as e:
            print(f"[Feedback] Reaction log failed: {e}")
