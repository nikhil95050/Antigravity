import os
import threading
import time
from uuid import uuid4
from datetime import datetime

from flask import Flask, request, jsonify

from telegram_helpers import set_webhook, answer_callback_query, send_message
from services.session_service import SessionService
from services.user_service import UserService
from services.queue_service import enqueue_job
from services.worker_service import run_intent_job
from intent_handler import normalize_input, detect_intent
from app_config import get_startup_readiness
from redis_cache import mark_processed_update, is_rate_limited
from errors import MovieBotError, DuplicateUpdateError, get_user_safe_message
from repositories.admin_repository import AdminRepository

# Initialize services
session_service = SessionService()
user_service = UserService()
admin_repo = AdminRepository()

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SECRET_PATH = f"/webhook/{TELEGRAM_BOT_TOKEN}"

# Cache for admin IDs to keep webhook fast
ADMIN_CACHE = {"1878846631"} 
_metrics_lock = threading.Lock()
_runtime_metrics = {
    "updates_processed": 0,
    "callbacks_answered": 0,
    "user_error_messages": 0,
    "unhandled_exceptions": 0,
    "admin_denied": 0,
    "duplicate_updates": 0,
    "rate_limited": 0,
    "jobs_enqueued": 0
}

def _metric_inc(key: str):
    with _metrics_lock:
        _runtime_metrics[key] = _runtime_metrics.get(key, 0) + 1

def _is_admin(chat_id) -> bool:
    cid = str(chat_id or "")
    if cid in ADMIN_CACHE:
        return True
    # Periodic refresh of admin cache? For now, the intent_handler check is authoritative.
    # We do a fast check here, and intent_handler does the secure one.
    return cid == "1878846631"

def _background_tasks():
    """Background loop for log cleanup and cache refreshes."""
    print("[Main] Background task worker started.")
    while True:
        try:
            # 1. Cleanup logs older than 7 days (as requested)
            admin_repo.cleanup_old_logs(days=7)
            
            # 2. Refresh admin cache (in a real app, do this less frequently than every sleep)
            # For simplicity, we keep it static for now as intent_handler handles security.
            
            # Sleep for 24 hours
            time.sleep(86400)
        except Exception as e:
            print(f"[Main] Error in background tasks: {e}")
            time.sleep(3600)

def process_update(update: dict):
    request_id = uuid4().hex[:10]
    try:
        update_id = update.get("update_id")
        if update_id and not mark_processed_update(str(update_id)):
            _metric_inc("duplicate_updates")
            raise DuplicateUpdateError(str(update_id))

        normalized = normalize_input(update)
        chat_id = normalized["chat_id"]
        if not chat_id: return

        if normalized["action_type"] == "callback" and normalized["callback_query_id"]:
            if answer_callback_query(normalized["callback_query_id"], chat_id=chat_id):
                _metric_inc("callbacks_answered")

        if is_rate_limited(f"rate:{chat_id}", limit=12, window_seconds=60):
            _metric_inc("rate_limited")
            send_message(chat_id, "You're moving a bit fast! Please wait a moment.")
            return

        session = session_service.get_session(chat_id)
        user = user_service.get_user(chat_id)
        
        intent = detect_intent(normalized["input_text"], session)
        
        # Phase 3: Quick ACK - Enqueue the heavy work
        enqueue_job(
            "run_intent_job",
            intent=intent,
            chat_id=chat_id,
            username=normalized["username"],
            input_text=normalized["input_text"],
            session=session,
            user=user
        )
        _metric_inc("jobs_enqueued")
        _metric_inc("updates_processed")

    except DuplicateUpdateError:
        pass
    except Exception as e:
        _metric_inc("unhandled_exceptions")
        import traceback; traceback.print_exc()

@app.route(SECRET_PATH, methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        if not update: return jsonify({"ok": False}), 400
        process_update(update)
        return jsonify({"ok": True}), 200
    except Exception:
        return jsonify({"ok": False}), 500

@app.route("/health", methods=["GET"])
def health():
    with _metrics_lock: stats = dict(_runtime_metrics)
    return jsonify({"status": "ok", "metrics": stats})

if __name__ == "__main__":
    # Start background cleanup thread
    threading.Thread(target=_background_tasks, daemon=True).start()
    
    port = int(os.environ.get("PORT", 5000))
    print(f"[Bot] Webhook listener starting on {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
