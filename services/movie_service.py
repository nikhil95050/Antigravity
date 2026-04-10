from typing import List, Dict, Optional

class MovieService:
    def __init__(self, history_repo=None, watchlist_repo=None):
        self.history_repo = history_repo
        self.watchlist_repo = watchlist_repo

    def get_history(self, chat_id: str, limit: int = 10, offset: int = 0) -> List[Dict]:
        if not self.history_repo: return []
        return self.history_repo.get_user_history(chat_id, limit, offset)

    def add_to_history(self, chat_id: str, movies: List[Dict]):
        if not self.history_repo: return
        self.history_repo.log_recommendations(chat_id, movies)

    def mark_watched(self, chat_id: str, movie_id: str):
        if not self.history_repo: return
        self.history_repo.update_watched(chat_id, movie_id, watched=True)

    def get_watchlist(self, chat_id: str, limit: int = 10, offset: int = 0) -> List[Dict]:
        if not self.watchlist_repo: return []
        return self.watchlist_repo.get_watchlist(chat_id, limit, offset)

    def add_to_watchlist(self, chat_id: str, movie: Dict) -> bool:
        if not self.watchlist_repo: return False
        return self.watchlist_repo.add_to_watchlist(chat_id, movie)

    def get_movie_from_history(self, chat_id: str, movie_id: str) -> Optional[Dict]:
        """Fetch a specific movie from history with full metadata (O(1))."""
        if not self.history_repo: return None
        return self.history_repo.get_entry(chat_id, movie_id)

    def get_random_watchlist_reminder(self, chat_id: str) -> Optional[Dict]:
        """Fetch a single random movie from the user's watchlist for a reminder."""
        wl = self.get_watchlist(chat_id, limit=50)
        unwatched = [m for m in wl if not m.get("watched")]
        if not unwatched:
            return None
        import random
        return random.choice(unwatched)
