import json
import concurrent.futures
from typing import List, Dict
from adapters.apify_adapter import ApifyAdapter
from adapters.watchmode_adapter import WatchmodeAdapter
from repositories.trailer_repository import TrailerRepository
from services.logging_service import LoggingService
from movie_data import (
    get_trending_movies,
    get_surprise_movies,
    get_similar_movies,
    get_question_engine_recs,
    lookup_movie_and_similar
)

class RecommendationService:
    """Service layer for recommendation logic with performance optimizations."""

    def __init__(self):
        self.apify_adapter = ApifyAdapter()
        self.watchmode_adapter = WatchmodeAdapter()
        self.trailer_repo = TrailerRepository()

    def _dedup_and_exclude(self, movies: List[Dict], session: Dict) -> List[Dict]:
        last_recs_raw = session.get("last_recs_json") or "[]"
        try:
            last_recs = json.loads(last_recs_raw) if isinstance(last_recs_raw, str) else last_recs_raw
            exclude_ids = {str(m.get("movie_id", "")) for m in last_recs}
        except Exception:
            exclude_ids = set()

        seen = set()
        result = []
        for m in movies:
            mid = str(m.get("movie_id", ""))
            if mid and mid not in exclude_ids and mid not in seen and m.get("title"):
                seen.add(mid)
                result.append(m)
        return result

    def _enrich_movies_parallel(self, movies: List[Dict], chat_id: str, intent: str):
        """Fetch trailers and streaming links in parallel for maximum speed."""
        
        def enrich_single(movie):
            movie_id = str(movie.get("movie_id", ""))
            title = movie.get("title", "")
            year = movie.get("year", "")
            
            # 1. Trailer (Repo or API)
            trailer = self.trailer_repo.get_trailer(movie_id)
            if not trailer:
                trailer = LoggingService.profile_call(
                    chat_id, intent, "fetch_trailer", "Apify",
                    self.apify_adapter.get_trailer, title, year
                )
                if movie_id and trailer:
                    self.trailer_repo.set_trailer(movie_id, trailer)
            movie["trailer"] = trailer
            
            # 2. Watchmode Streaming links
            sources = LoggingService.profile_call(
                chat_id, intent, "fetch_streaming", "Watchmode",
                self.watchmode_adapter.get_streaming_sources, movie_id, title
            )
            # EXPLICIT FALLBACK for India region as requested by user
            if sources:
                movie["streaming"] = ", ".join(sources)
            else:
                movie["streaming"] = "Not currently available on major streaming platforms in India"

        # Limit workers to 5 since that is our typical delivery batch
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            executor.map(enrich_single, movies)
        
        return movies

    def _rank_candidates(self, movies: List[Dict], user: Dict) -> List[Dict]:
        """Rank candidates based on user preferences."""
        pref_genres = set(g.strip().lower() for g in (user or {}).get("preferred_genres", "").split(",") if g.strip())
        dis_genres = set(g.strip().lower() for g in (user or {}).get("disliked_genres", "").split(",") if g.strip())
        
        for m in movies:
            score = 0
            m_genres = set(g.strip().lower() for g in m.get("genres", "").split(",") if g.strip())
            
            if pref_genres & m_genres:
                score += 5 * len(pref_genres & m_genres)
            if dis_genres & m_genres:
                score -= 10
            
            try:
                rating = float(m.get("rating") or 0)
                score += rating
            except: pass
            m["_score"] = score
            
        return sorted(movies, key=lambda x: x.get("_score", 0), reverse=True)

    def get_recommendations(self, session: Dict, user: Dict, mode: str = "question_engine", 
                            seed_title: str = None, sim_depth: int = 0) -> List[Dict]:
        chat_id = (user or {}).get("chat_id", "Unknown")
        intent = mode
        
        # Increase candidate limit to 14 to allow for multi-page iterations
        limit = 14
        
        if mode == "similarity" and sim_depth >= 2:
            mode = "question_engine"

        # Candidate Gen (Profiled)
        if mode == "trending":
            movies = LoggingService.profile_call(chat_id, intent, "candidates", "Perplexity", get_trending_movies, limit=limit)
        elif mode == "surprise":
            movies = LoggingService.profile_call(chat_id, intent, "candidates", "Perplexity", get_surprise_movies, limit=limit)
        elif mode == "similarity" and seed_title:
            movies = LoggingService.profile_call(chat_id, intent, "candidates", "Perplexity", get_similar_movies, seed_title, limit=limit)
        else:
            # For question engine, fetch a larger pool so "Next 5" feels instant
            movies = LoggingService.profile_call(chat_id, intent, "candidates", "Perplexity", get_question_engine_recs, session, user, limit=limit)

        movies = self._dedup_and_exclude(movies, session)
        movies = self._rank_candidates(movies, user)
        # Process ONLY 5 movies at a time for the current request
        return self._enrich_movies_parallel(movies[:5], chat_id, intent)

    def lookup_movie_context(self, title: str) -> List[Dict]:
        # Profiling individual lookup
        movies = lookup_movie_and_similar(title, limit=5)
        # Standardize individual lookups to 5
        return self._enrich_movies_parallel(movies[:5], "Unknown", "lookup")
