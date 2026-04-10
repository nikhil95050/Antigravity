import os
import httpx
import asyncio
import hashlib
import json
from typing import List, Dict
from config.app_config import is_feature_enabled
from config.redis_cache import get_json, set_json
from services.logging_service import get_logger

from services.container import container
logger = get_logger("omdb_helper")

OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "").strip()
OMDB_BASE = "http://www.omdbapi.com/"

from utils.circuit_breaker import CircuitBreaker

_omdb_cb = CircuitBreaker("OMDb", failure_threshold=3, recovery_timeout=300)

# --- OMDb Async ---

async def omdb_get_by_title_async(title: str, chat_id: str = "system") -> dict:
    if not title: return {}
    
    # Tiered search strategy for robustness
    queries = [
        title,                                      # 1. Exact title
        title.split("(")[0].strip() if "(" in title else None,  # 2. Strip year suffix
    ]
    queries = [q for q in queries if q]
    
    # 0. Level 0: Global Discovery Cache
    for query in queries:
        cache_key = "omdb_t_" + hashlib.sha256(query.lower().encode()).hexdigest()
        cached = get_json(cache_key)
        if cached: return cached

        # 1. Level 1: Supabase Mirror (Permanent Store)
        try:
            from services.container import container
            # We use movie_id hash of query if we don't know it yet
            temp_id = hashlib.sha256(query.lower().encode()).hexdigest()
            mirror_repo = getattr(container, "metadata_repo", None)
            if mirror_repo:
                mirrored = mirror_repo.get_metadata(temp_id)
                if mirrored:
                    logger.info(f"Metadata MIRROR HIT for {query}")
                    return mirrored
        except Exception as e:
            logger.debug(f"Mirror check failed: {e}")

        # 2. Level 2: External API (Last Resort)
        if _omdb_cb.is_healthy():
            try:
                resp = await container.shared_client.get(OMDB_BASE, params={
                    "t": query, "type": "movie", "plot": "short", "apikey": OMDB_API_KEY
                })
                data = resp.json()
                if data.get("Response") == "True":
                    from repositories.api_usage_repository import ApiUsageRepository
                    ApiUsageRepository().log_usage(provider="OMDb", action="get_by_title", chat_id=chat_id)
                    
                    res = _normalize_omdb(data)
                    # Sync to Mirror & Cache
                    set_json(cache_key, res, ttl=86400 * 30)
                    if mirror_repo:
                        mirror_repo.upsert_metadata(res["movie_id"], res) # Real ID
                        mirror_repo.upsert_metadata(temp_id, res) # Alias for query
                    return res
            except Exception as e:
                logger.error(f"OMDb API error for {query}: {e}")
                # Potentially trigger circuit breaker logic if we wrapped it
            
    return {}

async def omdb_get_by_imdb_id_async(imdb_id: str, chat_id: str = "system") -> dict:
    if not imdb_id: return {}
    cache_key = "omdb_i_" + imdb_id
    cached = get_json(cache_key)
    if cached: return cached

    try:
        resp = await container.shared_client.get(OMDB_BASE, params={
            "i": imdb_id, "type": "movie", "plot": "short", "apikey": OMDB_API_KEY
        })
        data = resp.json()
        if data.get("Response") == "True":
            from repositories.api_usage_repository import ApiUsageRepository
            ApiUsageRepository().log_usage(provider="OMDb", action="get_by_id", chat_id=chat_id)
            
            res = _normalize_omdb(data)
            set_json(cache_key, res, ttl=86400 * 30)
            return res
    except Exception as e:
        logger.error(f"OMDb ID error for {imdb_id}: {e}")
    return {}

def _normalize_omdb(data: dict) -> dict:
    title = data.get("Title", "")
    imdb_id = data.get("imdbID", "")
    year = data.get("Year", "")
    rating = data.get("imdbRating", "")
    genres = data.get("Genre", "")
    poster = data.get("Poster", "")
    if poster == "N/A": poster = ""
    plot = data.get("Plot", "")
    if plot == "N/A": plot = ""
    
    return {
        "movie_id": imdb_id or title.lower().replace(" ", "_"),
        "title": title,
        "year": year.split("–")[0].strip() if "–" in year else year,
        "rating": rating if rating != "N/A" else "",
        "genres": genres,
        "language": data.get("Language", "English").split(",")[0].strip(),
        "description": plot,
        "director": data.get("Director", ""),
        "actors": data.get("Actors", ""),
        "poster": poster,
        "trailer": "",
    }

# --- Helpers ---

def _enrich_missing_fields(movie: dict) -> dict:
    return movie

async def fetch_movies_by_titles_async(titles: List[str], chat_id: str = "system") -> List[Dict]:
    if not titles: return []
    unique_titles = list(dict.fromkeys(titles))
    tasks = [omdb_get_by_title_async(t, chat_id=chat_id) for t in unique_titles]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r and r.get("title")]

async def get_trailer_url_async(title: str, year: str = "") -> str:
    query = f"{title} {year} official trailer".strip().replace(" ", "+")
    return f"https://www.youtube.com/results?search_query={query}"
