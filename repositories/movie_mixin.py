from typing import Dict, Any

class MovieFieldsMixin:
    """Shared logic for mapping movie fields to/from Supabase."""

    @staticmethod
    def _map_movie_to_supabase(data: Dict[str, Any]) -> Dict[str, Any]:
        """Maps standard movie object to database columns, filtered for safe schema."""
        # We REMOVE director, actors, and other potentially missing columns to avoid 400 errors.
        return {
            "movie_id":       str(data.get("movie_id", "")),
            "title":          data.get("title", ""),
            "year":           str(data.get("year", "")),
            "genres":         data.get("genres", ""),
            "language":       data.get("language", ""),
            "description":    data.get("description", ""),
            "poster_url":     data.get("poster", "") or data.get("poster_url", ""),
            "trailer_url":    data.get("trailer", "") or data.get("trailer_url", ""),
            "streaming_info": data.get("streaming", "") or data.get("streaming_info", ""),
        }

    @staticmethod
    def _map_movie_from_supabase(row: Dict[str, Any]) -> Dict[str, Any]:
        """Maps database columns back to standard movie object."""
        return {
            **row,
            "poster":    row.get("poster_url"),
            "trailer":   row.get("trailer_url"),
            "streaming": row.get("streaming_info"),
        }
