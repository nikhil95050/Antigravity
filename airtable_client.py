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

from session_store import (
    mem_get_session, mem_set_session, mem_reset_session,
    mem_get_user, mem_set_user, mem_session_count, mem_user_count,
)
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


def get_session(chat_id):
    _remember_chat_id(chat_id)
    cached = cache_get_json(f"session:{chat_id}")
    if isinstance(cached, dict) and cached:
        mem_set_session(chat_id, cached)
        return cached

    session = mem_get_session(chat_id)
    if session:
        return session

    if is_supabase_configured():
        rows, error = supabase_select_rows("sessions", {"chat_id": chat_id}, limit=1)
        if not error and rows:
            data = rows[0]
            mem_set_session(chat_id, data)
            cache_set_json(f"session:{chat_id}", data, ttl=3600)
            return data

    if _check_airtable():
        try:
            records = _tbl("Sessions").all(formula=f"{{Chat ID}}={chat_id}")
            if records:
                fields = records[0]["fields"]
                data = {
                    "chat_id": str(fields.get("Chat ID", "")),
                    "session_state": fields.get("Session State", "idle"),
                    "question_index": fields.get("Question Index", 0),
                    "pending_question": fields.get("Pending Question", ""),
                    "answers_mood": fields.get("Answers Mood", ""),
                    "answers_genre": fields.get("Answers Genre", ""),
                    "answers_language": fields.get("Answers Language", ""),
                    "answers_era": fields.get("Answers Era", ""),
                    "answers_context": fields.get("Answers Context", ""),
                    "answers_avoid": fields.get("Answers Avoid", ""),
                    "last_recs_json": fields.get("Last Recs JSON", "[]"),
                    "sim_depth": fields.get("Sim Depth", 0),
                    "last_active": fields.get("Last Active", ""),
                    "updated_at": fields.get("Updated At", ""),
                }
                mem_set_session(chat_id, data)
                cache_set_json(f"session:{chat_id}", data, ttl=3600)
                return data
        except Exception:
            pass
    return {}


def _write_supabase_session(chat_id, patch: dict):
    if not is_supabase_configured():
        return
    payload = {**mem_get_session(chat_id), **patch, "chat_id": str(chat_id)}
    supabase_insert_rows("sessions", [payload], upsert=True, on_conflict="chat_id")


def _write_airtable_session(chat_id, patch: dict):
    if not _check_airtable():
        return
    try:
        table = _tbl("Sessions")
        records = table.all(formula=f"{{Chat ID}}={chat_id}")
        data = {
            "Chat ID": int(chat_id),
            "Session State": patch.get("session_state", mem_get_session(chat_id).get("session_state", "idle")),
            "Question Index": int(patch.get("question_index", mem_get_session(chat_id).get("question_index", 0) or 0)),
            "Pending Question": patch.get("pending_question", mem_get_session(chat_id).get("pending_question", "")),
            "Answers Mood": patch.get("answers_mood", mem_get_session(chat_id).get("answers_mood", "")),
            "Answers Genre": patch.get("answers_genre", mem_get_session(chat_id).get("answers_genre", "")),
            "Answers Language": patch.get("answers_language", mem_get_session(chat_id).get("answers_language", "")),
            "Answers Era": patch.get("answers_era", mem_get_session(chat_id).get("answers_era", "")),
            "Answers Context": patch.get("answers_context", mem_get_session(chat_id).get("answers_context", "")),
            "Answers Avoid": patch.get("answers_avoid", mem_get_session(chat_id).get("answers_avoid", "")),
            "Last Recs JSON": patch.get("last_recs_json", mem_get_session(chat_id).get("last_recs_json", "[]")),
            "Sim Depth": int(patch.get("sim_depth", mem_get_session(chat_id).get("sim_depth", 0) or 0)),
            "Last Active": patch.get("last_active", mem_get_session(chat_id).get("last_active", now_iso())),
            "Updated At": patch.get("updated_at", now_iso()),
        }
        if records:
            table.update(records[0]["id"], data)
        else:
            table.create(data)
    except Exception as e:
        log_error(chat_id, "airtable.upsert_session", "", "airtable_write_failed", str(e), raw_payload=patch)


