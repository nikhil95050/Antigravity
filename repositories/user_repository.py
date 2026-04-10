from typing import Any, Dict, List, Optional
from config.supabase_client import select_rows, is_configured
from .base_repository import BaseRepository
from utils.time_utils import utc_now_iso

class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__("users")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")),
            "username": data.get("username", ""),
            "preferred_genres": data.get("preferred_genres", []) if isinstance(data.get("preferred_genres"), list) else [],
            "disliked_genres": data.get("disliked_genres", []) if isinstance(data.get("disliked_genres"), list) else [],
            "preferred_language": data.get("preferred_language", ""),
            "preferred_era": data.get("preferred_era", ""),
            "watch_context": data.get("watch_context", ""),
            "avg_rating_preference": data.get("avg_rating_preference"),
            "subscriptions": data.get("subscriptions", ""),
            "user_taste_vector": data.get("user_taste_vector", {}),
            "updated_at": utc_now_iso()
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def get_user(self, chat_id: str) -> Dict[str, Any]:
        """Fetch user profile with local/Redis caching."""
        from config.redis_cache import get_json, set_json
        cache_key = f"user:{chat_id}"
        cached = get_json(cache_key)
        if cached: return cached
        
        data = self.get_by_id(chat_id)
        if data:
            set_json(cache_key, data, ttl=3600)
            return data
        return {"chat_id": str(chat_id), "username": "User", "preferred_genres": [], "disliked_genres": []}

    def upsert_user(self, chat_id: str, username: str = None, patch: Dict[str, Any] = None):
        """Standard user upsert with cache invalidation."""
        from config.redis_cache import delete_key
        data = {"chat_id": chat_id}
        if username: data["username"] = username
        if patch: data.update(patch)
        
        self.upsert(chat_id, data)
        delete_key(f"user:{chat_id}")

    def update_preferences(self, chat_id: str, patch: Dict[str, Any]):
        """Specialized update for user preference fields."""
        self.upsert_user(chat_id, patch=patch)
