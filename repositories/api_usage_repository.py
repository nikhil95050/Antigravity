from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository
from utils.time_utils import utc_now_iso
from services.logging_service import get_logger

logger = get_logger("api_usage_repo")

class ApiUsageRepository(BaseRepository):
    """Repository for tracking API credits and usage logs."""

    def __init__(self):
        super().__init__("api_usage")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "chat_id": str(data.get("chat_id", "system")),
            "provider": str(data.get("provider", "unknown")),
            "action": str(data.get("action", "query")),
            "timestamp": data.get("timestamp") or utc_now_iso(),
        }
        # Add tokens only if they are positive (prevents unnecessary column hits if they don't exist in older schemas)
        if data.get("prompt_tokens"): payload["prompt_tokens"] = data.get("prompt_tokens")
        if data.get("completion_tokens"): payload["completion_tokens"] = data.get("completion_tokens")
        if data.get("total_tokens"): payload["total_tokens"] = data.get("total_tokens")
        return payload

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def log_usage(self, provider: str, action: str, chat_id: str = "system", prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        """Logs a single API call for usage tracking safely in the background."""
        payload = {
            "chat_id": chat_id,
            "provider": provider,
            "action": action,
            "timestamp": utc_now_iso(),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }
        
        from config.supabase_client import is_configured as is_supabase_configured
        if is_supabase_configured():
            self._bg(self._safe_supabase_log, payload)

    def _safe_supabase_log(self, payload):
        try:
            from config.supabase_client import insert_row
            insert_row(self.table_name, self._map_to_supabase(payload))
        except Exception as e:
            logger.error(f"Supabase log failed for {payload.get('provider')}: {e}")
