import json
import time
from config.redis_cache import get_redis
from services.logging_service import get_logger

logger = get_logger("queue")

QUEUE_NAME = "movie_bot_queue"


def enqueue_job(func_name: str, *args, **kwargs):
    """Push a job onto the Redis queue."""
    client = get_redis()
    if not client:
        # Redis unavailable — run inline as a last-resort fallback
        logger.warning(f"[Queue] ⚠️  Redis unavailable. Running '{func_name}' inline (no queue).")
        from services.worker_service import run_intent_job
        if func_name == "run_intent_job":
            try:
                run_intent_job(*args, **kwargs)
            except Exception as e:
                logger.error(f"[Queue] Inline fallback error: {e}")
        return

    job = {
        "func": func_name,
        "args": args,
        "kwargs": kwargs,
        "enqueued_at": time.time(),
    }
    try:
        client.rpush(QUEUE_NAME, json.dumps(job))
        print(f"[Queue] Enqueued: {func_name}")
    except Exception as e:
        print(f"[Queue] ❌ Enqueue failed for '{func_name}': {e}")