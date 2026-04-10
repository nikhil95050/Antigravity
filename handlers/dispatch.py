from contextvars import ContextVar
from services.logging_service import interaction_context

from clients.telegram_helpers import (
    send_message, send_photo, build_movie_buttons, build_iteration_buttons, 
    build_pagination_keyboard
)
from .user_handlers import *
from .rec_handlers import *
from .callback_handlers import *
from .admin_handlers import *

INTENT_MAP = {
    "start": handle_start,
    "reset": handle_reset,
    "movie": handle_movie,
    "questioning": handle_questioning,
    "trending": handle_trending,
    "surprise": handle_surprise,
    "history": handle_history,
    "watchlist": handle_watchlist,
    "watched": handle_watched,
    "save": handle_save,
    "like": handle_like,
    "dislike": handle_dislike,
    "search": handle_search,
    "more_like": handle_more_like,
    "more_suggestions": handle_more_suggestions,
    "help": handle_help,
    "fallback": handle_fallback,
    "min_rating": handle_min_rating,
    "admin_health": handle_admin_health,
    "admin_stats": handle_admin_stats,
    "admin_clear_cache": handle_admin_clear_cache,
    "admin_errors": handle_admin_errors,
    "admin_usage": handle_admin_usage,
    "admin_broadcast": handle_admin_broadcast,
    "admin_broadcast_confirm": handle_admin_broadcast_confirm,
    "admin_broadcast_cancel": handle_admin_broadcast_cancel,
    "admin_disable_provider": handle_admin_disable_provider,
    "admin_enable_provider": handle_admin_enable_provider,
}

async def dispatch_intent(intent: str, **kwargs):
    """Orchestrates intent execution by routing to the appropriate handler."""
    chat_id = kwargs.get("chat_id")
    input_text = kwargs.get("text") or kwargs.get("input_text", "")

    # SEMANTIC INTERCEPTOR: If current intent is fallback, try to classify natural language
    if intent == "fallback" and len(input_text) > 3:
        from services.semantic_service import SemanticService
        classified_intent = await SemanticService.classify_intent(input_text, chat_id=str(chat_id))
        if classified_intent:
            intent = classified_intent

    handler = INTENT_MAP.get(intent)
    if not handler:
        await send_message(chat_id, "I'm not sure how to handle that. Try /help.")
        return

    # 1. Provide core abstractions from the container
    from config.supabase_client import is_configured as supabase_ready
    from services.container import session_service, user_service
    chat_id = kwargs.get("chat_id")
    
    # 2. Lazy load state (only if we have a chat_id)
    session = None
    user = None
    if chat_id:
        session = session_service.get_session(str(chat_id))
        user = user_service.get_user(str(chat_id))

    # 3. Call handler with required positional arguments
    # Standard handler signature: (chat_id, ..., session, user, **kwargs)
    if "text" in kwargs and "input_text" not in kwargs:
        kwargs["input_text"] = kwargs["text"]

    import time
    start_time = time.time()
    
    # Set context for interaction logging
    interaction_context.set({
        "chat_id": chat_id,
        "input_text": kwargs.get("input_text", ""),
        "intent": intent,
        "start_time": start_time,
        "user_sent_at": kwargs.get("user_sent_at")
    })

    try:
        if asyncio.iscoroutinefunction(handler):
            await handler(session=session, user=user, **kwargs)
        else:
            handler(session=session, user=user, **kwargs)
    except Exception as e:
        from services.logging_service import get_logger
        get_logger("dispatcher").exception(f"Handler error for intent '{intent}': {e}")
        
        # Notify User
        from utils.bot_utils import notify_user_of_error
        if chat_id:
            await notify_user_of_error(chat_id, error_context=intent)
