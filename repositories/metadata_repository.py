from typing import Any, Dict, Optional
from .base_repository import BaseRepository
from utils.time_utils import utc_now_iso
import json

class MetadataRepository(BaseRepository):
    """
    Repository for permanent storage of movie metadata (OMDb/Watchmode).
    Acts as a Level 2 mirror to reduce external API dependency.
    """
    def __init__(self):
        super().__init__("movie_metadata")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "movie_id": data.get("movie_id"),
            "data_json": json.dumps(data) if isinstance(data, dict) else data,
            "last_updated": utc_now_iso(),
            "chat_id": "system" # BaseRepository expects chat_id
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        raw = row.get("data_json")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except:
                return {}
        return raw or {}

    def get_metadata(self, movie_id: str) -> Optional[Dict[str, Any]]:
        # Check cache then Supabase
        return self.get_by_id(movie_id, id_field="movie_id")

    def upsert_metadata(self, movie_id: str, data: Dict[str, Any]):
        self.upsert(movie_id, data, id_field="movie_id")
