"""
Airtable client — uses in-memory store as primary fast layer.
Airtable is synced for persistence.

IMPORTANT: Field names match the actual Airtable table structure (Title Case with spaces).
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

_history_store = {}   # {chat_id_str: [row, ...]}
_watchlist_store = {} # {chat_id_str: [row, ...]}
_trailer_store = {}   # {movie_id_str: url}
_store_lock = threading.Lock()


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def _api():
    from pyairtable import Api
    return Api(AIRTABLE_API_KEY)


def _tbl(name):
    return _api().table(AIRTABLE_BASE_ID, name)


def _check_airtable():
    global _airtable_ok
    if _airtable_ok is not None:
        return _airtable_ok
    with _airtable_lock:
        if _airtable_ok is not None:
            return _airtable_ok
        try:
            t = _tbl("Sessions")
            t.all(max_records=1)
            _airtable_ok = True
            print("[Airtable] ✅ Connected successfully")
        except Exception as e:
            _airtable_ok = False
            print(f"[Airtable] ⚠️ Unavailable, using in-memory: {e}")
        return _airtable_ok


# ─── SESSIONS ──────────────────────────────────────────────────────────────────
# Airtable fields: Chat ID (number), Session State, Question Index (number),
# Pending Question, Answers Mood/Genre/Language/Era/Context/Avoid,
# Last Recs JSON (multiline), Sim Depth (number), Last Active (dateTime), Updated At (dateTime)

def _session_to_at(data: dict) -> dict:
    """Convert internal session dict to Airtable field names."""
    out = {}
    mapping = {
        "chat_id": "Chat ID",
        "session_state": "Session State",
        "question_index": "Question Index",
        "pending_question": "Pending Question",
        "answers_mood": "Answers Mood",
        "answers_genre": "Answers Genre",
        "answers_language": "Answers Language",
        "answers_era": "Answers Era",
        "answers_context": "Answers Context",
        "answers_avoid": "Answers Avoid",
        "last_recs_json": "Last Recs JSON",
        "sim_depth": "Sim Depth",
        "last_active": "Last Active",
        "updated_at": "Updated At",
    }
    for k, v in data.items():
        at_key = mapping.get(k)
        if at_key:
            # Convert number fields
            if at_key in ("Chat ID", "Question Index", "Sim Depth"):
                try:
                    v = int(v) if v not in (None, "") else 0
                except Exception:
                    v = 0
            out[at_key] = v
    return out


def _at_to_session(fields: dict) -> dict:
    """Convert Airtable fields back to internal session format."""
    reverse = {
        "Chat ID": "chat_id",
        "Session State": "session_state",
        "Question Index": "question_index",
        "Pending Question": "pending_question",
        "Answers Mood": "answers_mood",
        "Answers Genre": "answers_genre",
        "Answers Language": "answers_language",
        "Answers Era": "answers_era",
        "Answers Context": "answers_context",
        "Answers Avoid": "answers_avoid",
        "Last Recs JSON": "last_recs_json",
        "Sim Depth": "sim_depth",
        "Last Active": "last_active",
        "Updated At": "updated_at",
    }
    out = {}
    for at_k, int_k in reverse.items():
        if at_k in fields:
            out[int_k] = fields[at_k]
    return out


def get_session(chat_id):
    session = mem_get_session(chat_id)
    if session:
        return session
    if _check_airtable():
        try:
            t = _tbl("Sessions")
            records = t.all(formula=f"{{Chat ID}}={chat_id}")
            if records:
                data = _at_to_session(records[0]["fields"])
                mem_set_session(chat_id, data)
                return data
        except Exception as e:
            print(f"[Airtable] get_session error: {e}")
    return {}


def _bg(fn, *args, **kwargs):
    """Run Airtable write in background thread (non-blocking)."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()


def _do_upsert_session(chat_id, patch):
    if not _check_airtable():
        return
    try:
        t = _tbl("Sessions")
        records = t.all(formula=f"{{Chat ID}}={chat_id}")
        at_patch = _session_to_at({**patch, "chat_id": int(chat_id)})
        if records:
            t.update(records[0]["id"], at_patch)
        else:
            full = mem_get_session(chat_id)
            full["chat_id"] = chat_id
            t.create(_session_to_at(full))
    except Exception as e:
        print(f"[Airtable] upsert_session error: {e}")


def upsert_session(chat_id, patch: dict):
    patch["updated_at"] = now_iso()
    mem_set_session(chat_id, patch)
    _bg(_do_upsert_session, chat_id, dict(patch))


