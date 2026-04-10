import os
import json
import time
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from config.redis_cache import get_redis  # ← single shared, validated connection
from services.worker_service import run_intent_job

load_dotenv()

TASK_REGISTRY = {
    "run_intent_job": run_intent_job,
}

QUEUE_NAME = "movie_bot_queue"
MAX_WORKERS = int(os.environ.get("WORKER_THREADS", "8"))

_shutdown = threading.Event()


from services.logging_service import get_logger, LoggingService
logger = get_logger("worker")

def _handle_sigterm(signum, frame):
    logger.info("SIGTERM received — draining queue and shutting down...")
    _shutdown.set()

signal.signal(signal.SIGTERM, _handle_sigterm)

def process_job(job_data):
    request_id = "worker_" + os.urandom(4).hex()
    try:
        job = json.loads(job_data)
        func_name = job.get("func")
        args = job.get("args", [])
        kwargs = job.get("kwargs", {})
        
        logger.info(f"Processing job: {func_name}", extra={"func": func_name})
        handler = TASK_REGISTRY.get(func_name)
        
        if handler:
            # Use profiler for background jobs
            with LoggingService.profile_context(func_name):
                handler(*args, **kwargs)
        else:
            logger.error(f"No handler for '{func_name}'")
    except Exception as e:
        logger.exception(f"Job execution error: {e}")
        # Notify user in background if chat_id exists in job
        job_json = json.loads(job_data)
        chat_id = job_json.get("kwargs", {}).get("chat_id")
        if chat_id:
            from utils.bot_utils import notify_user_of_error
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(notify_user_of_error(chat_id))

def start_worker():
    client = get_redis()
    if not client:
        logger.critical("Cannot start worker — Redis is not connected. Check REDIS_URL.")
        return

    logger.info(f"Worker starting with {MAX_WORKERS} threads. Listening on '{QUEUE_NAME}'...")
    from services.logging_service import interaction_batcher, error_batcher

    # Add SIGINT for local development (Ctrl+C)
    signal.signal(signal.SIGINT, _handle_sigterm)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while not _shutdown.is_set():
            try:
                result = client.blpop(QUEUE_NAME, timeout=5)
                if result:
                    _, job_data = result
                    executor.submit(process_job, job_data)
            except Exception as e:
                # Re-check shutdown flag on connection error
                if not _shutdown.is_set():
                    logger.error(f"Poll error: {e}")
                    time.sleep(1)

        logger.info("Draining active jobs...")
        executor.shutdown(wait=True)
    
    logger.info("Flushing final logs...")
    interaction_batcher.shutdown()
    error_batcher.shutdown()
    logger.info("Worker shutdown complete.")


if __name__ == "__main__":
    start_worker()