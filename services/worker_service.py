import sys
from intent_handler import (
    handle_start, handle_reset, handle_movie,
    handle_history, handle_watchlist, handle_watched,
    handle_like, handle_dislike, handle_save,
    handle_more_like, handle_trending, handle_surprise,
    handle_questioning, handle_fallback,
    handle_admin_health, handle_admin_stats, handle_admin_errors,
    handle_admin_clear_cache, handle_admin_disable_provider, handle_admin_enable_provider
)

# Dispatcher for background tasks
INTENT_HANDLERS = {
    "start": handle_start,
    "reset": handle_reset,
    "movie": handle_movie,
    "movie_prompt": handle_movie,
    "history": handle_history,
    "watchlist": handle_watchlist,
    "watched": handle_watched,
    "like": handle_like,
    "dislike": handle_dislike,
    "save": handle_save,
    "more_like": handle_more_like,
    "trending": handle_trending,
    "surprise": handle_surprise,
    "questioning": handle_questioning,
    "admin_health": handle_admin_health,
    "admin_stats": handle_admin_stats,
    "admin_errors": handle_admin_errors,
    "admin_clear_cache": handle_admin_clear_cache,
    "admin_disable_provider": handle_admin_disable_provider,
    "admin_enable_provider": handle_admin_enable_provider,
    "fallback": handle_fallback,
    "help": lambda chat_id, text: handle_fallback(chat_id, "/help") # Help is actually a static text
}

def log_interaction(chat_id: str, username: str, input_text: str, intent: str):
    try:
        from supabase_client import insert_rows, is_configured
        if is_configured():
            import threading
            from datetime import datetime
            
            payload = {
                "chat_id": str(chat_id),
                "username": username or "",
                "input_text": input_text or "",
                "intent": intent or "",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            def _bg_log():
                try:
                    insert_rows("user_interactions", [payload])
                except Exception as e:
                    print(f"[Worker] Failed to log interaction: {e}")
                    
            threading.Thread(target=_bg_log, daemon=True).start()
    except Exception as e:
        print(f"[Worker] Error setting up interaction log: {e}")

def run_intent_job(intent: str, chat_id: str, username: str, input_text: str, session: dict, user: dict):
    """Entry point for the background worker to execute an intent."""
    log_interaction(chat_id, username, input_text, intent)
    
    handler = INTENT_HANDLERS.get(intent, handle_fallback)
    
    try:
        if intent in ("start", "movie", "movie_prompt", "more_like", "questioning"):
            handler(chat_id, input_text if intent != "start" else username, session, user)
        elif intent in ("trending", "surprise"):
            handler(chat_id, session, user)
        elif intent in ("like", "dislike", "save", "watched"):
            handler(chat_id, input_text, user)
        elif intent == "reset":
            handle_reset(chat_id, username)
        elif intent in ("history", "watchlist", "admin_health", "admin_errors", "admin_clear_cache"):
            handler(chat_id)
        elif intent == "admin_stats":
            handle_admin_stats(chat_id)
        elif intent in ("admin_disable_provider", "admin_enable_provider"):
             provider = input_text.split()[-1] if " " in input_text else "unknown"
             handler(chat_id, provider)
        elif intent == "help":
            from intent_handler import handle_help
            handle_help(chat_id)
        else:
            # Fallback signature: (chat_id, text)
            handler(chat_id, input_text)
            
    except Exception as e:
        print(f"[Worker] Error running {intent} for {chat_id}: {e}")
        import traceback; traceback.print_exc()
