from typing import Any, Dict
from datetime import datetime
from .base_repository import BaseRepository

class SessionRepository(BaseRepository):
    def __init__(self):
        super().__init__("sessions", "Sessions")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")),
            "session_state": data.get("session_state", "idle"),
            "question_index": int(data.get("question_index", 0)),
            "pending_question": data.get("pending_question", ""),
            "answers_mood": data.get("answers_mood", ""),
            "answers_genre": data.get("answers_genre", ""),
            "answers_language": data.get("answers_language", ""),
            "answers_era": data.get("answers_era", ""),
            "answers_context": data.get("answers_context", ""),
            "answers_time": data.get("answers_time", ""),
            "answers_avoid": data.get("answers_avoid", ""),
            "answers_favorites": data.get("answers_favorites", ""),
            "last_question_msg_id": data.get("last_question_msg_id"),
            "last_recs_json": data.get("last_recs_json", "[]"),
            "sim_depth": int(data.get("sim_depth", 0)),
            "last_active": data.get("last_active") or datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Chat ID": int(data["chat_id"]) if str(data["chat_id"]).isdigit() else 0,
            "Session State": data.get("session_state", "idle"),
            "Question Index": int(data.get("question_index", 0)),
            "Pending Question": data.get("pending_question", ""),
            "Answers Mood": data.get("answers_mood", ""),
            "Answers Genre": data.get("answers_genre", ""),
            "Answers Language": data.get("answers_language", ""),
            "Answers Era": data.get("answers_era", ""),
            "Answers Context": data.get("answers_context", ""),
            "Answers Time": data.get("answers_time", ""),
            "Answers Avoid": data.get("answers_avoid", ""),
            "Answers Favorites": data.get("answers_favorites", ""),
            "Last Question Msg ID": str(data.get("last_question_msg_id", "")),
            "Last Recs JSON": data.get("last_recs_json", "[]"),
            "Sim Depth": int(data.get("sim_depth", 0)),
            "Last Active": data.get("last_active") or datetime.utcnow().isoformat() + "Z",
            "Updated At": datetime.utcnow().isoformat() + "Z"
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def _map_from_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(record.get("Chat ID", "")),
            "session_state": record.get("Session State", "idle"),
            "question_index": record.get("Question Index", 0),
            "pending_question": record.get("Pending Question", ""),
            "answers_mood": record.get("Answers Mood", ""),
            "answers_genre": record.get("Answers Genre", ""),
            "answers_language": record.get("Answers Language", ""),
            "answers_era": record.get("Answers Era", ""),
            "answers_context": record.get("Answers Context", ""),
            "answers_time": record.get("Answers Time", ""),
            "answers_avoid": record.get("Answers Avoid", ""),
            "answers_favorites": record.get("Answers Favorites", ""),
            "last_question_msg_id": int(record.get("Last Question Msg ID")) if str(record.get("Last Question Msg ID", "")).isdigit() else None,
            "last_recs_json": record.get("Last Recs JSON", "[]"),
            "sim_depth": record.get("Sim Depth", 0),
            "last_active": record.get("Last Active", ""),
            "updated_at": record.get("Updated At", "")
        }
