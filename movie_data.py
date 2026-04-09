"""
Movie data layer.
- Perplexity: generates curated lists of movie TITLES only (recommendation engine)
- Apify (OMDb + IMDB scraper): fetches real structured data for each title
"""
import json
import re
from perplexity_client import ask_perplexity
from apify_client_helper import fetch_movies_by_titles, fetch_movie_details

SYSTEM_TITLES = (
    "You are a movie recommendation assistant. "
    "When asked for movie recommendations, respond with ONLY a JSON array of movie title strings. "
    "No prose, no markdown, no explanation. Just a raw JSON array like: "
    '[\"Movie Title 1\", \"Movie Title 2\", \"Movie Title 3\"]'
)

def _extract_titles(text: str) -> list:
    """Extract a list of title strings from Perplexity response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(t).strip() for t in data if t and str(t).strip()]
    except Exception:
        # Try to extract array
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list):
                    return [str(t).strip() for t in data if t and str(t).strip()]
            except Exception:
                pass
        # Fallback: numbered list
        titles = re.findall(r'\d+\.\s+([^\n]+)', text)
        if titles:
            return [t.strip().strip('"').strip("'") for t in titles]
    return []

def _get_titles_from_perplexity(prompt: str, limit: int) -> list:
    raw = ask_perplexity(prompt, system=SYSTEM_TITLES, model="sonar")
    titles = _extract_titles(raw)
    return titles[:limit]

def search_movies_by_query(query: str, limit: int = 8) -> list:
    """Use Perplexity to get title recommendations, then OMDb for real data."""
    prompt = (
        f"List exactly {limit} real movie titles that match: '{query}'. "
        f"Return only a JSON array of title strings."
    )
    titles = _get_titles_from_perplexity(prompt, limit)
    if not titles:
        return []
    return fetch_movies_by_titles(titles)

def get_trending_movies(limit: int = 8) -> list:
    """Get trending/popular movies via Perplexity titles + OMDb data."""
    prompt = (
        f"List {limit} currently trending and highly rated movies from 2023-2025. "
        f"Return only a JSON array of title strings."
    )
    titles = _get_titles_from_perplexity(prompt, limit)
    if not titles:
        titles = ["Oppenheimer", "Dune Part Two", "Poor Things", "The Zone of Interest",
                  "Killers of the Flower Moon", "Past Lives", "Anatomy of a Fall", "May December"]
    return fetch_movies_by_titles(titles)

def get_surprise_movies(limit: int = 8) -> list:
    """Get diverse underrated movies via Perplexity + OMDb."""
    prompt = (
        f"List {limit} underrated, critically acclaimed, or hidden gem movies across different genres and eras. "
        f"Mix of international and Hollywood. Return only a JSON array of title strings."
    )
    titles = _get_titles_from_perplexity(prompt, limit)
    if not titles:
        titles = ["A Ghost Story", "Coherence", "The Invitation", "Timecrimes",
                  "Paprika", "A Separation", "Capernaum", "Wild Tales"]
    return fetch_movies_by_titles(titles)

def lookup_movie_and_similar(title: str, limit: int = 5) -> list:
    """Look up a specific movie via OMDb, then get similar via Perplexity."""
    # First get the actual movie
    movies = fetch_movie_details(title)
    if not movies:
        return []

    found_title = movies[0].get("title", title)

    # Get similar movies via Perplexity
    similar_count = limit - len(movies)
    if similar_count > 0:
        prompt = (
            f"List {similar_count} movies similar to '{found_title}' in genre, tone, or style. "
            f"Do NOT include '{found_title}'. Return only a JSON array of title strings."
        )
        similar_titles = _get_titles_from_perplexity(prompt, similar_count)
        similar = fetch_movies_by_titles(similar_titles)
        movies.extend(similar)

    return movies[:limit]

def get_similar_movies(seed_title: str, limit: int = 8) -> list:
    """Get movies similar to a seed title."""
    prompt = (
        f"List {limit} movies similar to '{seed_title}' — same genre, tone, and emotional feel. "
        f"Do NOT include '{seed_title}' itself. Return only a JSON array of title strings."
    )
    titles = _get_titles_from_perplexity(prompt, limit)
    return fetch_movies_by_titles(titles)

def get_question_engine_recs(session: dict, user: dict, limit: int = 5) -> list:
    """Generate personalized recommendations based on session answers."""
    mood = session.get("answers_mood", "")
    genre = session.get("answers_genre", "")
    language = session.get("answers_language", "")
    era = session.get("answers_era", "")
    context = session.get("answers_context", "")
    avoid = session.get("answers_avoid", "")
    pref_genre = (user or {}).get("preferred_genres", "")

    parts = []
    if genre:
        parts.append(f"{genre} genre")
    elif pref_genre:
        parts.append(pref_genre)
    if mood:
        parts.append(f"{mood} mood")
    if language and language.lower() not in ("any", ""):
        parts.append(f"in {language}")
    if era and era.lower() not in ("any", ""):
        parts.append(f"from {era}")
    if context and context.lower() not in ("alone", ""):
        parts.append(f"good for {context}")
    if avoid and avoid.lower() not in ("none", "nothing", ""):
        parts.append(f"without {avoid}")

    query = " ".join(parts) if parts else "highly rated popular movies"

    prompt = (
        f"Recommend {limit} real movies for someone who wants: '{query}'. "
        f"Return only a JSON array of title strings."
    )
    titles = _get_titles_from_perplexity(prompt, limit)
    if not titles:
        return []
    return fetch_movies_by_titles(titles)
