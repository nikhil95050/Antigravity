import json
from airtable_client import get_trailer_cache, set_trailer_cache
from movie_data import (
    search_movies_perplexity,
    get_trending_perplexity,
    get_surprise_perplexity,
    lookup_movie_perplexity,
    get_similar_movies_perplexity,
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
    """Remove duplicates and movies already seen in last_recs_json."""
    last_recs_raw = session.get("last_recs_json") or "[]"
    try:
        last_recs = json.loads(last_recs_raw) if isinstance(last_recs_raw, str) else last_recs_raw
        exclude_ids = {m.get("movie_id", "") for m in last_recs}
    except Exception:
        exclude_ids = set()

    seen = set()
    result = []
    for m in movies:
        mid = m.get("movie_id", "")
        if mid not in exclude_ids and mid not in seen and m.get("title"):
            seen.add(mid)
            result.append(m)
    return result


def _enrich_trailers(movies: list) -> list:
    """Add YouTube search URL as trailer fallback if not provided."""
    enriched = []
    for movie in movies:
        movie_id = movie.get("movie_id", "")
        trailer = movie.get("trailer", "")
        if not trailer and movie_id:
            cached = get_trailer_cache(movie_id)
            if cached:
                trailer = cached
            else:
                title = movie.get("title", "")
                year = movie.get("year", "")
                query = f"{title} {year} official trailer".strip().replace(" ", "+")
                trailer = f"https://www.youtube.com/results?search_query={query}"
                set_trailer_cache(movie_id, trailer)
        movie["trailer"] = trailer
        enriched.append(movie)
    return enriched


def run_recommendation(session: dict, user: dict, mode: str = "question_engine",
                        seed_title: str = None, sim_depth: int = 0) -> list:
    """Core recommendation entry point — calls appropriate data source."""
    if mode == "similarity" and sim_depth >= 2:
        mode = "question_engine"

    print(f"[Engine] Mode={mode} seed={seed_title}")

    if mode == "trending":
        movies = get_trending_perplexity(limit=8)
    elif mode == "surprise":
        movies = get_surprise_perplexity(limit=8)
    elif mode == "similarity" and seed_title:
        movies = get_similar_movies_perplexity(seed_title, limit=8)
    else:
        movies = get_question_engine_recs(session, user, limit=8)

    movies = _dedup_and_exclude(movies, session)
    movies = _enrich_trailers(movies)
    return movies[:5]


def lookup_movie(title: str) -> list:
    """Lookup a specific movie by title and return it + similar movies."""
    movies = lookup_movie_perplexity(title, limit=5)
    movies = _enrich_trailers(movies)
    return movies
