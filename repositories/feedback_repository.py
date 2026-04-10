from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository
from utils.time_utils import utc_now_iso

class FeedbackRepository(BaseRepository):
    """Repository for user feedback (Likes/Dislikes)."""

    def __init__(self):
        super().__init__("feedback")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")), # Added missing chat_id
            "movie_id": str(data.get("movie_id", "")),
            "reaction_type": str(data.get("reaction_type", "")).lower(),
            "timestamp": data.get("timestamp") or utc_now_iso()
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def log_reaction(self, chat_id: str, movie_id: str, reaction: str):
        """Logs a 'like' or 'dislike' reaction safely."""
        payload = {
            "chat_id": str(chat_id),
            "movie_id": str(movie_id),
            "reaction_type": str(reaction).lower(),
            "timestamp": utc_now_iso()
        }
        try:
            self.upsert(chat_id, payload, id_field="chat_id,movie_id")
        except Exception as e:
            from services.logging_service import get_logger
            get_logger("feedback_repo").error(f"Reaction log failed for user {chat_id}: {e}")

    def add_feedback(self, chat_id: str, movie_id: str, reaction: str):
        """Alias for log_reaction to match testing and service naming conventions."""
        return self.log_reaction(chat_id, movie_id, reaction)
