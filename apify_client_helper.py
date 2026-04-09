"""
Apify integration for movie data.
Uses:
  - OMDb API (free key) for exact movie lookups and details
  - Apify getdataforme/imdb-movie-scraper for IMDB scraping
  - Perplexity only for generating recommendation title lists
"""
import os
import requests
import json

APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
OMDB_API_KEY = "trilogy"  # free public demo key
OMDB_BASE = "http://www.omdbapi.com/"
APIFY_BASE = "https://api.apify.com/v2"

# ─── OMDb ──────────────────────────────────────────────────────────────────────

def omdb_get_by_title(title: str) -> dict:
    """Get a single movie by exact title from OMDb."""
    try:
        resp = requests.get(OMDB_BASE, params={
            "t": title, "type": "movie", "plot": "short", "apikey": OMDB_API_KEY
        }, timeout=10)
        data = resp.json()
        if data.get("Response") == "True":
            return _normalize_omdb(data)
    except Exception as e:
        print(f"[OMDb] get_by_title error: {e}")
    return {}

def omdb_search(query: str, limit: int = 10) -> list:
    """Search OMDb for movies matching query. Returns list of normalized movies."""
    try:
        resp = requests.get(OMDB_BASE, params={
            "s": query, "type": "movie", "apikey": OMDB_API_KEY
        }, timeout=10)
        data = resp.json()
        results = data.get("Search", [])
        movies = []
        for item in results[:limit]:
            # Search results only have basic info — fetch full details
            detail = omdb_get_by_imdb_id(item.get("imdbID", ""))
            if detail:
                movies.append(detail)
            elif item.get("Title"):
                movies.append({
                    "movie_id": item.get("imdbID", ""),
                    "title": item.get("Title", ""),
                    "year": item.get("Year", ""),
                    "rating": "",
                    "genres": "",
                    "language": "English",
                    "description": "",
                    "poster": item.get("Poster", ""),
                    "trailer": "",
                })
        return movies
    except Exception as e:
        print(f"[OMDb] search error: {e}")
    return []

def omdb_get_by_imdb_id(imdb_id: str) -> dict:
    """Get full movie details by IMDB ID."""
    if not imdb_id:
        return {}
    try:
        resp = requests.get(OMDB_BASE, params={
            "i": imdb_id, "type": "movie", "plot": "short", "apikey": OMDB_API_KEY
        }, timeout=10)
        data = resp.json()
        if data.get("Response") == "True":
            return _normalize_omdb(data)
    except Exception as e:
        print(f"[OMDb] get_by_id error: {e}")
    return {}

def _normalize_omdb(data: dict) -> dict:
    """Normalize an OMDb response into our standard movie format."""
    title = data.get("Title", "")
    imdb_id = data.get("imdbID", "")
    year = data.get("Year", "")
    rating = data.get("imdbRating", "N/A")
    genres = data.get("Genre", "")
    language = data.get("Language", "English")
    poster = data.get("Poster", "")
    if poster == "N/A":
        poster = ""
    plot = data.get("Plot", "")
    if plot == "N/A":
        plot = ""
    return {
        "movie_id": imdb_id,
        "title": title,
        "year": year.split("–")[0].strip() if "–" in year else year,
        "rating": rating if rating != "N/A" else "",
        "genres": genres,
        "language": language.split(",")[0].strip(),
        "description": plot,
        "poster": poster,
        "trailer": "",
    }

# ─── Apify IMDB scraper ────────────────────────────────────────────────────────

def apify_run_actor(actor_id: str, input_data: dict, timeout: int = 90) -> list:
    """Run an Apify actor synchronously and return dataset items."""
    try:
        headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}"}
        url = f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items"
        resp = requests.post(
            url, json=input_data, headers=headers,
            params={"timeout": timeout, "memory": 512},
            timeout=timeout + 15
        )
        if resp.status_code == 200:
            result = resp.json()
            return result if isinstance(result, list) else []
        elif resp.status_code == 201:
            # Actor returned items as body
            try:
                result = resp.json()
                return result if isinstance(result, list) else []
            except Exception:
                return []
        else:
            print(f"[Apify] Actor {actor_id} error {resp.status_code}: {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"[Apify] run_actor error: {e}")
        return []

def apify_get_imdb_movie(query: str) -> list:
    """Use getdataforme/imdb-movie-scraper to search for movies."""
    items = apify_run_actor("CrbGiK4g1EDmo0e7C", {
        "query": query,
        "maxItems": 5,
    }, timeout=90)
    movies = []
    for item in items:
        title = item.get("title") or item.get("name") or ""
        if not title:
            continue
        imdb_id = item.get("id") or item.get("imdbId") or item.get("tconst") or ""
        if imdb_id and not imdb_id.startswith("tt"):
            imdb_id = ""
        year = str(item.get("year") or item.get("releaseYear") or "")
        rating = str(item.get("rating") or item.get("imdbRating") or "")
        genres = item.get("genres") or item.get("genre") or []
        if isinstance(genres, list):
            genres = ", ".join(genres)
        language = item.get("language") or "English"
        if isinstance(language, list):
            language = language[0] if language else "English"
        poster = item.get("image") or item.get("posterUrl") or item.get("poster") or ""
        description = item.get("description") or item.get("plot") or ""
        movies.append({
            "movie_id": imdb_id or title.lower().replace(" ", "_"),
            "title": title,
            "year": year,
            "rating": rating,
            "genres": genres,
            "language": language,
            "description": description,
            "poster": poster,
            "trailer": "",
        })
    return movies

# ─── High-level movie fetch functions ─────────────────────────────────────────

def fetch_movies_by_titles(titles: list) -> list:
    """
    Given a list of movie titles (from Perplexity), fetch real data for each 
    from OMDb. Returns normalized movie list.
    """
    movies = []
    seen = set()
    for title in titles:
        if title in seen:
            continue
        seen.add(title)
        movie = omdb_get_by_title(title)
        if movie and movie.get("title"):
            movies.append(movie)
        else:
            # Fallback: try Apify IMDB scraper
            apify_results = apify_get_imdb_movie(title)
            if apify_results:
                movies.append(apify_results[0])
    return movies

def fetch_movie_details(title: str) -> list:
    """Get a specific movie + similar info from OMDb, then Apify fallback."""
    result = omdb_get_by_title(title)
    if result and result.get("title"):
        return [result]
    # Try search
    results = omdb_search(title, limit=3)
    if results:
        return results
    # Try Apify
    apify_results = apify_get_imdb_movie(title)
    return apify_results[:3]

def get_trailer_url(title: str, year: str = "") -> str:
    """Build a YouTube search URL for the trailer."""
    query = f"{title} {year} official trailer".strip().replace(" ", "+")
    return f"https://www.youtube.com/results?search_query={query}"