def upsert_session(chat_id, patch: dict):
    payload = dict(patch)
    payload["updated_at"] = now_iso()
    mem_set_session(chat_id, payload)
    cache_set_json(f"session:{chat_id}", mem_get_session(chat_id), ttl=3600)
    _remember_chat_id(chat_id)
    _bg(_write_supabase_session, chat_id, payload)
    _bg(_write_airtable_session, chat_id, payload)


def reset_session(chat_id):
    mem_reset_session(chat_id)
    cache_set_json(f"session:{chat_id}", mem_get_session(chat_id), ttl=3600)
    payload = mem_get_session(chat_id)
    _bg(_write_supabase_session, chat_id, payload)
    _bg(_write_airtable_session, chat_id, payload)


def get_user(chat_id):
    _remember_chat_id(chat_id)
    cached = cache_get_json(f"user:{chat_id}")
    if isinstance(cached, dict) and cached:
        mem_set_user(chat_id, cached.get("username", ""), cached)
        return cached

    user = mem_get_user(chat_id)
    if user:
        return user

    if is_supabase_configured():
        rows, error = supabase_select_rows("users", {"chat_id": chat_id}, limit=1)
        if not error and rows:
            data = rows[0]
            mem_set_user(chat_id, data.get("username", ""), data)
            cache_set_json(f"user:{chat_id}", data, ttl=3600)
            return data

    if _check_airtable():
        try:
            records = _tbl("Users").all(formula=f"{{Chat ID}}={chat_id}")
            if records:
                fields = records[0]["fields"]
                data = {
                    "chat_id": str(fields.get("Chat ID", "")),
                    "username": fields.get("Username", ""),
                    "preferred_genres": fields.get("Preferred Genres", ""),
                    "disliked_genres": fields.get("Disliked Genres", ""),
                    "preferred_language": fields.get("Preferred Language", ""),
                    "preferred_era": fields.get("Preferred Era", ""),
                    "watch_context": fields.get("Watch Context", ""),
                    "avg_rating_preference": fields.get("Avg Rating Preference", ""),
                    "updated_at": fields.get("Updated At", ""),
                }
                mem_set_user(chat_id, data.get("username", ""), data)
                cache_set_json(f"user:{chat_id}", data, ttl=3600)
                return data
        except Exception:
            pass
    return {}


def _write_supabase_user(chat_id, username, patch: dict):
    if not is_supabase_configured():
        return
    payload = {**mem_get_user(chat_id), **patch, "chat_id": str(chat_id)}
    if username and not payload.get("username"):
        payload["username"] = username
    supabase_insert_rows("users", [payload], upsert=True, on_conflict="chat_id")


def _write_airtable_user(chat_id, username, patch: dict):
    if not _check_airtable():
        return
    try:
        table = _tbl("Users")
        records = table.all(formula=f"{{Chat ID}}={chat_id}")
        state = mem_get_user(chat_id)
        data = {
            "Chat ID": int(chat_id),
            "Username": patch.get("username", username or state.get("username", "")),
            "Preferred Genres": patch.get("preferred_genres", state.get("preferred_genres", "")),
            "Disliked Genres": patch.get("disliked_genres", state.get("disliked_genres", "")),
            "Preferred Language": patch.get("preferred_language", state.get("preferred_language", "")),
            "Preferred Era": patch.get("preferred_era", state.get("preferred_era", "")),
            "Watch Context": patch.get("watch_context", state.get("watch_context", "")),
            "Avg Rating Preference": patch.get("avg_rating_preference", state.get("avg_rating_preference", "")),
            "Updated At": now_iso(),
        }
        if records:
            table.update(records[0]["id"], data)
        else:
            table.create(data)
    except Exception as e:
        log_error(chat_id, "airtable.upsert_user", "", "airtable_write_failed", str(e), raw_payload=patch)


def upsert_user(chat_id, username, patch: dict = None):
    update = dict(patch or {})
    if username:
        update["username"] = username
    mem_set_user(chat_id, username, update)
    cache_set_json(f"user:{chat_id}", mem_get_user(chat_id), ttl=3600)
    _remember_chat_id(chat_id)
    _bg(_write_supabase_user, chat_id, username, update)
    _bg(_write_airtable_user, chat_id, username, update)


