import os
import json
import time
from redis import Redis

# Configuration
REDIS_URL = os.environ.get("REDIS_URL")
redis_conn = Redis.from_url(REDIS_URL) if REDIS_URL else Redis()
QUEUE_NAME = "movie_bot_queue"

def enqueue_job(func_name, *args, **kwargs):
    """Enqueue a job by its function name as a string."""
    job = {
        "func": func_name,
        "args": args,
        "kwargs": kwargs,
        "enqueued_at": time.time()
    }
    redis_conn.rpush(QUEUE_NAME, json.dumps(job))
    print(f"[Queue] Enqueued: {func_name}")
