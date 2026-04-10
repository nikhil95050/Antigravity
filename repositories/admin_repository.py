from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository
from utils.time_utils import utc_now_iso
from config.supabase_client import select_rows, insert_rows, update_rows, delete_rows, is_configured

class AdminRepository(BaseRepository):
    """Repository for managing the Admin Database and system control features."""

    def __init__(self):
        super().__init__("admins")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")),
            "username": data.get("username", ""),
            "permission_level": data.get("permission_level", "admin"),
            "added_at": data.get("added_at") or utc_now_iso()
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    # --- Multi-Admin Management ---
    def is_admin(self, chat_id: str) -> bool:
        admin = self.get_by_id(str(chat_id))
        if admin: return True
        return False

    def add_admin(self, chat_id: str, username: str, level: str = "admin"):
        payload = {"chat_id": str(chat_id), "username": username, "permission_level": level}
        self.upsert(chat_id, payload)

    # --- Bot Stats ---
    def increment_stat(self, metric_name: str, amount: int = 1):
        from config.redis_cache import increment
        increment(f"stat:{metric_name}", amount)
        # Note: Periodically syncing these to Supabase is recommended in Phase 3

    def get_stats(self) -> Dict[str, int]:
        stats = {}
        if is_configured():
            rows, error = select_rows("bot_stats", {})
            if rows:
                for r in rows:
                    stats[r["metric_name"]] = r["metric_value"]
        return stats

    # --- Provider Health ---
    def update_provider_health(self, provider_name: str, is_enabled: bool, failure_count: int, last_failure_at: Optional[str]):
        payload = {
            "provider_name": provider_name,
            "is_enabled": is_enabled,
            "failure_count": failure_count,
            "last_failure_at": last_failure_at,
            "updated_at": utc_now_iso()
        }
        if is_configured():
            insert_rows("provider_health", [payload], upsert=True, on_conflict="provider_name")

    def get_provider_health(self) -> List[Dict[str, Any]]:
        if is_configured():
            rows, error = select_rows("provider_health", {})
            return rows or []
        return []

    # --- Admin Audit ---
    def log_admin_action(self, admin_chat_id: str, command: str, details: str = ""):
        from datetime import datetime
        payload = {"admin_chat_id": str(admin_chat_id), "command": command, "details": details, "timestamp": utc_now_iso()}
        if is_configured():
            insert_rows("admin_audit", [payload])

    def cleanup_old_logs(self, days: int = 7):
        from datetime import datetime, timedelta, timezone
        if not is_configured(): return
        limit_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
        delete_rows("error_logs", {"timestamp": f"lt.{limit_date}"})
        delete_rows("admin_audit", {"timestamp": f"lt.{limit_date}"})
