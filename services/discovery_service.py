import json
import random
import asyncio
import re
from typing import List, Dict
from services.logging_service import get_logger

logger = get_logger("discovery_service")

class DiscoveryService:
    def __init__(self, shared_client=None):
        # We NO LONGER import container here to avoid circularity.
        # The container MUST pass the shared_client during instantiation.
        self.client = shared_client

    async def _get_titles_from_perplexity(self, prompt: str, limit: int = 5, chat_id: str = "system") -> List[str]:
        """Helper to get a list of movie titles from Perplexity with Semantic Caching."""
        from config.redis_cache import get_json, set_json
        import hashlib
        
        # 1. Semantic Cache Check
        prompt_hash = hashlib.sha256(prompt.lower().encode()).hexdigest()
        cache_key = f"prompt_cache:{prompt_hash}"
        cached = get_json(cache_key)
        if cached:
            logger.info(f"Semantic Cache HIT for prompt: {prompt[:30]}...")
            return cached[:limit]

        from clients.perplexity_client import ask_perplexity
        # Enforce strict JSON output
        strict_prompt = prompt + " Return ONLY a JSON array of strings. No conversational text."
        raw = await ask_perplexity(strict_prompt, chat_id=chat_id)
        if not raw: return []
        
        # Try regex extraction for JSON array
        titles = []
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                titles = json.loads(match.group(0))
        except Exception as e:
            logger.debug(f"JSON extract failed for perplexity output: {e}")
        
        if not titles:
            # Fallback to line-based parsing
            lines = [l.strip().strip('"').strip("'").strip("-").strip() for l in raw.split("\n") if l.strip()]
            titles = [l for l in lines if len(l) > 2 and len(l) < 100 and ":" not in l]

        if titles:
            set_json(cache_key, titles, ttl=86400) # Cache for 24h
        
        return titles[:limit]

    async def get_trending_movies(self, limit: int = 8, chat_id: str = "system") -> List[Dict]:
        from config.redis_cache import get_json, set_json
        from clients.omdb_client import fetch_movies_by_titles_async
        
        cache_key = "global_trending_movies"
        cached = get_json(cache_key)
        if cached:
            return cached[:limit]

        prompt = f"Return a list of {limit} trending movies. JSON array of titles."
        titles = await self._get_titles_from_perplexity(prompt, limit, chat_id)
        movies = await fetch_movies_by_titles_async(titles)
        
        if movies:
            set_json(cache_key, movies, ttl=3600)
        return movies

    async def get_weekly_trending_digest(self, limit: int = 3, chat_id: str = "system") -> List[Dict]:
        """Special digest for weekly broadcasts."""
        from config.redis_cache import get_json, set_json
        from clients.omdb_client import fetch_movies_by_titles_async
        
        cache_key = "weekly_trending_digest"
        cached = get_json(cache_key)
        if cached:
            return cached[:limit]

        prompt = f"Identify the 3 most critically acclaimed and popular movies released this week. JSON array of titles."
        titles = await self._get_titles_from_perplexity(prompt, limit, chat_id)
        movies = await fetch_movies_by_titles_async(titles)
        
        if movies:
            set_json(cache_key, movies, ttl=86400 * 3) # Cache for 3 days
        return movies

    async def get_surprise_movies(self, limit: int = 8, chat_id: str = "system") -> List[Dict]:
        from clients.omdb_client import fetch_movies_by_titles_async
        # Added strict cinematic constraints to avoid non-movie results (like cities)
        prompt = (
            f"Identify a list of {limit} 'hidden gem' movies. These should be real, critically acclaimed movies "
            f"that are relatively niche or underrated. Return ONLY a JSON array of movie titles."
        )
        titles = await self._get_titles_from_perplexity(prompt, limit, chat_id)
        return await fetch_movies_by_titles_async(titles, chat_id=chat_id)

    async def get_star_movies(self, name: str, limit: int = 5, chat_id: str = "system") -> List[Dict]:
        """Discover movies based on an actor or director with conversational reasoning."""
        from clients.omdb_client import fetch_movies_by_titles_async
        prompt = (
            f"You are CineMate. The user is a big fan of '{name}'. "
            f"Suggest {limit} of their most iconic or fascinating movies. "
            f"For each, give me the title and a short, enthusiastic reason why a fan should watch it. "
            f"Return ONLY a JSON array of objects: [{{ \"title\": \"...\", \"reason\": \"...\" }}]"
        )
        
        from clients.perplexity_client import ask_perplexity
        raw = await ask_perplexity(prompt, chat_id=chat_id)
        if not raw: return []
        
        recs = []
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                recs = json.loads(match.group(0))
        except Exception: pass
        if not recs: return []
        
        titles = [r.get("title") for r in recs if r.get("title")]
        movies = await fetch_movies_by_titles_async(titles, chat_id=chat_id)
        
        for m in movies:
            for r in recs:
                if m["title"].lower() in r["title"].lower() or r["title"].lower() in m["title"].lower():
                    m["reason"] = r.get("reason")
                    break
        return movies

    async def get_similar_movies(self, seed_title: str, limit: int = 8, chat_id: str = "system") -> List[Dict]:
        from clients.omdb_client import fetch_movies_by_titles_async
        # Heuristic: If seed_title is long or has specific keywords, it's a search query 
        is_query = len(seed_title.split()) > 3 or any(k in seed_title.lower() for k in ["movie", "about", "like", "with", "film"])
        
        if is_query:
            prompt = f"Identify {limit} movies matching this description: '{seed_title}'. Return ONLY a JSON array of titles."
        else:
            prompt = f"Recommend {limit} movies similar to '{seed_title}'. Return ONLY a JSON array of titles."
            
        titles = await self._get_titles_from_perplexity(prompt, limit, chat_id)
        return await fetch_movies_by_titles_async(titles, chat_id=chat_id)

    async def lookup_movie_and_similar(self, title: str, limit: int = 5, chat_id: str = "system") -> List[Dict]:
        """Parallelize main movie lookup and similar title generation for speed."""
        from clients.omdb_client import omdb_get_by_title_async, fetch_movies_by_titles_async
        
        async def get_main():
            return await omdb_get_by_title_async(title)
        
        async def get_similar_titles():
            prompt = f"4 movies similar to '{title}'. JSON array of titles."
            return await self._get_titles_from_perplexity(prompt, 4, chat_id)

        main_res, sim_titles = await asyncio.gather(get_main(), get_similar_titles())
        if not main_res: return []
        similar_movies = await fetch_movies_by_titles_async(sim_titles)
        return [main_res] + similar_movies

    async def get_question_engine_recs(self, session: dict, user: dict, limit: int = 5, chat_id: str = "system") -> list:
        """Generate personalized recommendations with CineMate reasoning and permanent profile context."""
        from clients.omdb_client import fetch_movies_by_titles_async
        
        # 1. Current Session Context
        current = []
        for k in ["mood", "genre", "language", "era", "context", "time", "avoid", "favorites", "rating"]:
            v = session.get(f"answers_{k}", "")
            if v and "[Skipped]" not in str(v) and str(v).lower() != "any": 
                current.append(f"{k}: {v}")
        
        # 2. Permanent Profile Context (JSON List aware)
        permanent = []
        prefs = user.get("preferred_genres", [])
        if isinstance(prefs, list) and prefs:
            permanent.append(f"favorite genres: {', '.join(prefs)}")
        
        dislikes = user.get("disliked_genres", [])
        if isinstance(dislikes, list) and dislikes:
            permanent.append(f"strictly avoid these genres: {', '.join(dislikes)}")
            
        taste = user.get("user_taste_vector", {})
        if isinstance(taste, dict):
            if taste.get("top_actors"): 
                permanent.append(f"favorite actors: {', '.join(taste['top_actors'])}")
            if taste.get("top_directors"): 
                permanent.append(f"favorite directors: {', '.join(taste['top_directors'])}")
            
        if user.get("preferred_era"): 
            permanent.append(f"favorite era: {user['preferred_era']}")
        
        rating_min = user.get("avg_rating_preference")
        if rating_min:
            permanent.append(f"ONLY suggest movies with an IMDb rating of {rating_min} or higher")
            
        context = ", ".join(current) if current else "highly rated popular movies"
        history_context = f" (Keep in mind the user generally loves: {'; '.join(permanent)})" if permanent else ""
        
        prompt = (
            f"You are CineMate, a passionate movie expert. The user is in this mood: '{context}'{history_context}. "
            f"Identify {limit} unique, highly-rated movies that fit this specific moment while respecting their long-term tastes. "
            f"For each, give me the title and a one-sentence warm, conversational reason why it's a perfect match. "
            f"Return ONLY a JSON array of objects: [{{ \"title\": \"...\", \"reason\": \"...\" }}]"
        )
        
        from clients.perplexity_client import ask_perplexity
        raw = await ask_perplexity(prompt, chat_id=chat_id)
        if not raw: return []
        
        recs = []
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                recs = json.loads(match.group(0))
        except Exception: pass
        
        if not recs: return []
        
        titles = [r.get("title") for r in recs if r.get("title")]
        movies = await fetch_movies_by_titles_async(titles, chat_id=chat_id)
        
        # Inject reasoning into movie objects
        for m in movies:
            for r in recs:
                if m["title"].lower() in r["title"].lower() or r["title"].lower() in m["title"].lower():
                    m["reason"] = r.get("reason")
                    break
                    
        return movies

    async def get_backup_essentials(self, limit: int = 5) -> List[Dict]:
        """Static fallback mode for when external providers are offline."""
        from config.redis_cache import get_json
        # Check for pre-seeded essentials
        cached = get_json("cine_essentials")
        if cached:
            random.shuffle(cached)
            return cached[:limit]
            
        # Hardcoded ultimate fallback if even Redis essentials are missing
        return [
            {"title": "The Shawshank Redemption", "year": "1994", "rating": "9.3", "reason": "An absolute cinematic essential for any movie lover."},
            {"title": "The Godfather", "year": "1972", "rating": "9.2", "reason": "The pinnacle of crime drama and storytelling."},
            {"title": "Pulp Fiction", "year": "1994", "rating": "8.9", "reason": "A masterclass in non-linear narrative and dialogue."},
            {"title": "Inception", "year": "2010", "rating": "8.8", "reason": "A mind-bending journey that stays with you long after."},
            {"title": "Parasite", "year": "2019", "rating": "8.5", "reason": "A groundbreaking modern masterpiece of social themes."}
        ]
