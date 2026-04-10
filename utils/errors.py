from typing import Optional, Dict, Any

class MovieBotError(Exception):
    """Base exception for the Movie Bot."""
    def __init__(self, message: str, category: str = "internal_error", raw_payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.category = category
        self.raw_payload = raw_payload

class UserError(MovieBotError):
    """Errors that should be shown to the user in a safe way."""
    def __init__(self, message: str, raw_payload: Optional[Dict[str, Any]] = None):
        super().__init__(message, category="user_error", raw_payload=raw_payload)

class ProviderError(MovieBotError):
    """Errors from external providers (Perplexity, OMDb, etc.)."""
    def __init__(self, message: str, provider: str, is_transient: bool = True, raw_payload: Optional[Dict[str, Any]] = None):
        category = "transient_provider_error" if is_transient else "degraded_service_error"
        super().__init__(message, category=category, raw_payload=raw_payload)
        self.provider = provider

class DuplicateUpdateError(MovieBotError):
    """Error for duplicate Telegram updates."""
    def __init__(self, update_id: str):
        super().__init__(f"Duplicate update: {update_id}", category="duplicate_update")
        self.update_id = update_id

class RateLimitError(MovieBotError):
    """Error for user rate limiting."""
    def __init__(self, chat_id: str):
        super().__init__(f"User {chat_id} is rate limited", category="rate_limit")
        self.chat_id = chat_id

def get_user_safe_message(error: MovieBotError) -> str:
    """Map internal error categories to user-friendly messages."""
    messages = {
        "user_error": str(error),
        "transient_provider_error": "🎬 I'm having a brief moment of trouble reaching my movie databases. Please try in a few seconds.",
        "degraded_service_error": "⚙️ Part of my recommendation engine is offline right now, but I can still help with basic lookups.",
        "internal_error": "⚠️ I hit an unexpected snag. Please try again or use /reset to start over.",
        "rate_limit": "🐢 You're moving a bit fast! Please wait a moment before your next request.",
        "duplicate_update": "" # Silent recovery
    }
    return messages.get(error.category, messages["internal_error"])
