from repositories.history_repository import HistoryRepository
from repositories.watchlist_repository import WatchlistRepository
from typing import List, Dict, Optional

class MovieService:
    def __init__(self):
        self.history_repo = HistoryRepository()
        self.watchlist_repo = WatchlistRepository()

    def get_history(self, chat_id: str, limit: int = 20) -> List[Dict]:
        return self.history_repo.get_user_history(chat_id, limit)

    def add_to_history(self, chat_id: str, movies: List[Dict]):
        self.history_repo.log_recommendations(chat_id, movies)

    def mark_as_watched(self, chat_id: str, movie_id: str):
        self.history_repo.update_watched(chat_id, movie_id, watched=True)

    def get_watchlist(self, chat_id: str, limit: int = 25) -> List[Dict]:
        return self.watchlist_repo.get_watchlist(chat_id, limit)

    def add_to_watchlist(self, chat_id: str, movie: Dict) -> bool:
        return self.watchlist_repo.add_to_watchlist(chat_id, movie)

    def get_movie_from_history(self, chat_id: str, movie_id: str) -> Optional[Dict]:
        """Fetch a specific movie from history with full metadata."""
        # Note: HistoryRepository doesn't have a direct get_by_both yet, 
        # but we can filter the get_user_history list for now or add a helper.
        history = self.get_history(chat_id, limit=200)
        for m in history:
            if str(m.get("movie_id")) == str(movie_id):
                return m
        return None
