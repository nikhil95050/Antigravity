from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from .base_repository import BaseRepository
from supabase_client import select_rows, insert_rows, update_rows, delete_rows, is_configured
from airtable_client import is_airtable_available, get_table

class AdminRepository(BaseRepository):
    """Repository for managing the Admin Database and system control features with full mirroring."""

    def __init__(self):
        super().__init__("admins", "Admins")

    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(data.get("chat_id", "")),
            "username": data.get("username", ""),
            "permission_level": data.get("permission_level", "admin"),
            "added_at": data.get("added_at") or datetime.utcnow().isoformat() + "Z"
        }

    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Chat ID": str(data.get("chat_id", "")),
            "Username": data.get("username", ""),
            "Permission Level": data.get("permission_level", "admin"),
            "Added At": data.get("added_at") or datetime.utcnow().isoformat() + "Z"
        }

    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return row

    def _map_from_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_id": str(record.get("Chat ID", "")),
            "username": record.get("Username", ""),
            "permission_level": record.get("Permission Level", ""),
            "added_at": record.get("Added At", "")
        }

    # --- Multi-Admin Management ---
    def is_admin(self, chat_id: str) -> bool:
        # Check Supabase first, then fallback to Airtable
        admin = self.get_by_id(str(chat_id))
        if admin: return True
        return str(chat_id) == "1878846631" # Hardcoded fallback

    def add_admin(self, chat_id: str, username: str, level: str = "admin"):
        payload = {"chat_id": str(chat_id), "username": username, "permission_level": level}
        self.upsert(chat_id, payload)

    # --- Bot Stats Mirroring ---
    def increment_stat(self, metric_name: str, amount: int = 1):
        if is_configured():
            rows, error = select_rows("bot_stats", {"metric_name": metric_name}, limit=1)
            current_value = rows[0].get("metric_value", 0) if rows else 0
            new_value = current_value + amount
            payload = {
                "metric_name": metric_name,
                "metric_value": new_value,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
            insert_rows("bot_stats", [payload], upsert=True, on_conflict="metric_name")
            
            # Mirror to Airtable Bot Stats
            if is_airtable_available():
                self._bg(self._mirror_stat, metric_name, new_value)

    def _mirror_stat(self, name, val):
        try:
            tbl = get_table("Bot Stats")
            recs = tbl.all(formula=f"{{Metric Name}}='{name}'")
            data = {"Metric Name": name, "Metric Value": val, "Updated At": datetime.utcnow().isoformat() + "Z"}
            if recs: tbl.update(recs[0]["id"], data)
            else: tbl.create(data)
        except: pass

    def get_stats(self) -> Dict[str, int]:
        stats = {}
        if is_configured():
            rows, error = select_rows("bot_stats", {})
            if rows:
                for r in rows:
                    stats[r["metric_name"]] = r["metric_value"]
        return stats

    # --- Provider Health Mirroring ---
    def update_provider_health(self, provider_name: str, is_enabled: bool, failure_count: int, last_failure_at: Optional[str]):
        payload = {
            "provider_name": provider_name,
            "is_enabled": is_enabled,
            "failure_count": failure_count,
            "last_failure_at": last_failure_at,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
        if is_configured():
            insert_rows("provider_health", [payload], upsert=True, on_conflict="provider_name")
        if is_airtable_available():
            self._bg(self._mirror_provider, provider_name, is_enabled, failure_count, last_failure_at)

    def _mirror_provider(self, name, enabled, count, last):
        try:
            tbl = get_table("Provider Health")
            recs = tbl.all(formula=f"{{Provider Name}}='{name}'")
            data = {"Provider Name": name, "Is Enabled": enabled, "Failure Count": count, "Last Failure At": last, "Updated At": datetime.utcnow().isoformat() + "Z"}
            if recs: tbl.update(recs[0]["id"], data)
            else: tbl.create(data)
        except: pass

    # --- Admin Audit Mirroring ---
    def log_admin_action(self, admin_chat_id: str, command: str, details: str = ""):
        payload = {"admin_chat_id": str(admin_chat_id), "command": command, "details": details, "timestamp": datetime.utcnow().isoformat() + "Z"}
        if is_configured():
            insert_rows("admin_audit", [payload])
        if is_airtable_available():
            try:
                get_table("Admin Audit").create({
                    "Admin Chat ID": payload["admin_chat_id"],
                    "Command": payload["command"],
                    "Details": payload["details"],
                    "Timestamp": payload["timestamp"]
                })
            except: pass

    def cleanup_old_logs(self, days: int = 7):
        if not is_configured(): return
        limit_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        delete_rows("error_logs", {"timestamp": f"lt.{limit_date}"})
        delete_rows("admin_audit", {"timestamp": f"lt.{limit_date}"})
        # Note: Airtable deletions usually handled via automation or manually for audit safety