def reset_session(chat_id):
    mem_reset_session(chat_id)
    if _check_airtable():
        try:
            t = _tbl("Sessions")
            records = t.all(formula=f"{{Chat ID}}={chat_id}")
            data = _session_to_at({**mem_get_session(chat_id), "chat_id": int(chat_id)})
            if records:
                t.update(records[0]["id"], data)
            else:
                t.create(data)
        except Exception as e:
            print(f"[Airtable] reset_session error: {e}")


# ─── USERS ──────────────────────────────────────────────────────────────────────
# Airtable fields: Chat ID (number), Username, Preferred Genres (multiline),
# Disliked Genres (multiline), Preferred Language, Preferred Era,
# Watch Context, Avg Rating Preference (number), Updated At (dateTime)

def _user_to_at(data: dict) -> dict:
    mapping = {
        "chat_id": "Chat ID",
        "username": "Username",
        "preferred_genres": "Preferred Genres",
        "disliked_genres": "Disliked Genres",
        "preferred_language": "Preferred Language",
        "preferred_era": "Preferred Era",
        "watch_context": "Watch Context",
        "avg_rating_preference": "Avg Rating Preference",
        "updated_at": "Updated At",
    }
    out = {}
    for k, v in data.items():
        at_key = mapping.get(k)
        if at_key:
            if at_key == "Chat ID":
                try:
                    v = int(v)
                except Exception:
                    v = 0
            elif at_key == "Avg Rating Preference":
                try:
                    v = float(v) if v not in (None, "") else None
                except Exception:
                    v = None
                if v is None:
                    continue
            out[at_key] = v
    return out


def _at_to_user(fields: dict) -> dict:
    reverse = {
        "Chat ID": "chat_id",
        "Username": "username",
        "Preferred Genres": "preferred_genres",
        "Disliked Genres": "disliked_genres",
        "Preferred Language": "preferred_language",
        "Preferred Era": "preferred_era",
        "Watch Context": "watch_context",
        "Avg Rating Preference": "avg_rating_preference",
        "Updated At": "updated_at",
    }
    return {int_k: fields[at_k] for at_k, int_k in reverse.items() if at_k in fields}


def get_user(chat_id):
    user = mem_get_user(chat_id)
    if user:
        return user
    if _check_airtable():
        try:
            t = _tbl("Users")
            records = t.all(formula=f"{{Chat ID}}={chat_id}")
            if records:
                data = _at_to_user(records[0]["fields"])
                mem_set_user(chat_id, data.get("username", ""), data)
                return data
        except Exception as e:
            print(f"[Airtable] get_user error: {e}")
    return {}


def _do_upsert_user(chat_id, username, update):
    if not _check_airtable():
        return
    try:
        t = _tbl("Users")
        records = t.all(formula=f"{{Chat ID}}={chat_id}")
        update["updated_at"] = now_iso()
        at_data = _user_to_at({**update, "chat_id": int(chat_id)})
        if records:
            t.update(records[0]["id"], at_data)
        else:
            full = mem_get_user(chat_id)
            full["chat_id"] = chat_id
            full["username"] = username or ""
            t.create(_user_to_at(full))
    except Exception as e:
        print(f"[Airtable] upsert_user error: {e}")


def upsert_user(chat_id, username, patch: dict = None):
    update = patch or {}
    if username:
        update["username"] = username
    mem_set_user(chat_id, username, update)
    _bg(_do_upsert_user, chat_id, username, dict(update))


# ─── HISTORY ────────────────────────────────────────────────────────────────────
# Airtable fields: Title, Chat ID (number), Movie ID, Year, Genres, Language,
# Rating, Recommended At (dateTime), Watched (checkbox), Watched At (dateTime)

def _history_to_at(row: dict) -> dict:
    out = {
        "Title": str(row.get("title", "")),
        "Chat ID": int(row.get("chat_id", 0)),
        "Movie ID": str(row.get("movie_id", "")),
        "Year": str(row.get("year", "")),
        "Genres": str(row.get("genres", "")),
        "Language": str(row.get("language", "")),
        "Rating": str(row.get("rating", "")),
        "Recommended At": row.get("recommended_at") or now_iso(),
        "Watched": bool(row.get("watched", False)),
    }
    if row.get("watched_at"):
        out["Watched At"] = row["watched_at"]
    return out


def _at_to_history(fields: dict) -> dict:
    return {
        "title": fields.get("Title", ""),
        "chat_id": str(fields.get("Chat ID", "")),
        "movie_id": fields.get("Movie ID", ""),
        "year": fields.get("Year", ""),
        "genres": fields.get("Genres", ""),
        "language": fields.get("Language", ""),
        "rating": fields.get("Rating", ""),
        "recommended_at": fields.get("Recommended At", ""),
        "watched": bool(fields.get("Watched", False)),
        "watched_at": fields.get("Watched At", ""),
    }


