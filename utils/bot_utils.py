import asyncio
from clients.telegram_helpers import send_message
from services.logging_service import get_logger

logger = get_logger("bot_utils")

async def notify_user_of_error(chat_id: str, error_context: str = "generic"):
    """
    Sends a friendly, human-like error notification to the user.
    Used for both foreground and background failures.
    """
    error_messages = {
        "generic": "I'm sorry, I hit a snag while processing that! 🧐 Please try again in a moment.",
        "discovery": "My cinematic sensors are a bit fuzzy right now! 🎬 I couldn't quite find those movies, but let's try another search?",
        "streaming": "I found the movies, but I'm having trouble checking the streaming links! 📺 Give me a second to reboot my connection.",
        "admin": "CineMate's internal controls are acting up. I'll notify the technician! 🛠️"
    }
    
    msg = error_messages.get(error_context, error_messages["generic"])
    try:
        await send_message(chat_id, f"<b>Whoops!</b>\n{msg}")
    except Exception as e:
        logger.error(f"Failed to send error notification to {chat_id}: {e}")
