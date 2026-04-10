import os
import asyncio
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from config.app_config import load_config, get_config
from config.redis_cache import get_redis, validate_redis_connection
from clients.telegram_helpers import (
    BASE_URL, send_message, set_webhook, delete_webhook, build_iteration_buttons
)
from handlers.dispatch import dispatch_intent
from handlers.normalizer import normalize_input, detect_intent

# Services are imported from container
from services.container import (
    container, 
    session_service, 
    user_service, 
    movie_service, 
    admin_repo
)

# Setup Logger
logger = get_logger("main")

# Early Configuration Validation
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN is not set. Bot cannot start.")
    exit(1)

# In-memory metrics for /health
_metrics = {
    "updates_processed": 0,
    "callbacks_answered": 0,
    "user_error_messages": 0,
    "unhandled_exceptions": 0,
    "rate_limited": 0,
    "jobs_enqueued": 0
}

def _metric_inc(key: str):
    _metrics[key] = _metrics.get(key, 0) + 1

async def cleanup_loop():
    """Asynchronous background loop for database cleanup."""
    logger.info("Background cleanup loop started.")
    while True:
        try:
            admin_repo.cleanup_old_logs(days=7)
            logger.info("Scheduled cleanup of old logs completed.")
            await asyncio.sleep(86400) # Sleep for 24h
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}")
            await asyncio.sleep(3600)

async def prewarm_popular_caches():
    """Startup task to ensure hot data is available."""
    try:
        from services.container import discovery_service
        logger.info("Pre-warming Trending cache...")
        await discovery_service.get_trending_movies(limit=10)
        logger.info("Pre-warming complete.")
    except Exception as e:
        logger.warning(f"Pre-warming failed: {e}")

async def periodic_tasks_loop():
    """Weekly/Daily background jobs for engagement."""
    from services.container import discovery_service
    from handlers.common import send_movies_async
    from config.supabase_client import select_rows

    while True:
        try:
            now = datetime.utcnow()
            # 1. Weekly Trending Digest (Mondays at 10 AM UTC)
            if now.weekday() == 0 and now.hour == 10:
                from config.redis_cache import get_redis
                redis_client = get_redis()
                week_key = f"weekly_digest_sent:{now.strftime('%Y-%W')}"
                
                if redis_client and not redis_client.get(week_key):
                    logger.info("Executing Weekly Trending Digest...")
                    movies = await discovery_service.get_weekly_trending_digest()
                    if movies:
                        users, _ = select_rows("users", {}, limit=5000)
                        for u in (users or []):
                            chat_id = u.get("chat_id")
                            if chat_id:
                                await send_movies_async(chat_id, movies, "🔥 <b>Weekly Trending Digest:</b>")
                        
                        # Mark as sent for this week
                        redis_client.set(week_key, "1", ex=604800) # 7 days
                
                await asyncio.sleep(3600) # Prevents re-triggering within the same hour

            # 2. Daily Watchlist Reminder (Daily at 6 PM UTC)
            if now.hour == 18:
                logger.info("Executing Daily Watchlist Reminders...")
                users, _ = select_rows("users", {}, limit=5000)
                for u in (users or []):
                    chat_id = u.get("chat_id")
                    if chat_id:
                        movie = movie_service.get_random_watchlist_reminder(chat_id)
                        if movie:
                            await send_message(chat_id, "🍿 <b>Don't forget this gem in your watchlist:</b>")
                            await send_movies_async(chat_id, [movie])
                await asyncio.sleep(3600)

            await asyncio.sleep(600) # Check every 10 mins
        except Exception as e:
            logger.error(f"Error in periodic loop: {e}")
            await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("🎬 Movie Bot starting up...")
    asyncio.create_task(cleanup_loop())
    asyncio.create_task(periodic_tasks_loop())
    asyncio.create_task(prewarm_popular_caches())
    
    logger.info("Bot API started and ready.")
    yield
    
    # Shutdown
    logger.info("Bot API shutting down...")
    await container.teardown()
    logger.info("Bot API shutdown complete.")

app = FastAPI(title="Movie Bot API", lifespan=lifespan)

async def process_update_async(update: dict):
    request_id = uuid4().hex[:10]
    try:
        update_id = update.get("update_id")
        if update_id and not mark_processed_update(str(update_id)):
            _metric_inc("duplicate_updates")
            return

        normalized = normalize_input(update)
        chat_id = normalized["chat_id"]
        if not chat_id: return

        if normalized["action_type"] == "callback" and normalized["callback_query_id"]:
            if answer_callback_query(normalized["callback_query_id"], chat_id=chat_id):
                _metric_inc("callbacks_answered")

        session = session_service.get_session(chat_id)
        user = user_service.get_user(chat_id)
        
        # Determine user tier for rate limiting
        user_tier = "user"
        if admin_repo.is_admin(str(chat_id)):
            user_tier = "admin"
        elif user.get("vip"):
            user_tier = "vip"

        if is_rate_limited(f"rate:{chat_id}", limit=12, window_seconds=60, user_tier=user_tier):
            _metric_inc("rate_limited")
            send_message(chat_id, "You're moving a bit fast! Please wait a moment.")
            return

        intent = detect_intent(normalized["input_text"], session)
        
        # Log incoming intent
        LoggingService.log_event(chat_id, intent, "received", request_id)

        # Offload heavy work
        enqueue_job(
            "run_intent_job",
            intent=intent,
            chat_id=chat_id,
            username=normalized["username"],
            input_text=normalized["input_text"],
            session=session,
            user=user,
            request_id=request_id,
            callback_query_id=normalized.get("callback_query_id"),
            message_id=normalized.get("message_id"),
            user_sent_at=normalized.get("sent_at")
        )
        _metric_inc("jobs_enqueued")
        _metric_inc("updates_processed")

    except Exception as e:
        _metric_inc("unhandled_exceptions")
        logger.exception(f"Unexpected error processing update {request_id}: {e}")

@app.post(f"/webhook/{TELEGRAM_BOT_TOKEN}")
async def webhook(update: Dict[str, Any], background_tasks: BackgroundTasks):
    background_tasks.add_task(process_update_async, update)
    return {"ok": True}

@app.get("/health")
async def health():
    from config.supabase_client import is_configured as supabase_configured
    from config.redis_cache import is_connected as redis_connected
    
    return {
        "status": "ok", 
        "timestamp": datetime.utcnow().isoformat(),
        "infrastructure": {
            "supabase_ready": supabase_configured(),
            "redis_connected": redis_connected()
        },
        "metrics": _metrics
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
