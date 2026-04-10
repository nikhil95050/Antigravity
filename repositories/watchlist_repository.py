from typing import Any, Dict, List, Optional
from datetime import datetime
from .base_repository import BaseRepository
from supabase_client import select_rows, insert_rows, is_configured

class WatchlistRepository(BaseRepository):
    def __init__(self):
        super().__init__("watchlist", "Watchlist")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")),
            "movie_id": str(data.get("movie_id", "")),
            "title": data.get("title", ""),
            "year": str(data.get("year", "")),
            "language": data.get("language", ""),
            "rating": str(data.get("rating", "")),
            "genres": data.get("genres", ""),
            "description": data.get("description", ""),
            "director": data.get("director", ""),
            "actors": data.get("actors", ""),
            "poster_url": data.get("poster", "") or data.get("poster_url", ""),
            "trailer_url": data.get("trailer", "") or data.get("trailer_url", ""),
            "streaming_info": data.get("streaming", "") or data.get("streaming_info", ""),
            "added_at": data.get("added_at") or datetime.utcnow().isoformat() + "Z"
        }

    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Chat ID": int(data["chat_id"]) if str(data["chat_id"]).isdigit() else 0,
            "Movie ID": str(data.get("movie_id", "")),
            "Title": data.get("title", ""),
            "Year": str(data.get("year", "")),
            "Language": data.get("language", ""),
            "Rating": str(data.get("rating", "")),
            "Genres": data.get("genres", ""),
            "Description": data.get("description", ""),
            "Director": data.get("director", ""),
            "Actors": data.get("actors", ""),
            "Poster URL": data.get("poster", "") or data.get("poster_url", ""),
            "Trailer URL": data.get("trailer", "") or data.get("trailer_url", ""),
            "Streaming Info": data.get("streaming", "") or data.get("streaming_info", ""),
            "Added At": data.get("added_at") or datetime.utcnow().isoformat() + "Z"
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **row,
            "poster": row.get("poster_url"),
            "trailer": row.get("trailer_url"),
            "streaming": row.get("streaming_info")
        }

    def _map_from_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(record.get("Chat ID", "")),
            "movie_id": record.get("Movie ID", ""),
            "title": record.get("Title", ""),
            "year": record.get("Year", ""),
            "language": record.get("Language", ""),
            "rating": record.get("Rating", ""),
            "genres": record.get("Genres", ""),
            "description": record.get("Description", ""),
            "director": record.get("Director", ""),
            "actors": record.get("Actors", ""),
            "poster": record.get("Poster URL", ""),
            "poster_url": record.get("Poster URL", ""),
            "trailer": record.get("Trailer URL", ""),
            "trailer_url": record.get("Trailer URL", ""),
            "streaming": record.get("Streaming Info", ""),
            "streaming_info": record.get("Streaming Info", ""),
            "added_at": record.get("Added At", "")
        }

    def get_watchlist(self, chat_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        if is_configured():
            rows, error = select_rows(self.table_name, {"chat_id": str(chat_id)}, limit=limit, order="added_at.desc")
            if not error and rows:
                return [self._map_from_supabase(r) for r in rows]
        
        # Fallback to Airtable
        from airtable_client import is_airtable_available, get_table
        if is_airtable_available():
            try:
                table = get_table(self.airtable_name)
                records = table.all(formula=f"{{Chat ID}}={chat_id}", sort=["-Added At"])
                return [self._map_from_airtable(r["fields"]) for r in records[:limit]]
            except: pass
        return []

    def add_to_watchlist(self, chat_id: str, movie: Dict[str, Any]) -> bool:
        """Add movie to watchlist with deduplication."""
        payload = {**movie, "chat_id": chat_id, "added_at": datetime.utcnow().isoformat() + "Z"}
        self.upsert(chat_id, payload, id_field="chat_id,movie_id")
        return True
