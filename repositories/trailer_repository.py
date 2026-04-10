from typing import Any, Dict, Optional
from datetime import datetime
from .base_repository import BaseRepository
from supabase_client import select_rows, insert_rows, is_configured

class TrailerRepository(BaseRepository):
    def __init__(self):
        super().__init__("trailer_cache", "Trailer Cache")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "movie_id": str(data.get("movie_id", "")),
            "trailer_url": data.get("trailer_url", ""),
            "cached_at": data.get("cached_at") or datetime.utcnow().isoformat() + "Z"
        }

    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Movie ID": str(data.get("movie_id", "")),
            "Trailer URL": data.get("trailer_url", ""),
            "Cached At": data.get("cached_at") or datetime.utcnow().isoformat() + "Z"
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def _map_from_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "movie_id": str(record.get("Movie ID", "")),
            "trailer_url": record.get("Trailer URL", ""),
            "cached_at": record.get("Cached At", "")
        }

    def get_trailer(self, movie_id: str) -> Optional[str]:
        data = self.get_by_id(movie_id, id_field="movie_id")
        return data.get("trailer_url") if data else None

    def set_trailer(self, movie_id: str, trailer_url: str):
        payload = {
            "movie_id": movie_id,
            "trailer_url": trailer_url,
            "cached_at": datetime.utcnow().isoformat() + "Z"
        }
        self.upsert(movie_id, payload, id_field="movie_id")
