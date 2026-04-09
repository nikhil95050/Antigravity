import json
from airtable_client import (
    get_trailer_cache, set_trailer_cache, get_history, insert_history_rows
)
from apify_client_helper import search_movies, get_trending_movies, search_trailer
from perplexity_client import understand_user_answer, generate_explanation

QUESTIONS = [
    ("mood",     "What's your mood right now? (e.g. happy, sad, excited, relaxed, thrilled)"),
    ("genre",    "What genre are you in the mood for? (e.g. action, comedy, drama, sci-fi, horror, romance)"),
    ("language", "Any language preference? (e.g. English, Spanish, French, Hindi, any)"),
    ("era",      "Do you prefer a specific era? (e.g. classic 80s/90s, 2000s, recent 2020s, any)"),
    ("context",  "Who are you watching with? (e.g. alone, with family, with friends, date night)"),
    ("avoid",    "Anything you want to avoid? (e.g. violence, gore, nudity, none)"),
]

QUESTION_KEYS = [q[0] for q in QUESTIONS]

def get_next_question(question_index: int) -> tuple:
    """Return (key, text) for question at index, or None if done."""
    if question_index < len(QUESTIONS):
        return QUESTIONS[question_index]
    return None

def build_recommendation_query(session: dict, user: dict, seed_title: str = None, mode: str = "question_engine") -> str:
    """Build an Apify search query from session answers and user preferences."""
    parts = []
    if mode == "similarity" and seed_title:
        parts.append(f"movies similar to {seed_title}")
    elif mode == "trending":
        parts.append("top rated popular movies 2024 2025")
    elif mode == "surprise":
        parts.append("underrated hidden gem movies critically acclaimed")
    else:
        mood = session.get("answers_mood", "")
        genre = session.get("answers_genre", "")
        language = session.get("answers_language", "")
        era = session.get("answers_era", "")
        context = session.get("answers_context", "")
        avoid = session.get("answers_avoid", "")

        pref_genre = user.get("preferred_genres", "") if user else ""
        pref_lang = user.get("preferred_language", "") if user else ""

        if genre:
            parts.append(genre)
        elif pref_genre:
            parts.append(pref_genre)
        if mood:
            parts.append(f"{mood} mood")
        if language and language.lower() not in ("any", ""):
            parts.append(language)
        elif pref_lang and pref_lang.lower() not in ("any", ""):
            parts.append(pref_lang)
        if era and era.lower() not in ("any", ""):
            parts.append(era)
        if not parts:
            parts.append("best movies highly rated")

    return " ".join(parts)

def score_movie(movie: dict, session: dict, user: dict, exclude_ids: list) -> float:
    """Score a movie based on relevance to preferences."""
    movie_id = movie.get("movie_id", "")
    if movie_id in exclude_ids:
        return -1.0

    score = 0.0
    try:
        rating = float(movie.get("rating", 0) or 0)
        score += rating * 0.5
    except Exception:
        pass

    genres = (movie.get("genres") or "").lower()
    pref_genre = (session.get("answers_genre") or user.get("preferred_genres", "") if user else "").lower()
    disliked = (user.get("disliked_genres", "") if user else "").lower()

    if pref_genre and any(g.strip() in genres for g in pref_genre.split(",")):
        score += 3.0
    if disliked and any(g.strip() in genres for g in disliked.split(",")):
        score -= 5.0

    avoid = (session.get("answers_avoid") or "").lower()
    if avoid and avoid not in ("none", "nothing", ""):
        if avoid in genres:
            score -= 3.0

    if movie.get("year"):
        era = (session.get("answers_era") or "").lower()
        year_str = str(movie.get("year", ""))
        if era and era not in ("any", ""):
            if "80" in era and year_str.startswith(("198",)):
                score += 2.0
            elif "90" in era and year_str.startswith(("199",)):
                score += 2.0
            elif "2000" in era and year_str.startswith(("200",)):
                score += 2.0
            elif "recent" in era or "2020" in era:
                try:
                    if int(year_str) >= 2020:
                        score += 2.0
                except Exception:
                    pass

    return score

def enrich_with_trailers(movies: list) -> list:
    """Add trailer URLs to movies, using cache first."""
    enriched = []
    for movie in movies:
        movie_id = movie.get("movie_id", "")
        trailer = movie.get("trailer", "")

        if not trailer and movie_id:
            cached = get_trailer_cache(movie_id)
            if cached:
                trailer = cached
            else:
                trailer = search_trailer(movie.get("title", ""), movie.get("year", ""))
                if trailer:
                    set_trailer_cache(movie_id, trailer)

        movie["trailer"] = trailer
        enriched.append(movie)
    return enriched

def run_recommendation(session: dict, user: dict, mode: str = "question_engine",
                        seed_title: str = None, sim_depth: int = 0) -> list:
    """Core recommendation function — fetch, score, deduplicate, return top 5."""
    if mode == "similarity" and sim_depth >= 2:
        mode = "question_engine"

    query = build_recommendation_query(session, user, seed_title, mode)
    print(f"[Engine] Mode={mode} Query='{query}'")

    if mode == "trending":
        raw = get_trending_movies(limit=20)
    else:
        raw = search_movies(query, limit=20)

    last_recs_raw = session.get("last_recs_json") or "[]"
    try:
        last_recs = json.loads(last_recs_raw) if isinstance(last_recs_raw, str) else last_recs_raw
        exclude_ids = [m.get("movie_id", "") for m in last_recs]
    except Exception:
        exclude_ids = []

    scored = []
    for movie in raw:
        s = score_movie(movie, session, user, exclude_ids)
        if s >= 0:
            scored.append((s, movie))

    scored.sort(key=lambda x: x[0], reverse=True)
    top5 = [m for _, m in scored[:5]]

    if not top5 and raw:
        top5 = raw[:5]

    top5 = enrich_with_trailers(top5)
    return top5

def lookup_movie(title: str) -> list:
    """Lookup a specific movie by title."""
    results = search_movies(title, limit=5)
    return results[:3]
