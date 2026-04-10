from typing import Any, Dict
from datetime import datetime
from .base_repository import BaseRepository

class ApiUsageRepository(BaseRepository):
    """Repository for tracking API credits and usage logs with full mirroring."""

    def __init__(self):
        super().__init__("api_usage", "API Usage")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "system")),
            "provider": str(data.get("provider", "unknown")),
            "action": str(data.get("action", "query")),
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat() + "Z",
            "prompt_tokens": data.get("prompt_tokens", 0),
            "completion_tokens": data.get("completion_tokens", 0),
            "total_tokens": data.get("total_tokens", 0)
        }

    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Chat ID": str(data.get("chat_id", "system")),
            "Provider": str(data.get("provider", "unknown")),
            "Action": str(data.get("action", "query")),
            "Timestamp": data.get("timestamp") or datetime.utcnow().isoformat() + "Z",
            "Prompt Tokens": data.get("prompt_tokens", 0),
            "Completion Tokens": data.get("completion_tokens", 0),
            "Total Tokens": data.get("total_tokens", 0)
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def _map_from_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(record.get("Chat ID", "")),
            "provider": str(record.get("Provider", "")),
            "action": str(record.get("Action", "")),
            "timestamp": record.get("Timestamp", ""),
            "prompt_tokens": record.get("Prompt Tokens", 0),
            "completion_tokens": record.get("Completion Tokens", 0),
            "total_tokens": record.get("Total Tokens", 0)
        }

    def log_usage(self, provider: str, action: str, chat_id: str = "system", prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        """Logs a single API call for usage tracking safely in the background."""
        payload = {
            "chat_id": chat_id,
            "provider": provider,
            "action": action,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }
        
        # 1. Supabase Background Write
        from supabase_client import insert_rows, is_configured as is_supabase_configured
        if is_supabase_configured():
            self._bg(self._safe_supabase_log, payload)
        
        # 2. Airtable Background Write
        from airtable_client import is_airtable_available, get_table
        if is_airtable_available():
            self._bg(self._safe_airtable_log, payload)

    def _safe_supabase_log(self, payload):
        try:
            from supabase_client import insert_rows
            insert_rows(self.table_name, [self._map_to_supabase(payload)])
        except Exception as e:
            print(f"[ApiUsage] Supabase log failed: {e}")

    def _safe_airtable_log(self, payload):
        try:
            from airtable_client import get_table
            get_table(self.airtable_name).create(self._map_to_airtable(payload))
        except Exception as e:
            print(f"[ApiUsage] Airtable log failed: {e}")
