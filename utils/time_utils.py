from datetime import datetime

def utc_now_iso() -> str:
    """Returns current UTC time in ISO 8601 format with a 'Z' suffix."""
    return datetime.utcnow().isoformat() + "Z"