def get_history(chat_id, limit=20):
    with _store_lock:
        local = list(reversed(_history_store.get(str(chat_id), [])))[:limit]
    if local:
        return local
    if _check_airtable():
        try:
            t = _tbl("History")
            records = t.all(
                formula=f"{{Chat ID}}={chat_id}",
                sort=[{"field": "Recommended At", "direction": "desc"}]
            )
            return [_at_to_history(r["fields"]) for r in records[:limit]]
        except Exception as e:
            print(f"[Airtable] get_history error: {e}")
    return []


def _do_insert_history(rows):
    if not _check_airtable():
        return
    try:
        t = _tbl("History")
        for row in rows:
            t.create(_history_to_at(row))
    except Exception as e:
        print(f"[Airtable] insert_history error: {e}")


def insert_history_rows(rows: list):
    ts = now_iso()
    for row in rows:
        row["recommended_at"] = ts

    with _store_lock:
        for row in rows:
            cid = str(row.get("chat_id", ""))
            if cid not in _history_store:
                _history_store[cid] = []
            existing_ids = {r.get("movie_id") for r in _history_store[cid]}
            if row.get("movie_id") not in existing_ids:
                _history_store[cid].append(row)

    _bg(_do_insert_history, list(rows))


def update_history_watched(chat_id, movie_id, watched: bool = True):
    with _store_lock:
        for row in _history_store.get(str(chat_id), []):
            if row.get("movie_id") == movie_id:
                row["watched"] = watched
                if watched:
                    row["watched_at"] = now_iso()
    if _check_airtable():
        try:
            t = _tbl("History")
            records = t.all(
                formula=f"AND({{Chat ID}}={chat_id},{{Movie ID}}='{movie_id}')"
            )
            if records:
                patch = {"Watched": watched}
                if watched:
                    patch["Watched At"] = now_iso()
                t.update(records[0]["id"], patch)
        except Exception as e:
            print(f"[Airtable] update_history_watched error: {e}")


def get_movie_from_history(chat_id, movie_id):
    with _store_lock:
        for row in _history_store.get(str(chat_id), []):
            if row.get("movie_id") == movie_id:
                return dict(row)
    if _check_airtable():
        try:
            t = _tbl("History")
            records = t.all(
                formula=f"AND({{Chat ID}}={chat_id},{{Movie ID}}='{movie_id}')"
            )
            if records:
                return _at_to_history(records[0]["fields"])
        except Exception as e:
            print(f"[Airtable] get_movie_from_history error: {e}")
    return None


# ─── WATCHLIST ───────────────────────────────────────────────────────────────────
# Airtable fields: Title, Chat ID (number), Movie ID, Year, Language, Rating, Genres, Added At (dateTime)

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
            t = _tbl("Watchlist")
            existing = t.all(
                formula=f"AND({{Chat ID}}={chat_id},{{Movie ID}}='{movie_id}')"
            )
            if not existing:
                t.create({
                    "Title": str(movie.get("title", "")),
                    "Chat ID": int(chat_id),
                    "Movie ID": movie_id,
                    "Year": str(movie.get("year", "")),
                    "Language": str(movie.get("language", "")),
                    "Rating": str(movie.get("rating", "")),
                    "Genres": str(movie.get("genres", "")),
                    "Added At": now_iso(),
                })
        except Exception as e:
            print(f"[Airtable] save_to_watchlist error: {e}")
    return True


# ─── TRAILER CACHE ───────────────────────────────────────────────────────────────
# Airtable fields: Movie ID, Trailer URL (url), Cached At (dateTime)

def get_trailer_cache(movie_id):
    with _store_lock:
        cached = _trailer_store.get(str(movie_id))
    if cached:
        return cached
    if _check_airtable():
        try:
            t = _tbl("Trailer Cache")
            records = t.all(formula=f"{{Movie ID}}='{movie_id}'")
            if records:
                url = records[0]["fields"].get("Trailer URL")
                if url:
                    with _store_lock:
                        _trailer_store[str(movie_id)] = url
                return url
        except Exception as e:
            print(f"[Airtable] get_trailer_cache error: {e}")
    return None


def set_trailer_cache(movie_id, trailer_url):
    with _store_lock:
        _trailer_store[str(movie_id)] = trailer_url
    if _check_airtable():
        try:
            t = _tbl("Trailer Cache")
            existing = t.all(formula=f"{{Movie ID}}='{movie_id}'")
            data = {
                "Movie ID": str(movie_id),
                "Trailer URL": trailer_url,
                "Cached At": now_iso(),
            }
            if existing:
                t.update(existing[0]["id"], data)
            else:
                t.create(data)
        except Exception as e:
            print(f"[Airtable] set_trailer_cache error: {e}")
