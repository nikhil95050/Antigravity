"""
Storage layer with hybrid persistence:
- Supabase when configured
- Airtable as a legacy fallback
- In-memory + optional Redis-style cache for fast local reads
"""
import json
import os
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from supabase_client import (
    is_configured as is_supabase_configured,
    is_available as is_supabase_available,
    select_rows as supabase_select_rows,
    insert_rows as supabase_insert_rows,
    update_rows as supabase_update_rows,
)
from redis_cache import (
    get_json as cache_get_json,
    set_json as cache_set_json,
    clear_local_cache,
    is_configured as is_redis_configured,
)

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")

_airtable_ok = None
_airtable_lock = threading.Lock()
_known_chat_ids = set()

_history_store = {}
_watchlist_store = {}
_trailer_store = {}
_error_store = []
_store_lock = threading.Lock()

TABLE_NAME_MAP = {
    "sessions": "Sessions",
    "users": "Users",
    "history": "History",
    "watchlist": "Watchlist",
    "trailer_cache": "Trailer Cache",
    "error_logs": "Error Logs",
}


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def _remember_chat_id(chat_id):
    cid = str(chat_id or "").strip()
    if cid:
        _known_chat_ids.add(cid)


def get_known_chat_ids():
    with _store_lock:
        ids = set(_known_chat_ids)
        ids.update(_history_store.keys())
        ids.update(_watchlist_store.keys())
    return sorted(ids)


def clear_runtime_cache():
    with _store_lock:
        _history_store.clear()
        _watchlist_store.clear()
        _trailer_store.clear()
        _error_store.clear()
        _known_chat_ids.clear()
    clear_local_cache()


def _api():
    from pyairtable import Api
    return Api(AIRTABLE_API_KEY)


def _tbl(name):
    return _api().table(AIRTABLE_BASE_ID, name)


def get_table(name: str):
    resolved = TABLE_NAME_MAP.get((name or "").strip().lower(), name)
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        raise RuntimeError("AIRTABLE_API_KEY or AIRTABLE_BASE_ID is not configured")
    return _tbl(resolved)


def _check_airtable():
    global _airtable_ok
    if _airtable_ok is not None:
        return _airtable_ok
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        _airtable_ok = False
        return False
    with _airtable_lock:
        if _airtable_ok is not None:
            return _airtable_ok
        try:
            t = _tbl("Sessions")
            t.all(max_records=1)
            _airtable_ok = True
        except Exception:
            _airtable_ok = False
        return _airtable_ok


def is_airtable_available():
    return bool(_check_airtable())


def log_error(
    chat_id,
    workflow_step: str,
    intent: str,
    error_type: str,
    error_message: str,
    raw_payload=None,
    retry_status: str = "not_retried",
    resolution_status: str = "open",
):
    row = {
        "timestamp": now_iso(),
        "chat_id": str(chat_id or ""),
        "workflow_step": str(workflow_step or ""),
        "intent": str(intent or ""),
        "error_type": str(error_type or ""),
        "error_message": str(error_message or ""),
        "raw_payload": raw_payload,
        "retry_status": str(retry_status or ""),
        "resolution_status": str(resolution_status or ""),
    }

    with _store_lock:
        _error_store.append(row)
        if len(_error_store) > 300:
            _error_store[:] = _error_store[-300:]

    if is_supabase_configured():
        supabase_insert_rows("error_logs", [{
            **row,
            "raw_payload": json.dumps(raw_payload, ensure_ascii=False) if raw_payload is not None else "",
        }])

    if not _check_airtable():
        return
    try:
        _tbl("Error Logs").create({
            "Timestamp": row["timestamp"],
            "Chat ID": int(chat_id) if str(chat_id).isdigit() else 0,
            "Workflow Step": row["workflow_step"],
            "Intent": row["intent"],
            "Error Type": row["error_type"],
            "Error Message": row["error_message"],
            "Raw Payload": json.dumps(raw_payload, ensure_ascii=False) if raw_payload is not None else "",
            "Retry Status": row["retry_status"],
            "Resolution Status": row["resolution_status"],
        })
    except Exception:
        pass


def get_recent_errors(limit: int = 10):
    with _store_lock:
        return list(reversed(_error_store[-max(1, int(limit or 1)):]))


def get_runtime_stats():
    with _store_lock:
        history_rows = sum(len(rows) for rows in _history_store.values())
        watchlist_rows = sum(len(rows) for rows in _watchlist_store.values())
        trailer_count = len(_trailer_store)
        error_count = len(_error_store)
    return {
        "supabase_configured": is_supabase_configured(),
        "supabase_available": is_supabase_available() if is_supabase_configured() else False,
        "redis_configured": is_redis_configured(),
        "airtable_available": is_airtable_available(),
        "cached_sessions": mem_session_count(),
        "cached_users": mem_user_count(),
        "history_rows": history_rows,
        "watchlist_rows": watchlist_rows,
        "trailer_cache_entries": trailer_count,
        "recent_error_count": error_count,
        "known_chat_ids": len(get_known_chat_ids()),
    }


def _bg(fn, *args, **kwargs):
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()



