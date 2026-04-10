from typing import List, Dict, Optional
from services.logging_service import LoggingService, get_logger

logger = get_logger("recommendation_service")

class RecommendationService:
    """Service layer for recommendation logic with performance optimizations."""

    def __init__(self, watchmode_client=None, trailer_repo=None, discovery_service=None):
        self.watchmode_client = watchmode_client
        self.trailer_repo = trailer_repo
        self.discovery_service = discovery_service

    def _dedup_and_exclude(self, movies: List[Dict], session: Dict) -> List[Dict]:
        last_recs_raw = session.get("last_recs_json") or "[]"
        try:
            import json
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

    async def _enrich_movies_async(self, movies: List[Dict], chat_id: str, intent: str, deferred: bool = False):
        """Fetch trailers and streaming links. If deferred, returns quickly and ignores slow providers."""
        import asyncio
        # If deferred, we only do cheap enrichments (Metadata from OMDb/Mirror is already there)
        # We spawn background tasks for the slow ones.
        tasks = [self._enrich_single_async(m, chat_id, intent) for m in movies]
        await asyncio.gather(*tasks)
        return movies

    async def _enrich_single_async(self, movie, chat_id, intent):
        import asyncio
        movie_id = str(movie.get("movie_id", ""))
        title = movie.get("title", "")
        year = movie.get("year", "")
        
        # Default placeholder for lazy loading
        if "streaming" not in movie:
            movie["streaming"] = "🔄 Loading streaming info..."

        async def get_trailer():
            if not self.trailer_repo: return
            trailer = self.trailer_repo.get_trailer(movie_id)
            if not trailer:
                from clients.omdb_client import get_trailer_url_async
                trailer = await LoggingService.profile_call_async(
                    chat_id, intent, "fetch_trailer", "Standard",
                    get_trailer_url_async, title, year
                )
                if movie_id and trailer:
                    self.trailer_repo.set_trailer(movie_id, trailer)
            movie["trailer"] = trailer

        async def get_streaming():
            if not self.watchmode_client: return
            # Check cache first to avoid async task if already known
            from config.redis_cache import get_json
            cache_key = f"wm_src_{movie_id}"
            cached = get_json(cache_key)
            if cached:
                movie["streaming"] = ", ".join(cached)
                return

            sources = await LoggingService.profile_call_async(
                chat_id, intent, "fetch_streaming", "Watchmode",
                self.watchmode_client.get_streaming_sources, movie_id, title
            )
            if sources:
                movie["streaming"] = ", ".join(sources)
            else:
                movie["streaming"] = "Not currently available on major streaming platforms in India"

        await asyncio.gather(get_trailer(), get_streaming())

    @staticmethod
    def _parse_genre_field(value) -> set:
        if isinstance(value, list):
            return set(g.strip().lower() for g in value if g and g.strip())
        if isinstance(value, str) and value.strip():
            return set(g.strip().lower() for g in value.split(",") if g.strip())
        return set()

    def _rank_candidates(self, movies: List[Dict], user: Dict, min_rating: float = 0.0) -> List[Dict]:
        pref_genres = self._parse_genre_field((user or {}).get("preferred_genres", []))
        dis_genres = self._parse_genre_field((user or {}).get("disliked_genres", []))
        
        ranked_movies = []
        for m in movies:
            m_copy = m.copy()
            score = 0
            m_genres = set(g.strip().lower() for g in m_copy.get("genres", "").split(",") if g.strip())
            
            if pref_genres & m_genres:
                score += 5 * len(pref_genres & m_genres)
            if dis_genres & m_genres:
                score -= 10
            
            try:
                rating = float(m_copy.get("rating") or 0)
                if min_rating > 0 and rating < min_rating:
                    score -= 20
                score += rating
            except (ValueError, TypeError): pass
            m_copy["_score"] = score
            ranked_movies.append(m_copy)
            
        return sorted(ranked_movies, key=lambda x: x.get("_score", 0), reverse=True)

    async def get_recommendations(self, session: Dict, user: Dict, mode: str = "question_engine", 
                            seed_title: str = None, sim_depth: int = 0, limit: int = 14, chat_id: str = "Unknown",
                            min_rating: float = 0.0) -> List[Dict]:
        if not self.discovery_service: return []
        intent = mode
        
        if mode == "similarity" and sim_depth >= 2:
            mode = "question_engine"

        movies = []
        try:
            # Candidate Gen (Passing positional args to avoid profile_call_async collision)
            if mode == "trending":
                movies = await LoggingService.profile_call_async(chat_id, intent, "candidates", "Perplexity", self.discovery_service.get_trending_movies, limit, chat_id)
            elif mode == "surprise":
                movies = await LoggingService.profile_call_async(chat_id, intent, "candidates", "Perplexity", self.discovery_service.get_surprise_movies, limit, chat_id)
            elif mode == "similarity" and seed_title:
                movies = await LoggingService.profile_call_async(chat_id, intent, "candidates", "Perplexity", self.discovery_service.get_similar_movies, seed_title, limit, chat_id)
            else:
                movies = await LoggingService.profile_call_async(chat_id, intent, "candidates", "Perplexity", self.discovery_service.get_question_engine_recs, session, user, limit, chat_id)
        except Exception as e:
            from services.logging_service import get_logger
            get_logger("rec_service").warning(f"Fallback triggered for mode '{mode}' due to: {e}")
            movies = await self.discovery_service.get_backup_essentials(limit=limit)
            # Tag the first movie to notify handlers that this is a fallback
            if movies: movies[0]["_is_fallback"] = True

        movies = self._dedup_and_exclude(movies, session)
        return self._rank_candidates(movies, user, min_rating=min_rating)

    async def enrich_movies(self, movies: List[Dict], chat_id: str, intent: str) -> List[Dict]:
        return await self._enrich_movies_async(movies, chat_id, intent)

    async def background_enrich_single_update(self, chat_id: str, message_id: int, movie: Dict, index: int, total: int, intent: str):
        """Background task to fully enrich a single movie and update its specific Telegram card."""
        import asyncio
        from clients.telegram_helpers import edit_message_caption, edit_message
        
        # 1. Perform full enrichment for this one movie
        await self._enrich_single_async(movie, chat_id, intent)
        
        # 2. Format new caption (matching the original format in send_single_movie_async)
        streaming_text = f"\n   📺 <i>{movie.get('streaming', '')}</i>" if movie.get("streaming") else ""
        caption = f"<b>{index}/{total}: {movie.get('title')}</b>\n\n{movie.get('description', '')[:500]}{streaming_text}"
        
        # 3. Edit message (we use edit_message_caption if it was a photo)
        if movie.get("poster"):
            await edit_message_caption(chat_id, message_id, caption[:1020])
        else:
            await edit_message(chat_id, message_id, caption)
            
        logger.info(f"Background enrichment complete for {movie.get('title')} in chat {chat_id}")

    async def lookup_movie_context(self, title: str, chat_id: str = "Unknown") -> List[Dict]:
        if not self.discovery_service: return []
        movies = await self.discovery_service.lookup_movie_and_similar(title, limit=5, chat_id=chat_id)
        return await self.enrich_movies(movies[:5], chat_id, "lookup")
