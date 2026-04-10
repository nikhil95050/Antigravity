from repositories.user_repository import UserRepository
from typing import Dict, Optional

class UserService:
    def __init__(self):
        self.repo = UserRepository()

    def get_user(self, chat_id: str) -> Dict:
        return self.repo.get_by_id(chat_id) or {}

    def upsert_user(self, chat_id: str, username: str, patch: Dict = None):
        data = patch or {}
        if username:
            data["username"] = username
        self.repo.upsert(chat_id, data)

    def add_preference(self, chat_id: str, genres: str, liked: bool = True):
        user = self.get_user(chat_id)
        field = "preferred_genres" if liked else "disliked_genres"
        current = user.get(field, "")
        
        new_genres = set(g.strip() for g in current.split(",") if g.strip())
        new_genres.update(g.strip() for g in genres.split(",") if g.strip())
        
        self.upsert_user(chat_id, user.get("username"), {field: ", ".join(sorted(new_genres))})
