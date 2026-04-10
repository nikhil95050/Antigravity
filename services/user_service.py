from typing import List, Dict, Any, Optional

class UserService:
    def __init__(self, user_repo=None):
        self.user_repo = user_repo

    def get_user(self, chat_id: str) -> Dict[str, Any]:
        if not self.user_repo: return {"chat_id": str(chat_id)}
        return self.user_repo.get_user(chat_id)

    def upsert_user(self, chat_id: str, username: str, patch: Dict[str, Any] = None):
        if not self.user_repo: return
        self.user_repo.upsert_user(chat_id, username, patch)

    def update_preferences(self, chat_id: str, patch: Dict[str, Any]):
        if not self.user_repo: return
        self.user_repo.update_preferences(chat_id, patch)

    def add_preference(self, chat_id: str, genres: str, liked: bool = True):
        """Manually add or remove a genre preference from the user's profile."""
        if not self.user_repo: return
        user = self.get_user(chat_id)
        field = "preferred_genres" if liked else "disliked_genres"
        
        current = user.get(field, [])
        if not isinstance(current, list): current = []
        
        # New genres to add
        new_list = [g.strip() for g in genres.split(",") if g.strip()]
        
        updated = list(set(current + new_list))
        self.update_preferences(chat_id, {field: updated})

    async def recompute_taste_profile(self, chat_id: str):
        """Analyze recent positive feedback to update permanent user preferences (Genres, Directors, Actors)."""
        if not self.user_repo: return
        
        from config.supabase_client import select_rows
        # 1. Fetch recent likes
        rows, _ = select_rows("feedback", {"chat_id": str(chat_id), "reaction_type": "like"}, limit=30)
        if not rows: return

        # 2. Extract multidimensional data
        from repositories.history_repository import HistoryRepository
        history_repo = HistoryRepository()
        
        genre_counts = {}
        actor_counts = {}
        director_counts = {}
        
        for r in rows:
            movie = history_repo.get_movie_from_history(chat_id, r["movie_id"])
            if not movie: continue
            
            # Genres
            if movie.get("genres"):
                genres = [g.strip() for g in movie["genres"].split(",") if g.strip()]
                for g in genres: genre_counts[g] = genre_counts.get(g, 0) + 1
            
            # Actors
            if movie.get("actors"):
                actors = [a.strip() for a in movie["actors"].split(",") if a.strip()]
                for a in actors: actor_counts[a] = actor_counts.get(a, 0) + 1

            # Director
            if movie.get("director"):
                dirs = [d.strip() for d in movie["director"].split(",") if d.strip()]
                for d in dirs: director_counts[d] = director_counts.get(d, 0) + 1
        
        # 3. Identify Top Entities
        get_top = lambda d, n: [k[0] for k in sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]]
        
        top_genres = get_top(genre_counts, 3)
        top_actors = get_top(actor_counts, 5)
        top_directors = get_top(director_counts, 3)
        
        # 4. Update Profile & Taste Vector
        taste_vector = {
            "top_actors": top_actors,
            "top_directors": top_directors,
            "last_liked_genres": top_genres,
            "updated_at": utc_now_iso()
        }
        
        self.update_preferences(chat_id, {
            "preferred_genres": top_genres,
            "user_taste_vector": taste_vector
        })
        
        from services.logging_service import get_logger
        get_logger("user_service").info(f"Updated Taste Vector for {chat_id}: {len(top_actors)} actors, {len(top_directors)} directors.")
