from repositories.session_repository import SessionRepository
from typing import Dict, Optional

class SessionService:
    def __init__(self):
        self.repo = SessionRepository()

    def get_session(self, chat_id: str) -> Dict:
        return self.repo.get_by_id(chat_id) or {}

    def upsert_session(self, chat_id: str, patch: Dict):
        # In a real service, we might do more validation here
        self.repo.upsert(chat_id, patch)

    def reset_session(self, chat_id: str):
        self.repo.upsert(chat_id, {
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
            "last_question_msg_id": None,
            "last_recs_json": "[]",
            "sim_depth": 0
        })
