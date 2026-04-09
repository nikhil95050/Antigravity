"""
Movie data layer — uses Perplexity AI to fetch real, structured movie data.
Falls back to Apify if configured. Perplexity has real-time web knowledge
and can return accurate movie details as JSON.
"""
import json
import re
from perplexity_client import ask_perplexity

SYSTEM_PROMPT = (
    "You are a movie database assistant. When asked for movies, always respond with ONLY valid JSON — "
    "an array of movie objects. No prose, no markdown, no explanation. Just raw JSON array. "
    "Each object must have: title, year, rating (IMDB 0-10), genres (comma-separated string), "
    "language, description (1-2 sentences), movie_id (imdb tt-code if known, else slugified title)."
)

def _extract_json(text: str) -> list:
    """Extract JSON array from Perplexity response, robust to markdown wrapping."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "movies" in data:
            return data["movies"]
    except Exception:
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return []

def _normalize_movie(item: dict, idx: int) -> dict:
    """Ensure all expected fields are present."""
    title = item.get("title") or item.get("name") or f"Movie {idx+1}"
    movie_id = item.get("movie_id") or item.get("imdb_id") or item.get("id") or re.sub(r'\W+', '_', title.lower())
    genres = item.get("genres") or item.get("genre") or ""
    if isinstance(genres, list):
        genres = ", ".join(genres)
    return {
        "movie_id": str(movie_id),
        "title": title,
        "year": str(item.get("year") or item.get("release_year") or ""),
        "rating": str(item.get("rating") or item.get("imdb_rating") or ""),
        "genres": genres,
        "language": item.get("language") or "English",
        "description": item.get("description") or item.get("plot") or item.get("overview") or "",
        "poster": item.get("poster") or item.get("poster_url") or "",
        "trailer": item.get("trailer") or item.get("trailer_url") or "",
    }

def search_movies_perplexity(query: str, limit: int = 8) -> list:
    prompt = (
        f"List {limit} real movies matching: '{query}'. "
        f"Return JSON array only. Each: title, year, rating (IMDB float), genres (comma string), "
        f"language, description (1 sentence), movie_id (IMDB tt-code or slug)."
    )
    raw = ask_perplexity(prompt, system=SYSTEM_PROMPT, model="sonar")
    items = _extract_json(raw)
    return [_normalize_movie(m, i) for i, m in enumerate(items[:limit]) if m.get("title")]

def get_trending_perplexity(limit: int = 8) -> list:
    prompt = (
        f"List {limit} trending/popular movies from 2023-2025 with high IMDB ratings. "
        f"Return JSON array only. Each: title, year, rating, genres, language, description, movie_id."
    )
    raw = ask_perplexity(prompt, system=SYSTEM_PROMPT, model="sonar")
    items = _extract_json(raw)
    return [_normalize_movie(m, i) for i, m in enumerate(items[:limit]) if m.get("title")]

def get_surprise_perplexity(limit: int = 8) -> list:
    prompt = (
        f"List {limit} underrated or hidden gem movies — critically acclaimed but not mainstream blockbusters. "
        f"Mix of genres and eras. Return JSON array only. Each: title, year, rating, genres, language, description, movie_id."
    )
    raw = ask_perplexity(prompt, system=SYSTEM_PROMPT, model="sonar")
    items = _extract_json(raw)
    return [_normalize_movie(m, i) for i, m in enumerate(items[:limit]) if m.get("title")]

def lookup_movie_perplexity(title: str, limit: int = 5) -> list:
    prompt = (
        f"Find the movie '{title}' and {limit-1} similar movies. "
        f"Start with the exact match. Return JSON array only. "
        f"Each: title, year, rating, genres, language, description, movie_id (IMDB tt-code if known)."
    )
    raw = ask_perplexity(prompt, system=SYSTEM_PROMPT, model="sonar")
    items = _extract_json(raw)
    return [_normalize_movie(m, i) for i, m in enumerate(items[:limit]) if m.get("title")]

def get_similar_movies_perplexity(seed_title: str, limit: int = 8) -> list:
    prompt = (
        f"List {limit} movies similar to '{seed_title}' — same genre, tone, and style. "
        f"Do NOT include '{seed_title}' itself. Return JSON array only. "
        f"Each: title, year, rating, genres, language, description, movie_id."
    )
    raw = ask_perplexity(prompt, system=SYSTEM_PROMPT, model="sonar")
    items = _extract_json(raw)
    return [_normalize_movie(m, i) for i, m in enumerate(items[:limit]) if m.get("title")]

def build_preference_query(session: dict, user: dict) -> str:
    parts = []
    mood = session.get("answers_mood", "")
    genre = session.get("answers_genre", "")
    language = session.get("answers_language", "")
    era = session.get("answers_era", "")
    context = session.get("answers_context", "")
    avoid = session.get("answers_avoid", "")
    pref_genre = user.get("preferred_genres", "") if user else ""

    if genre:
        parts.append(f"{genre} movies")
    elif pref_genre:
        parts.append(f"{pref_genre} movies")
    if mood:
        parts.append(f"with {mood} feel")
    if language and language.lower() not in ("any", ""):
        parts.append(f"in {language}")
    if era and era.lower() not in ("any", ""):
        parts.append(f"from {era}")
    if context and context.lower() not in ("alone", ""):
        parts.append(f"good for {context}")
    if avoid and avoid.lower() not in ("none", "nothing", ""):
        parts.append(f"without {avoid}")
    return " ".join(parts) if parts else "highly rated popular movies"

def get_question_engine_recs(session: dict, user: dict, limit: int = 5) -> list:
    query = build_preference_query(session, user)
    prompt = (
        f"Recommend {limit} movies for someone who wants: '{query}'. "
        f"Return JSON array only. Each: title, year, rating, genres, language, description, movie_id."
    )
    raw = ask_perplexity(prompt, system=SYSTEM_PROMPT, model="sonar")
    items = _extract_json(raw)
    return [_normalize_movie(m, i) for i, m in enumerate(items[:limit]) if m.get("title")]
