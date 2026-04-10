from typing import Dict, Any, Optional
from .base_repository import BaseRepository
from utils.time_utils import utc_now_iso


class SessionRepository(BaseRepository):
    def __init__(self):
        super().__init__("sessions")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Align mapping with current database schema to avoid 400 errors."""
        return {
            "chat_id":               str(data.get("chat_id", "")),
            "session_state":         data.get("session_state", "idle"),
            "question_index":        int(data.get("question_index", 0)),
            "pending_question":      data.get("pending_question", ""),
            "answers_mood":          data.get("answers_mood", ""),
            "answers_genre":         data.get("answers_genre", ""),
            "answers_language":      data.get("answers_language", ""),
            "answers_era":           data.get("answers_era", ""),
            "answers_context":       data.get("answers_context", ""),
            "answers_time":          data.get("answers_time", ""),
            "answers_avoid":         data.get("answers_avoid", ""),
            "answers_favorites":     data.get("answers_favorites", ""),
            "last_question_msg_id":  data.get("last_question_msg_id"),
            "last_recs_json":        data.get("last_recs_json", "[]"),
            "sim_depth":             int(data.get("sim_depth", 0)),
            "last_active":           data.get("last_active") or utc_now_iso(),
            "updated_at":            utc_now_iso(),
            # REMOVED: answers_rating, overflow_buffer_json (causing schema mismatches)
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def get_session(self, chat_id: str) -> Dict[str, Any]:
        from config.redis_cache import get_json, set_json
        cache_key = f"session:{chat_id}"
        cached = get_json(cache_key)
        if cached: return cached
        
        data = self.get_by_id(chat_id)
        if data:
            set_json(cache_key, data, ttl=3600)
            return data
        return {"chat_id": str(chat_id), "session_state": "idle", "question_index": 0}

    def upsert_session(self, chat_id: str, patch: Dict[str, Any]):
        from config.redis_cache import delete_key
        # Atomic background write
        self.upsert(chat_id, patch)
        # Immediate cache invalidation
        delete_key(f"session:{chat_id}")

    def reset_session(self, chat_id: str):
        defaults = {
            "session_state": "idle",
            "question_index": 0,
            "pending_question": "",
            "answers_mood": "",
            "answers_genre": "",
            "answers_language": "",
            "answers_era": "",
            "answers_context": "",
            "answers_time": "",
            "answers_avoid": "",
            "answers_favorites": "",
            "last_recs_json": "[]",
            "sim_depth": 0,
            "updated_at": utc_now_iso()
        }
        self.upsert_session(chat_id, defaults)