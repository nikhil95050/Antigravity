"""
In-memory session store used as primary fast cache.
Falls back to Airtable for persistence when available.
"""
import threading
from datetime import datetime

_lock = threading.Lock()
_sessions = {}
_users = {}

def now_iso():
    return datetime.utcnow().isoformat()

# ─── In-Memory Session ─────────────────────────────────────────────────────────

def mem_get_session(chat_id):
    with _lock:
        return dict(_sessions.get(str(chat_id), {}))

def mem_set_session(chat_id, data: dict):
    cid = str(chat_id)
    with _lock:
        existing = _sessions.get(cid, {})
        existing.update(data)
        existing["chat_id"] = cid
        _sessions[cid] = existing

def mem_reset_session(chat_id):
    cid = str(chat_id)
    with _lock:
        _sessions[cid] = {
            "chat_id": cid,
            "session_state": "idle",
            "question_index": 0,
            "pending_question": "",
            "answers_mood": "",
            "answers_genre": "",
            "answers_language": "",
            "answers_era": "",
            "answers_context": "",
            "answers_avoid": "",
            "last_recs_json": "[]",
            "sim_depth": 0,
            "last_active": now_iso(),
            "updated_at": now_iso(),
        }

# ─── In-Memory User ────────────────────────────────────────────────────────────

def mem_get_user(chat_id):
    with _lock:
        return dict(_users.get(str(chat_id), {}))

def mem_set_user(chat_id, username, patch: dict = None):
    cid = str(chat_id)
    with _lock:
        existing = _users.get(cid, {"chat_id": cid, "username": username or ""})
        if patch:
            existing.update(patch)
        existing["updated_at"] = now_iso()
        _users[cid] = existing

def mem_session_count():
    with _lock:
        return len(_sessions)

def mem_user_count():
    with _lock:
        return len(_users)
