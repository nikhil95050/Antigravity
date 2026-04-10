import os
import json
import time
from concurrent.futures import ThreadPoolExecutor
from redis import Redis
from services.worker_service import run_intent_job

# Import the actual functions that can be run
TASK_REGISTRY = {
    "run_intent_job": run_intent_job
}

# Configuration
REDIS_URL = os.environ.get("REDIS_URL")
redis_conn = Redis.from_url(REDIS_URL) if REDIS_URL else Redis()
QUEUE_NAME = "movie_bot_queue"

# Performance Tuning: Increase workers for IO-bound tasks on Windows
MAX_WORKERS = 8

def process_job(job_data):
    """Execution logic for a single job."""
    try:
        job = json.loads(job_data)
        func_name = job.get("func")
        args = job.get("args", [])
        kwargs = job.get("kwargs", {})
        
        print(f"[Worker] Processing job: {func_name}")
        
        handler = TASK_REGISTRY.get(func_name)
        if handler:
            handler(*args, **kwargs)
        else:
            print(f"[Worker] Error: No handler registered for {func_name}")
    except Exception as e:
        print(f"[Worker] Job execution error: {e}")

def start_worker():
    print(f"[Worker] Starting concurrent worker loop (Threads: {MAX_WORKERS}) on Windows. Listening on '{QUEUE_NAME}'...")
    
    # Use ThreadPoolExecutor to handle multiple enqueued jobs in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while True:
            try:
                # Block for up to 10 seconds waiting for a job
                result = redis_conn.blpop(QUEUE_NAME, timeout=10)
                if not result:
                    continue
                
                _, job_data = result
                # Submit job to the pool and continue polling for more
                executor.submit(process_job, job_data)
                
            except Exception as e:
                print(f"[Worker] Error in polling loop: {e}")
                time.sleep(1)

if __name__ == "__main__":
    start_worker()
