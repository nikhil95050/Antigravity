from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_repository import BaseRepository
from utils.time_utils import utc_now_iso
from config.supabase_client import select_rows, update_rows, is_configured
from config.redis_cache import get_json as cache_get_json, set_json as cache_set_json

class HistoryRepository(BaseRepository):
    def __init__(self):
        super().__init__("history")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Align with physical schema discovered during E2E testing. 
        Metadata columns (actors, director) are currently missing from the live DB.
        """
        return {
            "chat_id":        str(data.get("chat_id", "")),
            "movie_id":       str(data.get("movie_id", "")),
            "title":          data.get("title", ""),
            "year":           str(data.get("year", "")),
            "genres":         data.get("genres", ""),
            "language":       data.get("language", ""),
            "rating":         str(data.get("rating", "")),
            "recommended_at": data.get("recommended_at") or utc_now_iso(),
            "watched":        bool(data.get("watched", False)),
            "watched_at":     data.get("watched_at")
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def get_entry(self, chat_id: str, movie_id: str) -> Optional[Dict[str, Any]]:
        if not is_configured(): return None
        filters = {"chat_id": str(chat_id), "movie_id": str(movie_id)}
        rows, err = select_rows(self.table_name, filters, limit=1)
        if not err and rows:
            return self._map_from_supabase(rows[0])
        return None

    def get_user_history(self, chat_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        cache_key = f"history:{chat_id}:{limit}:{offset}"
        cached = cache_get_json(cache_key)
        if cached: return cached

        if is_configured():
            rows, error = select_rows(self.table_name, {"chat_id": str(chat_id)}, limit=limit, order="recommended_at.desc", offset=offset)
            if not error and rows:
                data = [self._map_from_supabase(r) for r in rows]
                cache_set_json(cache_key, data, ttl=600)
                return data
        return []

    def log_recommendations(self, chat_id: str, movies: List[Dict[str, Any]]):
        from config.redis_cache import delete_prefix
        delete_prefix(f"history:{chat_id}:")
        self.bulk_upsert(chat_id, movies, id_field="chat_id,movie_id")
            
    def update_watched(self, chat_id: str, movie_id: str, watched: bool = True):
        visited_at = utc_now_iso() if watched else None
        if is_configured():
            patch = {"watched": watched, "watched_at": visited_at}
            self._bg(update_rows, self.table_name, patch, {"chat_id": str(chat_id), "movie_id": str(movie_id)})
            from config.redis_cache import delete_prefix
            delete_prefix(f"history:{chat_id}:")
