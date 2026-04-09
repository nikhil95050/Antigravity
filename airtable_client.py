"""
Airtable client with in-memory session store as primary layer.
Airtable is used for persistence when available (token has correct scopes).
In-memory store ensures the bot always works even during Airtable setup.
"""
import os
import json
import threading
from datetime import datetime

from session_store import (
    mem_get_session, mem_set_session, mem_reset_session,
    mem_get_user, mem_set_user
)

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")

_airtable_ok = None
_airtable_lock = threading.Lock()

_history_store = {}
_watchlist_store = {}
_trailer_store = {}
_store_lock = threading.Lock()


def now_iso():
    return datetime.utcnow().isoformat()


def _get_pyairtable():
    try:
        from pyairtable import Api
        return Api(AIRTABLE_API_KEY)
    except Exception:
        return None


def _check_airtable():
    global _airtable_ok
    if _airtable_ok is not None:
        return _airtable_ok
    with _airtable_lock:
        if _airtable_ok is not None:
            return _airtable_ok
        try:
            api = _get_pyairtable()
            if not api:
                _airtable_ok = False
                return False
            t = api.table(AIRTABLE_BASE_ID, "sessions")
            t.all(max_records=1)
            _airtable_ok = True
            print("[Airtable] Connection OK")
        except Exception as e:
            _airtable_ok = False
            print(f"[Airtable] Unavailable, using in-memory store: {e}")
        return _airtable_ok


def _get_table(name):
    api = _get_pyairtable()
    if api:
        return api.table(AIRTABLE_BASE_ID, name)
    return None


# ─── SESSIONS ──────────────────────────────────────────────────────────────────

def get_session(chat_id):
    session = mem_get_session(chat_id)
    if session:
        return session
    if _check_airtable():
        try:
            t = _get_table("sessions")
            records = t.all(formula=f"{{chat_id}}='{chat_id}'")
            if records:
                data = records[0]["fields"]
                mem_set_session(chat_id, data)
                return data
        except Exception as e:
            print(f"[Airtable] get_session error: {e}")
    return {}


def upsert_session(chat_id, patch: dict):
    patch["updated_at"] = now_iso()
    mem_set_session(chat_id, patch)
    if _check_airtable():
        try:
            t = _get_table("sessions")
            records = t.all(formula=f"{{chat_id}}='{chat_id}'")
            if records:
                t.update(records[0]["id"], patch)
            else:
                full = mem_get_session(chat_id)
                full["chat_id"] = str(chat_id)
                t.create(full)
        except Exception as e:
            print(f"[Airtable] upsert_session error (non-critical): {e}")


def reset_session(chat_id):
    mem_reset_session(chat_id)
    if _check_airtable():
        try:
            t = _get_table("sessions")
            records = t.all(formula=f"{{chat_id}}='{chat_id}'")
            reset_data = mem_get_session(chat_id)
            if records:
                t.update(records[0]["id"], reset_data)
            else:
                t.create(reset_data)
        except Exception as e:
            print(f"[Airtable] reset_session error (non-critical): {e}")


# ─── USERS ──────────────────────────────────────────────────────────────────────

def get_user(chat_id):
    user = mem_get_user(chat_id)
    if user:
        return user
    if _check_airtable():
        try:
            t = _get_table("users")
            records = t.all(formula=f"{{chat_id}}='{chat_id}'")
            if records:
                data = records[0]["fields"]
                mem_set_user(chat_id, data.get("username", ""), data)
                return data
        except Exception as e:
            print(f"[Airtable] get_user error (non-critical): {e}")
    return {}


def upsert_user(chat_id, username, patch: dict = None):
    mem_set_user(chat_id, username, patch)
    if _check_airtable():
        try:
            t = _get_table("users")
            records = t.all(formula=f"{{chat_id}}='{chat_id}'")
            data = patch or {}
            data["updated_at"] = now_iso()
            if records:
                t.update(records[0]["id"], data)
            else:
                data["chat_id"] = str(chat_id)
                data["username"] = username or ""
                t.create(data)
        except Exception as e:
            print(f"[Airtable] upsert_user error (non-critical): {e}")


# ─── HISTORY ────────────────────────────────────────────────────────────────────

def get_history(chat_id, limit=20):
    with _store_lock:
        local = list(reversed(_history_store.get(str(chat_id), [])))[:limit]
    if local:
        return local
    if _check_airtable():
        try:
            t = _get_table("history")
            records = t.all(
                formula=f"{{chat_id}}='{chat_id}'",
                sort=[{"field": "recommended_at", "direction": "desc"}]
            )
            return [r["fields"] for r in records[:limit]]
        except Exception as e:
            print(f"[Airtable] get_history error (non-critical): {e}")
    return []


