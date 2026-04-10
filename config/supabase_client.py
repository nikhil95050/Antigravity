import json
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_API_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.environ.get("SUPABASE_API_KEY", "").strip()
)
REST_BASE = f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else ""

# Persistent AsyncClient for performance
_async_client = httpx.AsyncClient(
    timeout=httpx.Timeout(15.0, connect=5.0),
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
)

# Persistent SyncClient for legacy/internal tasks (repositories)
_sync_client = httpx.Client(timeout=15.0)

def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_API_KEY)

def _headers(prefer: str | None = None) -> dict:
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers

def _build_url_and_headers(path: str, prefer: str | None = None):
    return f"{REST_BASE}/{path.lstrip('/')}", _headers(prefer)

def _parse_response(resp):
    if 200 <= resp.status_code < 300:
        return (resp.json() if resp.text.strip() else None), None
    return None, f"Supabase error {resp.status_code}: {resp.text[:500]}"

async def _request_async(method: str, path: str, params=None, json_body=None, prefer: str | None = None):
    if not is_configured():
        return None, "supabase_not_configured"
    url, headers = _build_url_and_headers(path, prefer)
    try:
        resp = await _async_client.request(method, url, headers=headers, params=params, json=json_body)
        return _parse_response(resp)
    except Exception as e:
        return None, f"Supabase network error: {str(e)}"

def _request_sync(method: str, path: str, params=None, json_body=None, prefer: str | None = None):
    """Fallback sync request for repositories still using threads."""
    if not is_configured():
        return None, "supabase_not_configured"
    url, headers = _build_url_and_headers(path, prefer)
    try:
        resp = _sync_client.request(method, url, headers=headers, params=params, json=json_body)
        return _parse_response(resp)
    except Exception as e:
        return None, f"Supabase network error: {str(e)}"

def _format_filter(value):
    val_str = str(value)
    ops = ("eq.", "gt.", "gte.", "lt.", "lte.", "neq.", "in.", "is.")
    if any(val_str.startswith(op) for op in ops):
        return val_str
    return f"eq.{value}"

# --- Async CRUD (Preferred) ---

async def select_rows_async(table: str, filters: dict | None = None, limit: int | None = None, order: str | None = None, offset: int | None = None):
    params = {}
    if filters:
        for key, value in filters.items():
            params[key] = _format_filter(value)
    if limit: params["limit"] = limit
    if offset: params["offset"] = offset
    if order: params["order"] = order
    return await _request_async("GET", table, params=params)

async def insert_rows_async(table: str, rows: list[dict], upsert: bool = False, on_conflict: str | None = None):
    prefer = "resolution=merge-duplicates,return=representation" if upsert else "return=representation"
    params = {"on_conflict": on_conflict} if on_conflict else None
    return await _request_async("POST", table, params=params, json_body=rows, prefer=prefer)

# --- Sync Wrapper (For backward compatibility during migration) ---

def select_rows(table: str, filters: dict | None = None, limit: int | None = None, order: str | None = None, offset: int | None = None):
    params = {}
    if filters:
        for key, value in filters.items():
            params[key] = _format_filter(value)
    if limit: params["limit"] = limit
    if offset: params["offset"] = offset
    if order: params["order"] = order
    return _request_sync("GET", table, params=params)

def insert_rows(table: str, rows: list[dict], upsert: bool = False, on_conflict: str | None = None):
    prefer = "resolution=merge-duplicates,return=representation" if upsert else "return=representation"
    params = {"on_conflict": on_conflict} if on_conflict else None
    return _request_sync("POST", table, params=params, json_body=rows, prefer=prefer)

def update_rows(table: str, patch: dict, filters: dict):
    params = {key: _format_filter(value) for key, value in (filters or {}).items()}
    return _request_sync("PATCH", table, params=params, json_body=patch, prefer="return=representation")

def delete_rows(table: str, filters: dict):
    params = {key: _format_filter(value) for key, value in (filters or {}).items()}
    return _request_sync("DELETE", table, params=params, prefer="return=representation")

def is_available() -> bool:
    # We use a real table check but with no rows returned for efficiency
    try:
        data, error = select_rows("sessions", limit=0)
        return error is None
    except Exception:
        return False
