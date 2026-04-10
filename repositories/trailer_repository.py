from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository
from utils.time_utils import utc_now_iso

class TrailerRepository(BaseRepository):
    def __init__(self):
        super().__init__("trailer_cache")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "movie_id": str(data.get("movie_id", "")),
            "trailer_url": data.get("trailer_url", ""),
            "cached_at": data.get("cached_at") or utc_now_iso()
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def get_trailer(self, movie_id: str) -> Optional[str]:
        data = self.get_by_id(movie_id, id_field="movie_id")
        return data.get("trailer_url") if data else None

    def set_trailer(self, movie_id: str, trailer_url: str):
        payload = {
            "movie_id": movie_id,
            "trailer_url": trailer_url,
            "cached_at": utc_now_iso()
        }
        self.upsert(movie_id, payload, id_field="movie_id")