def get_history(chat_id, limit=20):
    with _store_lock:
        local = list(reversed(_history_store.get(str(chat_id), [])))[:limit]
    if local:
        return local

    if is_supabase_configured():
        rows, error = supabase_select_rows("history", {"chat_id": chat_id}, limit=limit, order="recommended_at.desc")
        if not error and rows:
            return rows

    if _check_airtable():
        try:
            records = _tbl("History").all(formula=f"{{Chat ID}}={chat_id}")
            return [{
                "title": r["fields"].get("Title", ""),
                "chat_id": str(r["fields"].get("Chat ID", "")),
                "movie_id": r["fields"].get("Movie ID", ""),
                "year": r["fields"].get("Year", ""),
                "genres": r["fields"].get("Genres", ""),
                "language": r["fields"].get("Language", ""),
                "rating": r["fields"].get("Rating", ""),
                "recommended_at": r["fields"].get("Recommended At", ""),
                "watched": bool(r["fields"].get("Watched", False)),
                "watched_at": r["fields"].get("Watched At", ""),
            } for r in records[:limit]]
        except Exception:
            pass
    return []


def _write_supabase_history(rows: list):
    if is_supabase_configured() and rows:
        supabase_insert_rows("history", rows)


def _write_airtable_history(rows: list):
    if not rows or not _check_airtable():
        return
    try:
        table = _tbl("History")
        for row in rows:
            table.create({
                "Title": row.get("title", ""),
                "Chat ID": int(row.get("chat_id", 0)),
                "Movie ID": row.get("movie_id", ""),
                "Year": row.get("year", ""),
                "Genres": row.get("genres", ""),
                "Language": row.get("language", ""),
                "Rating": row.get("rating", ""),
                "Recommended At": row.get("recommended_at", now_iso()),
                "Watched": bool(row.get("watched", False)),
                "Watched At": row.get("watched_at", ""),
            })
    except Exception as e:
        log_error(rows[0].get("chat_id") if rows else "", "airtable.insert_history", "", "airtable_write_failed", str(e), raw_payload=rows[:3])


def insert_history_rows(rows: list):
    ts = now_iso()
    for row in rows:
        row["recommended_at"] = ts
        _remember_chat_id(row.get("chat_id"))
    with _store_lock:
        for row in rows:
            cid = str(row.get("chat_id", ""))
            _history_store.setdefault(cid, [])
            existing_ids = {r.get("movie_id") for r in _history_store[cid]}
            if row.get("movie_id") not in existing_ids:
                _history_store[cid].append(row)
    _bg(_write_supabase_history, list(rows))
    _bg(_write_airtable_history, list(rows))


def update_history_watched(chat_id, movie_id, watched: bool = True):
    with _store_lock:
        for row in _history_store.get(str(chat_id), []):
            if row.get("movie_id") == movie_id:
                row["watched"] = watched
                row["watched_at"] = now_iso() if watched else ""

    if is_supabase_configured():
        patch = {"watched": watched, "watched_at": now_iso() if watched else None}
        supabase_update_rows("history", patch, {"chat_id": str(chat_id), "movie_id": movie_id})

    if _check_airtable():
        try:
            table = _tbl("History")
            records = table.all(formula=f"AND({{Chat ID}}={chat_id},{{Movie ID}}='{movie_id}')")
            if records:
                patch = {"Watched": watched}
                if watched:
                    patch["Watched At"] = now_iso()
                table.update(records[0]["id"], patch)
        except Exception as e:
            log_error(chat_id, "airtable.update_history_watched", "", "airtable_write_failed", str(e), raw_payload={"movie_id": movie_id, "watched": watched})


def get_movie_from_history(chat_id, movie_id):
    with _store_lock:
        for row in _history_store.get(str(chat_id), []):
            if row.get("movie_id") == movie_id:
                return dict(row)

    if is_supabase_configured():
        rows, error = supabase_select_rows("history", {"chat_id": chat_id, "movie_id": movie_id}, limit=1)
        if not error and rows:
            return rows[0]

    if _check_airtable():
        try:
            records = _tbl("History").all(formula=f"AND({{Chat ID}}={chat_id},{{Movie ID}}='{movie_id}')")
            if records:
                fields = records[0]["fields"]
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
        except Exception:
            pass
    return None


