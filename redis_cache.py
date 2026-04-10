import os
import json
import time
import threading
import requests

# Configuration
REDIS_REST_URL = (
    os.environ.get("REDIS_REST_URL", "").strip()
    or os.environ.get("UPSTASH_REDIS_REST_URL", "").strip()
)
# Use REDIS_API_KEY as the token if available
REDIS_REST_TOKEN = (
    os.environ.get("REDIS_REST_TOKEN", "").strip()
    or os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()
    or os.environ.get("REDIS_API_KEY", "").strip()
)

_local_cache = {}
_local_lock = threading.Lock()

def is_configured() -> bool:
    # If the URL looks like a REST URL (starts with http), we consider it configured
    return bool(REDIS_REST_URL and REDIS_REST_URL.startswith("http") and REDIS_REST_TOKEN)

def _execute_command(command: list):
    """Executes a Redis command via the Upstash REST API."""
    if not is_configured():
        return None
    
    try:
        url = REDIS_REST_URL.rstrip("/")
        headers = {"Authorization": f"Bearer {REDIS_REST_TOKEN}"}
        resp = requests.post(url, json=command, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("result")
    except Exception as e:
        print(f"[Redis] Error executing command {command[0]}: {e}")
    return None

def get_json(key: str):
    """Fetches a JSON-decoded value from Redis or local cache."""
    # Try local cache first (short-lived)
    with _local_lock:
        item = _local_cache.get(key)
        if item:
            val, expiry = item
            if expiry is None or expiry > time.time():
                return val
            else:
                del _local_cache[key]

    if not is_configured():
        return None

    # Try Redis
    result = _execute_command(["GET", key])
    if result:
        try:
            data = json.loads(result)
            # Update local cache
            with _local_lock:
                _local_cache[key] = (data, time.time() + 60) # Cache locally for 60s
            return data
        except Exception:
            return result
    return None

def set_json(key: str, value, ttl: int = None):
    """Sets a value in Redis and local cache."""
    with _local_lock:
        expiry = time.time() + ttl if ttl else None
        _local_cache[key] = (value, expiry)

    if not is_configured():
        return

    val_str = json.dumps(value, ensure_ascii=False)
    if ttl:
        _execute_command(["SET", key, val_str, "EX", str(ttl)])
    else:
        _execute_command(["SET", key, val_str])

def clear_local_cache():
    """Clears the local in-memory cache."""
    with _local_lock:
        _local_cache.clear()

def mark_processed_update(update_id: str) -> bool:
    """
    Returns True if this is the first time we see this update_id.
    Uses Redis INCR and EXPIRE to handle deduplication in a distributed environment.
    """
    key = f"processed_update:{update_id}"
    
    # Local fallback
    with _local_lock:
        if key in _local_cache:
            return False
        _local_cache[key] = (True, time.time() + 3600)
    
    if not is_configured():
        return True # Assume OK if not configured

    # Redis atomicity
    # We use a simple GET then SET approach if INCR is too complex for REST here,
    # but Upstash supports it.
    val = _execute_command(["SET", key, "1", "NX", "EX", "3600"])
    return val == "OK"

def is_rate_limited(key: str, limit: int = 10, window_seconds: int = 60) -> bool:
    """ Simple window-based rate limiter. """
    full_key = f"rate_limit:{key}"
    
    # Local fallback
    with _local_lock:
        val, expiry = _local_cache.get(full_key, (0, 0))
        if time.time() > expiry:
            _local_cache[full_key] = (1, time.time() + window_seconds)
            current = 1
        else:
            _local_cache[full_key] = (val + 1, expiry)
            current = val + 1
        
        if not is_configured():
            return current > limit

    # Redis version (Atomic)
    # Using Lua scripts or just INCR + EXPIRE
    # Simple version for REST:
    current_redis = _execute_command(["INCR", full_key])
    if current_redis == 1:
        _execute_command(["EXPIRE", full_key, str(window_seconds)])
    
    if current_redis is not None:
        return current_redis > limit
    
    return False # Default to not limited if Redis fails
