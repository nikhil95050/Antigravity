import concurrent.futures
from typing import List, Dict
from apify_client_helper import fetch_movies_by_titles, fetch_movie_details, get_trailer_url, omdb_get_by_title, _enrich_missing_fields

class ApifyAdapter:
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers

    def fetch_details_parallel(self, titles: List[str]) -> List[Dict]:
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_title = {executor.submit(self._fetch_single_movie, title): title for title in titles}
            for future in concurrent.futures.as_completed(future_to_title):
                try:
                    movie = future.result()
                    if movie: results.append(movie)
                except Exception as e:
                    print(f"[ApifyAdapter] Error: {e}")
        return results

    def _fetch_single_movie(self, title: str) -> Dict:
        res = omdb_get_by_title(title)
        if res and res.get("title"):
            return _enrich_missing_fields(res)
        return {}

    def get_movies_by_titles(self, titles: List[str]) -> List[Dict]:
        return fetch_movies_by_titles(titles)

    def get_movie_details(self, title: str) -> List[Dict]:
        return fetch_movie_details(title)

    def get_trailer(self, title: str, year: str = "") -> str:
        return get_trailer_url(title, year)
