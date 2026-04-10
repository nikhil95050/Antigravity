import json
import random
from typing import List, Dict
from perplexity_client import ask_perplexity
from apify_client_helper import fetch_movies_by_titles, fetch_movie_details

def _get_titles_from_perplexity(prompt: str, limit: int = 5) -> List[str]:
    """Helper to get a list of movie titles from Perplexity."""
    raw = ask_perplexity(prompt)
    if not raw: return []
    try:
        # Try to find JSON array in the response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start != -1 and end != -1:
            titles = json.loads(raw[start:end])
            if isinstance(titles, list):
                return [str(t) for t in titles][:limit]
    except:
        pass
    # Fallback: line-by-line parsing if JSON fails
    lines = [l.strip().strip('"').strip("'") for l in raw.split("\n") if l.strip()]
    return [l for l in lines if len(l) > 1][:limit]

def get_trending_movies(limit: int = 8) -> List[Dict]:
    prompt = f"Return a list of {limit} currently trending and popular movies. Return ONLY a JSON array of title strings."
    titles = _get_titles_from_perplexity(prompt, limit)
    return fetch_movies_by_titles(titles)

def get_surprise_movies(limit: int = 8) -> List[Dict]:
    prompt = f"Return a list of {limit} diverse, highly-rated 'hidden gem' or international movies. Return ONLY a JSON array of title strings."
    titles = _get_titles_from_perplexity(prompt, limit)
    return fetch_movies_by_titles(titles)

def get_similar_movies(seed_title: str, limit: int = 8) -> List[Dict]:
    prompt = f"Recommend {limit} movies similar in vibe and genre to '{seed_title}'. Return ONLY a JSON array of title strings."
    titles = _get_titles_from_perplexity(prompt, limit)
    return fetch_movies_by_titles(titles)

def lookup_movie_and_similar(title: str, limit: int = 5) -> List[Dict]:
    """Look up a specific movie and get 4 similar ones."""
    main_movie = fetch_movie_details(title)
    if not main_movie:
        return []
    
    # Get similar titles
    prompt = f"Recommend 4 movies very similar to '{title}'. Return ONLY a JSON array of title strings."
    similar_titles = _get_titles_from_perplexity(prompt, 4)
    similar_movies = fetch_movies_by_titles(similar_titles)
    
    return [main_movie] + similar_movies

def get_question_engine_recs(session: dict, user: dict, limit: int = 5) -> list:
    """Generate personalized recommendations based on the 8-question session context."""
    mood = session.get("answers_mood", "")
    genre = session.get("answers_genre", "")
    language = session.get("answers_language", "")
    era = session.get("answers_era", "")
    context = session.get("answers_context", "")
    time_limit = session.get("answers_time", "")
    avoid = session.get("answers_avoid", "")
    favorites = session.get("answers_favorites", "")
    
    pref_genre = (user or {}).get("preferred_genres", "")

    parts = []
    if mood and "[Skipped]" not in str(mood):
        parts.append(f"mood: {mood}")
    
    if genre and "[Skipped]" not in str(genre):
        parts.append(f"genres: {genre}")
    elif pref_genre:
        parts.append(f"preferred genres: {pref_genre}")
        
    if language and "any" not in str(language).lower() and "[Skipped]" not in str(language):
        parts.append(f"language: {language}")
        
    if era and "any" not in str(era).lower() and "[Skipped]" not in str(era):
        parts.append(f"era: {era}")
        
    if context and "[Skipped]" not in str(context):
        parts.append(f"watching context: {context}")
        
    if time_limit and "[Skipped]" not in str(time_limit):
        parts.append(f"runtime preference: {time_limit}")
        
    if avoid and "[Skipped]" not in str(avoid):
        parts.append(f"avoid these themes/genres: {avoid}")
        
    if favorites and "[Skipped]" not in str(favorites):
        parts.append(f"user likes these movies/actors: {favorites}")

    query = ", ".join(parts) if parts else "highly rated popular movies"

    candidates_limit = limit * 3
    prompt = (
        f"Recommend {candidates_limit} real movies for a user with these preferences: '{query}'. "
        f"Return ONLY a JSON array of movie title strings. No prose."
    )
    
    titles = _get_titles_from_perplexity(prompt, candidates_limit)
    if not titles:
        # High-quality fallbacks
        titles = ["The Shawshank Redemption", "Inception", "Parasite", "The Prestige", "The Grand Budapest Hotel"]
        
    return fetch_movies_by_titles(titles[:limit])