def insert_history_rows(rows: list):
    ts = now_iso()
    with _store_lock:
        for row in rows:
            cid = str(row.get("chat_id", ""))
            row["recommended_at"] = ts
            if cid not in _history_store:
                _history_store[cid] = []
            existing_ids = {r.get("movie_id") for r in _history_store[cid]}
            if row.get("movie_id") not in existing_ids:
                _history_store[cid].append(row)
    if _check_airtable():
        try:
            t = _get_table("history")
            for row in rows:
                row["recommended_at"] = ts
                t.create(row)
        except Exception as e:
            print(f"[Airtable] insert_history error (non-critical): {e}")


def update_history_watched(chat_id, movie_id, watched: bool = True):
    with _store_lock:
        for row in _history_store.get(str(chat_id), []):
            if row.get("movie_id") == movie_id:
                row["watched"] = watched
                if watched:
                    row["watched_at"] = now_iso()
    if _check_airtable():
        try:
            t = _get_table("history")
            records = t.all(
                formula=f"AND({{chat_id}}='{chat_id}',{{movie_id}}='{movie_id}')"
            )
            if records:
                patch = {"watched": watched}
                if watched:
                    patch["watched_at"] = now_iso()
                t.update(records[0]["id"], patch)
        except Exception as e:
            print(f"[Airtable] update_history_watched error (non-critical): {e}")


def get_movie_from_history(chat_id, movie_id):
    with _store_lock:
        for row in _history_store.get(str(chat_id), []):
            if row.get("movie_id") == movie_id:
                return dict(row)
    if _check_airtable():
        try:
            t = _get_table("history")
            records = t.all(
                formula=f"AND({{chat_id}}='{chat_id}',{{movie_id}}='{movie_id}')"
            )
            if records:
                return records[0]["fields"]
        except Exception as e:
            print(f"[Airtable] get_movie_from_history error (non-critical): {e}")
    return None


# ─── WATCHLIST ───────────────────────────────────────────────────────────────────

def save_to_watchlist(chat_id, movie: dict):
    cid = str(chat_id)
    movie_id = str(movie.get("movie_id", ""))
    with _store_lock:
        wl = _watchlist_store.get(cid, [])
        if any(w.get("movie_id") == movie_id for w in wl):
            return False
        wl.append({**movie, "chat_id": cid, "movie_id": movie_id})
        _watchlist_store[cid] = wl
    if _check_airtable():
        try:
            t = _get_table("watchlist")
            existing = t.all(
                formula=f"AND({{chat_id}}='{chat_id}',{{movie_id}}='{movie_id}')"
            )
            if not existing:
                t.create({
                    "chat_id": cid,
                    "movie_id": movie_id,
                    "title": movie.get("title", ""),
                    "year": str(movie.get("year", "")),
                    "language": movie.get("language", ""),
                    "rating": str(movie.get("rating", "")),
                    "genres": movie.get("genres", ""),
                })
        except Exception as e:
            print(f"[Airtable] save_to_watchlist error (non-critical): {e}")
    return True


# ─── TRAILER CACHE ───────────────────────────────────────────────────────────────

def get_trailer_cache(movie_id):
    with _store_lock:
        cached = _trailer_store.get(str(movie_id))
    if cached:
        return cached
    if _check_airtable():
        try:
            t = _get_table("trailer_cache")
            records = t.all(formula=f"{{movie_id}}='{movie_id}'")
            if records:
                url = records[0]["fields"].get("trailer_url")
                if url:
                    with _store_lock:
                        _trailer_store[str(movie_id)] = url
                return url
        except Exception as e:
            print(f"[Airtable] get_trailer_cache error (non-critical): {e}")
    return None


def set_trailer_cache(movie_id, trailer_url):
    with _store_lock:
        _trailer_store[str(movie_id)] = trailer_url
    if _check_airtable():
        try:
            t = _get_table("trailer_cache")
            existing = t.all(formula=f"{{movie_id}}='{movie_id}'")
            data = {
                "movie_id": str(movie_id),
                "trailer_url": trailer_url,
                "cached_at": now_iso(),
            }
            if existing:
                t.update(existing[0]["id"], data)
            else:
                t.create(data)
        except Exception as e:
            print(f"[Airtable] set_trailer_cache error (non-critical): {e}")
