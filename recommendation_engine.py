import json
from airtable_client import get_trailer_cache, set_trailer_cache
from apify_client_helper import get_trailer_url
from movie_data import (
    search_movies_by_query,
    get_trending_movies,
    get_surprise_movies,
    lookup_movie_and_similar,
    get_similar_movies,
    get_question_engine_recs,
)

QUESTIONS = [
    ("mood",     "What's your mood right now? (e.g. happy, sad, excited, relaxed, thrilled)"),
    ("genre",    "What genre are you in the mood for? (e.g. action, comedy, drama, sci-fi, horror, romance)"),
    ("language", "Any language preference? (e.g. English, Spanish, French, Hindi, any)"),
    ("era",      "Do you prefer a specific era? (e.g. classic 80s/90s, 2000s, recent 2020s, any)"),
    ("context",  "Who are you watching with? (e.g. alone, with family, with friends, date night)"),
    ("avoid",    "Anything you want to avoid? (e.g. violence, gore, nudity, none)"),
]

QUESTION_KEYS = [q[0] for q in QUESTIONS]


def get_next_question(question_index: int):
    if question_index < len(QUESTIONS):
        return QUESTIONS[question_index]
    return None


def _dedup_and_exclude(movies: list, session: dict) -> list:
    """Remove duplicates and movies from last_recs_json."""
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


def _enrich_trailers(movies: list) -> list:
    """Add trailer URL to each movie via cache or YouTube search link."""
    enriched = []
    for movie in movies:
        movie_id = str(movie.get("movie_id", ""))
        trailer = movie.get("trailer", "")
        if not trailer:
            if movie_id:
                cached = get_trailer_cache(movie_id)
                if cached:
                    trailer = cached
            if not trailer:
                title = movie.get("title", "")
                year = movie.get("year", "")
                trailer = get_trailer_url(title, year)
                if movie_id and trailer:
                    set_trailer_cache(movie_id, trailer)
        movie["trailer"] = trailer
        enriched.append(movie)
    return enriched


def run_recommendation(session: dict, user: dict, mode: str = "question_engine",
                        seed_title: str = None, sim_depth: int = 0) -> list:
    """Core recommendation dispatcher."""
    if mode == "similarity" and sim_depth >= 2:
        print("[Engine] Sim depth limit reached, falling back to question_engine")
        mode = "question_engine"

    print(f"[Engine] Mode={mode} seed={seed_title}")

    if mode == "trending":
        movies = get_trending_movies(limit=8)
    elif mode == "surprise":
        movies = get_surprise_movies(limit=8)
    elif mode == "similarity" and seed_title:
        movies = get_similar_movies(seed_title, limit=8)
    else:
        movies = get_question_engine_recs(session, user, limit=8)

    movies = _dedup_and_exclude(movies, session)
    movies = _enrich_trailers(movies)
    return movies[:5]


def lookup_movie(title: str) -> list:
    """Lookup a specific movie + similar by title."""
    movies = lookup_movie_and_similar(title, limit=5)
    movies = _enrich_trailers(movies)
    return movies
