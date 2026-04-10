import json
import os
from dotenv import load_dotenv

load_dotenv()

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_API_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.environ.get("SUPABASE_API_KEY", "").strip()
)
REST_BASE = f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else ""


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


def _request(method: str, path: str, params=None, json_body=None, prefer: str | None = None):
    if not is_configured():
        return None, "supabase_not_configured"
    try:
        resp = requests.request(
            method,
            f"{REST_BASE}/{path.lstrip('/')}",
            headers=_headers(prefer),
            params=params,
            json=json_body,
            timeout=10,
        )
        if 200 <= resp.status_code < 300:
            if not resp.text.strip():
                return None, None
            try:
                return resp.json(), None
            except Exception:
                return resp.text, None
        return None, f"{resp.status_code}: {resp.text[:300]}"
    except Exception as e:
        return None, str(e)


def _format_filter(value):
    val_str = str(value)
    ops = ("eq.", "gt.", "gte.", "lt.", "lte.", "neq.", "in.", "is.")
    if any(val_str.startswith(op) for op in ops):
        return val_str
    return f"eq.{value}"


def select_rows(table: str, filters: dict | None = None, limit: int | None = None, order: str | None = None):
    params = {}
    if filters:
        for key, value in filters.items():
            params[key] = _format_filter(value)
    if limit:
        params["limit"] = limit
    if order:
        params["order"] = order
    return _request("GET", table, params=params)


def insert_rows(table: str, rows: list[dict], upsert: bool = False, on_conflict: str | None = None):
    prefer = "return=representation"
    if upsert:
        prefer = "resolution=merge-duplicates,return=representation"
    params = {"on_conflict": on_conflict} if on_conflict else None
    return _request("POST", table, params=params, json_body=rows, prefer=prefer)


def update_rows(table: str, patch: dict, filters: dict):
    params = {key: _format_filter(value) for key, value in (filters or {}).items()}
    return _request("PATCH", table, params=params, json_body=patch, prefer="return=representation")


def delete_rows(table: str, filters: dict):
    params = {key: _format_filter(value) for key, value in (filters or {}).items()}
    return _request("DELETE", table, params=params, prefer="return=representation")


def is_available() -> bool:
    data, error = select_rows("sessions", limit=1)
    return error is None