def save_to_watchlist(chat_id, movie: dict):
    cid = str(chat_id)
    movie_id = str(movie.get("movie_id", ""))
    _remember_chat_id(chat_id)
    with _store_lock:
        wl = _watchlist_store.get(cid, [])
        if any(w.get("movie_id") == movie_id for w in wl):
            return False
        wl.append({**movie, "chat_id": cid, "movie_id": movie_id, "added_at": now_iso()})
        _watchlist_store[cid] = wl

    if is_supabase_configured():
        supabase_insert_rows("watchlist", [{
            "chat_id": cid,
            "movie_id": movie_id,
            "title": movie.get("title", ""),
            "year": str(movie.get("year", "")),
            "language": movie.get("language", ""),
            "rating": str(movie.get("rating", "")),
            "genres": movie.get("genres", ""),
            "added_at": now_iso(),
        }], upsert=True, on_conflict="chat_id,movie_id")

    if _check_airtable():
        try:
            table = _tbl("Watchlist")
            existing = table.all(formula=f"AND({{Chat ID}}={chat_id},{{Movie ID}}='{movie_id}')")
            if not existing:
                table.create({
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
            log_error(chat_id, "airtable.save_to_watchlist", "", "airtable_write_failed", str(e), raw_payload={"movie_id": movie_id, "title": movie.get("title", "")})
    return True


def get_watchlist(chat_id, limit=25):
    cid = str(chat_id)
    with _store_lock:
        local = list(reversed(_watchlist_store.get(cid, [])))[:limit]
    if local:
        return local

    if is_supabase_configured():
        rows, error = supabase_select_rows("watchlist", {"chat_id": cid}, limit=limit, order="added_at.desc")
        if not error and rows:
            return rows

    if _check_airtable():
        try:
            records = _tbl("Watchlist").all(formula=f"{{Chat ID}}={chat_id}")
            items = []
            for record in records[:limit]:
                fields = record.get("fields", {})
                items.append({
                    "title": fields.get("Title", ""),
                    "chat_id": str(fields.get("Chat ID", "")),
                    "movie_id": fields.get("Movie ID", ""),
                    "year": fields.get("Year", ""),
                    "language": fields.get("Language", ""),
                    "rating": fields.get("Rating", ""),
                    "genres": fields.get("Genres", ""),
                    "added_at": fields.get("Added At", ""),
                })
            return items
        except Exception as e:
            log_error(chat_id, "airtable.get_watchlist", "", "airtable_read_failed", str(e))
    return []


def get_trailer_cache(movie_id):
    cached = cache_get_json(f"trailer:{movie_id}")
    if cached:
        return cached

    with _store_lock:
        local = _trailer_store.get(str(movie_id))
    if local:
        return local

    if is_supabase_configured():
        rows, error = supabase_select_rows("trailer_cache", {"movie_id": str(movie_id)}, limit=1)
        if not error and rows:
            url = rows[0].get("trailer_url")
            if url:
                with _store_lock:
                    _trailer_store[str(movie_id)] = url
                cache_set_json(f"trailer:{movie_id}", url, ttl=86400)
                return url

    if _check_airtable():
        try:
            records = _tbl("Trailer Cache").all(formula=f"{{Movie ID}}='{movie_id}'")
            if records:
                url = records[0]["fields"].get("Trailer URL")
                if url:
                    with _store_lock:
                        _trailer_store[str(movie_id)] = url
                    cache_set_json(f"trailer:{movie_id}", url, ttl=86400)
                return url
        except Exception as e:
            log_error("", "airtable.get_trailer_cache", "", "airtable_read_failed", str(e), raw_payload={"movie_id": movie_id})
    return None


def set_trailer_cache(movie_id, trailer_url):
    with _store_lock:
        _trailer_store[str(movie_id)] = trailer_url
    cache_set_json(f"trailer:{movie_id}", trailer_url, ttl=86400)

    if is_supabase_configured():
        supabase_insert_rows("trailer_cache", [{
            "movie_id": str(movie_id),
            "trailer_url": trailer_url,
            "cached_at": now_iso(),
        }], upsert=True, on_conflict="movie_id")

    if _check_airtable():
        try:
            table = _tbl("Trailer Cache")
            existing = table.all(formula=f"{{Movie ID}}='{movie_id}'")
            data = {
                "Movie ID": str(movie_id),
                "Trailer URL": trailer_url,
                "Cached At": now_iso(),
            }
            if existing:
                table.update(existing[0]["id"], data)
            else:
                table.create(data)
        except Exception as e:
            log_error("", "airtable.set_trailer_cache", "", "airtable_write_failed", str(e), raw_payload={"movie_id": movie_id, "trailer_url": trailer_url})
