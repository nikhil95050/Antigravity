import os
import requests
from typing import List, Dict, Optional
from redis_cache import get_json, set_json

class WatchmodeAdapter:
    """Adapter for Watchmode API to fetch streaming availability, localized to India."""

    BASE_URL = "https://api.watchmode.com/v1"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("WATCHMODE_API_KEY", "")

    def get_streaming_sources(self, imdb_id: str, title: str = "") -> List[str]:
        """Fetch streaming source names for a given movie, filtered for India."""
        if not self.api_key:
            return []

        watchmode_id = self._get_watchmode_id(imdb_id, title)
        if not watchmode_id:
            return []
            
        cache_key = f"wm_src_{watchmode_id}"
        cached = get_json(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.BASE_URL}/title/{watchmode_id}/sources/"
            # Use regions=IN for India-specific availability
            resp = requests.get(url, params={"apiKey": self.api_key, "regions": "IN"}, timeout=8)
            if resp.status_code == 200:
                sources = resp.json()
                # Include sub (subscription), free, and ads-supported sources
                names = set()
                priority_types = ("sub", "free", "ads")
                for s in sources:
                    if s.get("type") in priority_types:
                        names.add(s.get("name"))
                res = sorted(list(names))
                set_json(cache_key, res, ttl=86400 * 7)
                return res
        except Exception as e:
            print(f"[Watchmode] Error fetching sources for {watchmode_id}: {e}")
        
        return []

    def _get_watchmode_id(self, imdb_id: str, title: str) -> Optional[str]:
        """Resolve a Watchmode ID from IMDb ID or title, optimized for India region."""
        
        cache_key = "wm_id_" + (imdb_id or title).replace(" ", "_")
        cached = get_json(cache_key)
        if cached:
            return cached

        try:
            # We search globally first or with region filter if supported for higher accuracy
            params = {"apiKey": self.api_key}
            if imdb_id and imdb_id.startswith("tt"):
                params["search_field"] = "imdb_id"
                params["search_value"] = imdb_id
            elif title:
                params["search_field"] = "name"
                params["search_value"] = title
            else:
                return None

            resp = requests.get(f"{self.BASE_URL}/search/", params=params, timeout=8)
            if resp.status_code == 200:
                results = resp.json().get("title_results", [])
                if results:
                    # Sort results by relevance (if multiple, find the best match)
                    # For now, take the first result as it's usually the most relevant
                    res = str(results[0].get("id"))
                    set_json(cache_key, res, ttl=86400 * 30)
                    return res
        except Exception as e:
            print(f"[Watchmode] Search error for {imdb_id}/{title}: {e}")
        return None
