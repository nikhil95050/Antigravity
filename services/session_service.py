from typing import List, Dict, Any, Optional

class SessionService:
    def __init__(self, session_repo=None):
        self.session_repo = session_repo

    def get_session(self, chat_id: str) -> Dict[str, Any]:
        if not self.session_repo: return {"chat_id": str(chat_id)}
        return self.session_repo.get_session(chat_id)

    def upsert_session(self, chat_id: str, patch: Dict[str, Any]):
        if not self.session_repo: return
        self.session_repo.upsert_session(chat_id, patch)

    def reset_session(self, chat_id: str):
        if not self.session_repo: return
        self.session_repo.reset_session(chat_id)
