import os
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from config.supabase_client import insert_rows, select_rows, update_rows, is_configured as is_supabase_configured
from config.redis_cache import get_json as cache_get_json, set_json as cache_set_json, delete_key as cache_delete_key

class BaseRepository(ABC):
    """
    Base repository class focused on Supabase.
    Includes atomic upserts and optional Redis caching for lookups.
    """
    
    def __init__(self, table_name: str):
        self.table_name = table_name

    def _bg(self, fn, *args, **kwargs):
        """Dispatches a background task using asyncio."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._wrap_async(fn, *args, **kwargs))
        except RuntimeError:
            # Fallback for non-async contexts (rare but possible during init)
            import threading
            threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()

    async def _wrap_async(self, fn, *args, **kwargs):
        """Ensures synchronous repository methods can run in the background."""
        if asyncio.iscoroutinefunction(fn):
            res = await fn(*args, **kwargs)
        else:
            res = await asyncio.to_thread(fn, *args, **kwargs)
        
        # If the result is a (data, error) tuple, log the error
        if isinstance(res, tuple) and len(res) == 2 and res[1]:
            from services.logging_service import get_logger
            get_logger("repo_bg").error(f"Background task {fn.__name__} failed: {res[1]}")

    @abstractmethod
    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def get_by_id(self, chat_id: str, id_field: str = "chat_id", use_cache: bool = True) -> Optional[Dict[str, Any]]:
        # 1. Try Cache
        cache_key = f"repo:{self.table_name}:{chat_id}"
        if use_cache:
            cached = cache_get_json(cache_key)
            if cached:
                return cached

        # 2. Try Supabase
        if is_supabase_configured():
            rows, error = select_rows(self.table_name, {id_field: str(chat_id)}, limit=1)
            if not error and rows:
                data = self._map_from_supabase(rows[0])
                if use_cache:
                    cache_set_json(cache_key, data, ttl=300) # Cache for 5 mins
                return data

        return None

    def upsert(self, chat_id: str, data: Dict[str, Any], id_field: str = "chat_id"):
        if is_supabase_configured():
            payload = self._map_to_supabase({**data, "chat_id": str(chat_id)})
            
            # Update cache immediately for consistency
            cache_key = f"repo:{self.table_name}:{chat_id}"
            existing = self.get_by_id(chat_id, id_field=id_field, use_cache=True) or {}
            existing.update(data)
            cache_set_json(cache_key, existing, ttl=300)
            
            # Fire and forget to Supabase
            self._bg(insert_rows, self.table_name, [payload], upsert=True, on_conflict=id_field)

    def bulk_upsert(self, chat_id: str, data_list: List[Dict[str, Any]], id_field: str = "chat_id"):
        if not data_list: return
        
        if is_supabase_configured():
            payloads = [self._map_to_supabase({**d, "chat_id": str(chat_id)}) for d in data_list]
            self._bg(insert_rows, self.table_name, payloads, upsert=True, on_conflict=id_field)
            
            # Invalidate specific cache
            cache_key = f"repo:{self.table_name}:{chat_id}"
            cache_delete_key(cache_key)
    def delete_rows(self, filters: Dict[str, Any]):
        """Targeted deletion from Supabase."""
        if is_supabase_configured():
            from config.supabase_client import delete_rows as supabase_delete
            return supabase_delete(self.table_name, filters)
        return None, "Not configured"
