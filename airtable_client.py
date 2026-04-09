import os
import json
import time
from datetime import datetime
from pyairtable import Api

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")

_api = None

def get_api():
    global _api
    if _api is None:
        _api = Api(AIRTABLE_API_KEY)
    return _api

def get_table(table_name):
    return get_api().table(AIRTABLE_BASE_ID, table_name)

def now_iso():
    return datetime.utcnow().isoformat()

# ─── SESSIONS ──────────────────────────────────────────────────────────────────

def get_session(chat_id):
    try:
        table = get_table("sessions")
        records = table.all(formula=f"{{chat_id}}='{chat_id}'")
        if records:
            return records[0]["fields"]
        return None
    except Exception as e:
        print(f"[Airtable] get_session error: {e}")
        return None

def upsert_session(chat_id, patch: dict):
    try:
        table = get_table("sessions")
        records = table.all(formula=f"{{chat_id}}='{chat_id}'")
        patch["updated_at"] = now_iso()
        if records:
            record_id = records[0]["id"]
            table.update(record_id, patch)
        else:
            patch["chat_id"] = str(chat_id)
            table.create(patch)
    except Exception as e:
        print(f"[Airtable] upsert_session error: {e}")

def reset_session(chat_id):
    try:
        table = get_table("sessions")
        records = table.all(formula=f"{{chat_id}}='{chat_id}'")
        reset_data = {
            "chat_id": str(chat_id),
            "session_state": "idle",
            "question_index": 0,
            "pending_question": "",
            "answers_mood": "",
            "answers_genre": "",
            "answers_language": "",
            "answers_era": "",
            "answers_context": "",
            "answers_avoid": "",
            "last_recs_json": "",
            "sim_depth": 0,
            "last_active": now_iso(),
            "updated_at": now_iso(),
        }
        if records:
            table.update(records[0]["id"], reset_data)
        else:
            table.create(reset_data)
    except Exception as e:
        print(f"[Airtable] reset_session error: {e}")

# ─── USERS ──────────────────────────────────────────────────────────────────────

def get_user(chat_id):
    try:
        table = get_table("users")
        records = table.all(formula=f"{{chat_id}}='{chat_id}'")
        if records:
            return records[0]["fields"]
        return None
    except Exception as e:
        print(f"[Airtable] get_user error: {e}")
        return None

def upsert_user(chat_id, username, patch: dict = None):
    try:
        table = get_table("users")
        records = table.all(formula=f"{{chat_id}}='{chat_id}'")
        data = patch or {}
        data["updated_at"] = now_iso()
        if records:
            table.update(records[0]["id"], data)
        else:
            data["chat_id"] = str(chat_id)
            data["username"] = username or ""
            table.create(data)
    except Exception as e:
        print(f"[Airtable] upsert_user error: {e}")

# ─── HISTORY ────────────────────────────────────────────────────────────────────

def get_history(chat_id, limit=20):
    try:
        table = get_table("history")
        records = table.all(
            formula=f"{{chat_id}}='{chat_id}'",
            sort=[{"field": "recommended_at", "direction": "desc"}]
        )
        return [r["fields"] for r in records[:limit]]
    except Exception as e:
        print(f"[Airtable] get_history error: {e}")
        return []

def insert_history_rows(rows: list):
    try:
        table = get_table("history")
        for row in rows:
            row["recommended_at"] = now_iso()
            table.create(row)
    except Exception as e:
        print(f"[Airtable] insert_history error: {e}")

def update_history_watched(chat_id, movie_id, watched: bool = True):
    try:
        table = get_table("history")
        records = table.all(
            formula=f"AND({{chat_id}}='{chat_id}',{{movie_id}}='{movie_id}')"
        )
        if records:
            patch = {"watched": watched}
            if watched:
                patch["watched_at"] = now_iso()
            table.update(records[0]["id"], patch)
    except Exception as e:
        print(f"[Airtable] update_history_watched error: {e}")

def get_movie_from_history(chat_id, movie_id):
    try:
        table = get_table("history")
        records = table.all(
            formula=f"AND({{chat_id}}='{chat_id}',{{movie_id}}='{movie_id}')"
        )
        if records:
            return records[0]["fields"]
        return None
    except Exception as e:
        print(f"[Airtable] get_movie_from_history error: {e}")
        return None

# ─── WATCHLIST ───────────────────────────────────────────────────────────────────

def save_to_watchlist(chat_id, movie: dict):
    try:
        table = get_table("watchlist")
        movie_id = movie.get("movie_id", "")
        existing = table.all(
            formula=f"AND({{chat_id}}='{chat_id}',{{movie_id}}='{movie_id}')"
        )
        if not existing:
            table.create({
                "chat_id": str(chat_id),
                "movie_id": str(movie_id),
                "title": movie.get("title", ""),
                "year": str(movie.get("year", "")),
                "language": movie.get("language", ""),
                "rating": str(movie.get("rating", "")),
                "genres": movie.get("genres", ""),
            })
            return True
        return False
    except Exception as e:
        print(f"[Airtable] save_to_watchlist error: {e}")
        return False

# ─── TRAILER CACHE ───────────────────────────────────────────────────────────────

def get_trailer_cache(movie_id):
    try:
        table = get_table("trailer_cache")
        records = table.all(formula=f"{{movie_id}}='{movie_id}'")
        if records:
            return records[0]["fields"].get("trailer_url")
        return None
    except Exception as e:
        print(f"[Airtable] get_trailer_cache error: {e}")
        return None

def set_trailer_cache(movie_id, trailer_url):
    try:
        table = get_table("trailer_cache")
        existing = table.all(formula=f"{{movie_id}}='{movie_id}'")
        data = {
            "movie_id": str(movie_id),
            "trailer_url": trailer_url,
            "cached_at": now_iso(),
        }
        if existing:
            table.update(existing[0]["id"], data)
        else:
            table.create(data)
    except Exception as e:
        print(f"[Airtable] set_trailer_cache error: {e}")
