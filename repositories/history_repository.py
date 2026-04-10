from typing import Any, Dict, List
from datetime import datetime
from .base_repository import BaseRepository
from supabase_client import select_rows, insert_rows, is_configured

class HistoryRepository(BaseRepository):
    def __init__(self):
        super().__init__("history", "History")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")),
            "movie_id": str(data.get("movie_id", "")),
            "title": data.get("title", ""),
            "year": str(data.get("year", "")),
            "genres": data.get("genres", ""),
            "language": data.get("language", ""),
            "rating": str(data.get("rating", "")),
            "description": data.get("description", ""),
            "director": data.get("director", ""),
            "actors": data.get("actors", ""),
            "poster_url": data.get("poster", "") or data.get("poster_url", ""),
            "trailer_url": data.get("trailer", "") or data.get("trailer_url", ""),
            "streaming_info": data.get("streaming", "") or data.get("streaming_info", ""),
            "recommended_at": data.get("recommended_at") or datetime.utcnow().isoformat() + "Z",
            "watched": bool(data.get("watched", False)),
            "watched_at": data.get("watched_at")
        }

    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "Chat ID": int(data["chat_id"]) if str(data["chat_id"]).isdigit() else 0,
            "Movie ID": str(data.get("movie_id", "")),
            "Title": data.get("title", ""),
            "Year": str(data.get("year", "")),
            "Genres": data.get("genres", ""),
            "Language": data.get("language", ""),
            "Rating": str(data.get("rating", "")),
            "Description": data.get("description", ""),
            "Director": data.get("director", ""),
            "Actors": data.get("actors", ""),
            "Poster URL": data.get("poster", "") or data.get("poster_url", ""),
            "Trailer URL": data.get("trailer", "") or data.get("trailer_url", ""),
            "Streaming Info": data.get("streaming", "") or data.get("streaming_info", ""),
            "Recommended At": data.get("recommended_at") or datetime.utcnow().isoformat() + "Z",
            "Watched": bool(data.get("watched", False)),
        }
        watched_at = data.get("watched_at")
        if watched_at:
            payload["Watched At"] = watched_at
        return payload

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
            "genres": record.get("Genres", ""),
            "language": record.get("Language", ""),
            "rating": record.get("Rating", ""),
            "description": record.get("Description", ""),
            "director": record.get("Director", ""),
            "actors": record.get("Actors", ""),
            "poster": record.get("Poster URL", ""),
            "trailer": record.get("Trailer URL", ""),
            "streaming": record.get("Streaming Info", ""),
            "recommended_at": record.get("Recommended At", ""),
            "watched": bool(record.get("Watched", False)),
            "watched_at": record.get("Watched At", "")
        }

    def get_user_history(self, chat_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        if is_configured():
            rows, error = select_rows(self.table_name, {"chat_id": str(chat_id)}, limit=limit, order="recommended_at.desc")
            if not error and rows:
                return [self._map_from_supabase(r) for r in rows]
        
        # Fallback to Airtable
        from airtable_client import is_airtable_available, get_table
        if is_airtable_available():
            try:
                table = get_table(self.airtable_name)
                records = table.all(formula=f"{{Chat ID}}={chat_id}", sort=["-Recommended At"])
                return [self._map_from_airtable(r["fields"]) for r in records[:limit]]
            except: pass
        return []

    def log_recommendations(self, chat_id: str, movies: List[Dict[str, Any]]):
        ts = datetime.utcnow().isoformat() + "Z"
        payloads = [{**movie, "recommended_at": ts} for movie in movies]
        self.bulk_upsert(chat_id, payloads, id_field="chat_id,movie_id")
            
    def insert(self, data: Dict[str, Any]):
        """Legacy support or specific inserts."""
        self.upsert(data.get("chat_id"), data, id_field="chat_id,movie_id")
