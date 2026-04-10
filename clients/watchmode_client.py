import os
import httpx
from typing import List, Dict, Optional
from config.redis_cache import get_json, set_json
from services.logging_service import get_logger

logger = get_logger("watchmode_client")

from utils.circuit_breaker import CircuitBreaker

_wm_cb = CircuitBreaker("Watchmode", failure_threshold=3, recovery_timeout=300)

class WatchmodeClient:
    """Client for Watchmode API to fetch streaming availability, localized to India."""

    BASE_URL = "https://api.watchmode.com/v1"

    def __init__(self, api_key: str = None, shared_client: httpx.AsyncClient = None):
        self.api_key = api_key or os.environ.get("WATCHMODE_API_KEY", "")
        self.client = shared_client
        if not self.client:
            from services.container import container
            self.client = container.shared_client

    async def get_streaming_sources(self, imdb_id: str, title: str = "", chat_id: str = "system") -> List[str]:
        """Fetch streaming source names for a given movie, filtered for India."""
        if not self.api_key:
            return []
        
        if not await self._is_budget_ok():
            logger.warning("Watchmode daily budget exceeded. Skipping lookup.")
            return []

        if not _wm_cb.is_healthy():
            return []

        watchmode_id = await self._get_watchmode_id(imdb_id, title)
        if not watchmode_id:
            return []
            
        cache_key = f"wm_src_{watchmode_id}"
        cached = get_json(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.BASE_URL}/title/{watchmode_id}/sources/"
            resp = await self.client.get(url, params={"apiKey": self.api_key, "regions": "IN"})
            
            if resp.status_code == 200:
                from services.container import container
                container.usage_repo.log_usage(provider="Watchmode", action="get_sources", chat_id=chat_id)
                
                sources = resp.json()
                names = set()
                priority_types = ("sub", "free", "ads")
                for s in sources:
                    if s.get("type") in priority_types:
                        names.add(s.get("name"))
                
                res = sorted(list(names))
                set_json(cache_key, res, ttl=86400 * 7)
                return res
            else:
                logger.error(f"Watchmode API error {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching sources for {watchmode_id}: {e}")
        
        return []

    async def _is_budget_ok(self) -> bool:
        """Token bucket check to stay under 1000/day limit."""
        from config.redis_cache import get_redis
        client = get_redis()
        if not client: return True
        try:
            count = client.incr("wm_calls_today")
            if count == 1:
                client.expire("wm_calls_today", 86400)
            return count < 950
        except Exception as e:
            logger.debug(f"Budget check error: {e}")
            return True

    async def _get_watchmode_id(self, imdb_id: str, title: str) -> Optional[str]:
        """Resolve a Watchmode ID from IMDb ID or title, optimized for India region."""
        cache_key = "wm_id_" + (imdb_id or title).replace(" ", "_")
        cached = get_json(cache_key)
        if cached:
            return cached

        try:
            params = {"apiKey": self.api_key}
            if imdb_id and imdb_id.startswith("tt"):
                params["search_field"] = "imdb_id"
                params["search_value"] = imdb_id
            elif title:
                params["search_field"] = "name"
                params["search_value"] = title
            else:
                return None

            resp = await self.client.get(f"{self.BASE_URL}/search/", params=params)
            if resp.status_code == 200:
                results = resp.json().get("title_results", [])
                if results:
                    res = str(results[0].get("id"))
                    set_json(cache_key, res, ttl=86400 * 30)
                    return res
        except Exception as e:
            logger.error(f"Search error for {imdb_id}/{title}: {e}")
        return None
