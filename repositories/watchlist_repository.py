from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository
from config.supabase_client import select_rows, is_configured
from utils.time_utils import utc_now_iso

class WatchlistRepository(BaseRepository):
    def __init__(self):
        super().__init__("watchlist")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Align with the extremely minimal watchlist schema found in this workspace."""
        # Based on iterative testing, this table ONLY supports a few core columns.
        # We drop poster, trailer, streaming, and description to ensure persistence.
        return {
            "chat_id":    str(data.get("chat_id", "")),
            "movie_id":   str(data.get("movie_id", "")),
            "title":      data.get("title", ""),
            "added_at":   data.get("added_at") or utc_now_iso()
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Map back to a standard movie object. Metadata will be empty but record exists."""
        return row

    def get_watchlist(self, chat_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        if is_configured():
            rows, error = select_rows(self.table_name, {"chat_id": str(chat_id)}, limit=limit, order="added_at.desc", offset=offset)
            if not error and rows:
                return [self._map_from_supabase(r) for r in rows]
        return []

    def add_to_watchlist(self, chat_id: str, movie: Dict[str, Any]) -> bool:
        payload = {**movie, "chat_id": chat_id, "added_at": utc_now_iso()}
        self.upsert(chat_id, payload, id_field="chat_id,movie_id")
        return True
