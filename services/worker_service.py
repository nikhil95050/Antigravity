import sys
import time
import asyncio
from intent_handler import dispatch_intent
from services.logging_service import LoggingService
from utils.time_utils import utc_now_iso


def log_interaction(chat_id: str, username: str, input_text: str, intent: str, request_id: str):
    """
    Logs user interaction via BatchLogger.
    """
    from datetime import datetime
    from services.logging_service import interaction_batcher
    
    payload = {
        "chat_id":    str(chat_id),
        "username":   username or "",
        "input_text": input_text or "",
        "intent":     intent or "",
        "request_id": request_id, 
        "timestamp":  utc_now_iso(),
    }
    interaction_batcher.emit(payload)
    _cache_recent_interaction(chat_id, intent, input_text)

def _cache_recent_interaction(chat_id, intent, input_text):
    """Keep last 10 interactions per user in Redis for fast admin lookup."""
    from config.redis_cache import get_redis, set_json
    client = get_redis()
    if client:
        try:
            key = f"recent_interactions:{chat_id}"
            import json
            client.lpush(key, json.dumps({
                "intent": intent, 
                "text": input_text, 
                "timestamp": time.time()
            }))
            client.ltrim(key, 0, 9)
            client.expire(key, 86400)
        except:
            pass


def run_intent_job(
    intent: str,
    chat_id: str,
    username: str,
    input_text: str,
    session: dict,
    user: dict,
    request_id: str = "N/A",
    callback_query_id: str = None,
    message_id: int = None,
):
    """Entry point for the background worker to execute an intent."""
    start_time = time.time()
    log_interaction(chat_id, username, input_text, intent, request_id)

    status = "success"
    err_msg = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    coro = dispatch_intent(
        intent=intent,
        chat_id=chat_id,
        username=username,
        input_text=input_text,
        session=session,
        user=user,
        request_id=request_id,
        callback_query_id=callback_query_id,
        message_id=message_id,
    )

    try:
        if loop and loop.is_running():
            # Already in a loop (e.g. fallback from enqueue_job)
            loop.create_task(coro)
        else:
            asyncio.run(coro)
        LoggingService.log_event(chat_id, intent, "completed", request_id)

    except Exception as e:
        status = "error"
        err_msg = str(e)
        LoggingService.log_event(
            chat_id, intent, "failed", request_id,
            status="error", error_type="worker_crash",
            extra={"error_message": err_msg}
        )
    finally:
        latency = int((time.time() - start_time) * 1000)
        _update_interaction_bg(request_id, status, latency, err_msg)


def _update_interaction_bg(request_id: str, status: str, latency: int, error: str = None):
    """Update the interaction log in a background thread."""
    if request_id == "N/A":
        return

    from config.supabase_client import update_rows, is_configured
    if not is_configured():
        return

    import threading
    def _do_update():
        payload = {
            "response_status": status,
            "latency_ms": latency,
            "error_message": error or ""
        }
        try:
            update_rows("user_interactions", payload, {"request_id": request_id})
        except:
            pass

    threading.Thread(target=_do_update, daemon=True).start()