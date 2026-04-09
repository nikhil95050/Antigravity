import os
import requests
import json

APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
BASE_URL = "https://api.apify.com/v2"

def run_actor(actor_id: str, input_data: dict, timeout: int = 60) -> list:
    """Run an Apify actor and return dataset items."""
    try:
        headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}"}
        run_url = f"{BASE_URL}/acts/{actor_id}/run-sync-get-dataset-items"
        resp = requests.post(
            run_url,
            json=input_data,
            headers=headers,
            timeout=timeout,
            params={"timeout": timeout, "memory": 256}
        )
        if resp.status_code == 200:
            return resp.json() if isinstance(resp.json(), list) else []
        else:
            print(f"[Apify] Actor {actor_id} error: {resp.status_code} {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"[Apify] run_actor error: {e}")
        return []

def search_movies(query: str, limit: int = 10) -> list:
    """Search movies using IMDB scraper actor."""
    items = run_actor(
        "apify/imdb-scraper",
        {
            "searchQuery": query,
            "maxItems": limit,
            "type": "MOVIE",
        },
        timeout=60
    )
    return parse_movie_items(items)

def get_trending_movies(limit: int = 10) -> list:
    """Get trending/popular movies."""
    items = run_actor(
        "apify/imdb-scraper",
        {
            "searchQuery": "top rated movies 2024",
            "maxItems": limit,
            "type": "MOVIE",
        },
        timeout=60
    )
    return parse_movie_items(items)

def search_trailer(title: str, year: str = "") -> str:
    """Search for a movie trailer URL via IMDB or YouTube search."""
    try:
        query = f"{title} {year} official trailer".strip()
        items = run_actor(
            "apify/imdb-scraper",
            {"searchQuery": query, "maxItems": 3, "type": "MOVIE"},
            timeout=30
        )
        if items:
            for item in items:
                video = item.get("trailer") or item.get("trailerUrl") or item.get("trailer_url")
                if video:
                    return video
        return ""
    except Exception as e:
        print(f"[Apify] search_trailer error: {e}")
        return ""

def parse_movie_items(items: list) -> list:
    """Normalize Apify IMDB scraper results into standard format."""
    movies = []
    for item in items:
        movie_id = (
            item.get("id") or item.get("imdbId") or item.get("tconst") or
            item.get("url", "").split("/title/")[-1].split("/")[0] or ""
        )
        title = item.get("title") or item.get("name") or ""
        year = str(item.get("year") or item.get("releaseYear") or "")
        rating = item.get("rating") or item.get("imdbRating") or item.get("ratingValue") or ""
        genres = item.get("genres") or item.get("genre") or []
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",")]
        language = item.get("language") or item.get("languages") or "English"
        if isinstance(language, list):
            language = language[0] if language else "English"
        poster = item.get("image") or item.get("posterUrl") or item.get("poster") or ""
        description = item.get("description") or item.get("plot") or item.get("summary") or ""
        trailer = item.get("trailer") or item.get("trailerUrl") or item.get("trailer_url") or ""
        if movie_id and title:
            movies.append({
                "movie_id": movie_id,
                "title": title,
                "year": year,
                "rating": str(rating),
                "genres": ", ".join(genres) if isinstance(genres, list) else str(genres),
                "language": language,
                "poster": poster,
                "description": description,
                "trailer": trailer,
            })
    return movies
