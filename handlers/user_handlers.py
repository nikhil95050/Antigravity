from services.container import session_service, user_service, movie_service, rec_service
from clients.telegram_helpers import (
    send_message, edit_message, format_history_list, format_watchlist_list, build_pagination_keyboard
)
from .common import _get_page, _process_and_send_recs
from services.recommendation_engine import QUESTIONS

async def handle_start(chat_id, username, session, user, **kwargs):
    session_service.reset_session(chat_id)
    user_service.upsert_user(chat_id, username)
    new_session = {"session_state": "questioning", "question_index": 0}
    session_service.upsert_session(chat_id, new_session)
    
    welcome = (
        f"<b>Hey there, {username or 'Movie Fan'}! 👋</b>\n\n"
        "I'm CineMate, your personal guide to the world of cinema. "
        "I live and breathe movies, and I'd love to help you find your next favorite film.\n\n"
        "To get started, I've got a few quick questions to help me understand your vibe today. Ready?"
    )
    await send_message(chat_id, welcome)
    from .rec_handlers import _send_current_question
    await _send_current_question(chat_id, new_session)

async def handle_reset(chat_id, username, **kwargs):
    session_service.reset_session(chat_id)
    await send_message(chat_id, f"No worries, {username}! I've cleared the slate. Whenever you're ready for a fresh start, just type /start and we'll dive back in. 🍿")

async def handle_help(chat_id, **kwargs):
    help_text = (
        "<b>🎬 CineMate's Guide: How to Find Your Next Favorite Movie</b>\n\n"
        "I'm here to make discovery fun! Here's how you can talk to me:\n\n"
        "🌟 /start - Let's go on a personalized movie journey\n"
        "🔍 /search - Tell me anything! (e.g. <i>'gritty 90s thrillers'</i>)\n"
        "🎬 /movie - Found something you liked? I'll find its cinematic twins\n"
        "🔥 /trending - What the world is raving about right now\n"
        "🎲 /surprise - Feeling brave? Let me pick a hidden gem for you\n\n"
        "🗂 /history - Revisit our past discoveries\n"
        "📂 /watchlist - Your private collection of 'must-see' titles\n"
        "📺 /subscriptions - Manage your streaming services\n"
        "🔄 /reset - Start with a clean slate"
    )
    await send_message(chat_id, help_text)

async def handle_history(chat_id, input_text, **kwargs):
    page = _get_page(input_text)
    history = movie_service.get_history(chat_id, limit=11, offset=(page-1)*10)
    has_more = len(history) > 10
    display_list = history[:10]
    
    markup = build_pagination_keyboard("history_", page, has_more)
    text = format_history_list(display_list, page)
    
    if "p" in input_text:
        await edit_message(chat_id, kwargs.get("message_id"), text, markup)
    else:
        intro = "<b>🎬 Your Cinematic Journey So Far</b>\nHere's everything we've discovered together:"
        await send_message(chat_id, intro)
        await send_message(chat_id, text, markup)

async def handle_watchlist(chat_id, input_text, **kwargs):
    page = _get_page(input_text)
    wl = movie_service.get_watchlist(chat_id, limit=11, offset=(page-1)*10)
    has_more = len(wl) > 10
    display_list = wl[:10]
    
    markup = build_pagination_keyboard("watchlist_", page, has_more)
    text = format_watchlist_list(display_list, page)
    
    if "p" in input_text:
        await edit_message(chat_id, kwargs.get("message_id"), text, markup)
    else:
        intro = "<b>📂 Your Private Collection</b>\nHere are the gems you've saved for later. Better get some popcorn ready!"
        await send_message(chat_id, intro)
        await send_message(chat_id, text, markup)

async def handle_search(chat_id, input_text, session, user, **kwargs):
    parts = input_text.split(None, 1)
    if len(parts) < 2:
        await send_message(chat_id, "I'm all ears! Tell me what you're in the mood for. \nExample: <code>/search mind-bending sci-fi with robots</code>")
        return
    query = parts[1].strip()
    await send_message(chat_id, f"🔍 <b>Searching the archives for '{query}'...</b>")
    full_list = await rec_service.get_recommendations(session, user, mode="similarity", seed_title=query)
    await _process_and_send_recs(chat_id, session, full_list, f"I've found some fascinating matches for <b>{query}</b>:")

async def handle_min_rating(chat_id, input_text, **kwargs):
    parts = input_text.split()
    if len(parts) < 2:
        await send_message(chat_id, "Set your minimum quality bar! 🎭\nExample: <code>/rating 7.5</code> (Only shows movies with 7.5+ IMDb rating)")
        return
    
    try:
        val = float(parts[1])
        if not (0 <= val <= 10): raise ValueError()
    except (ValueError, TypeError):
        await send_message(chat_id, "Please provide a valid rating between 0 and 10.")
        return
        
    user_service.update_preferences(chat_id, {"avg_rating_preference": val})
    await send_message(chat_id, f"✅ Done! I'll now only recommend cinematic masterpieces with a rating of <b>{val}+</b>.")

async def handle_fallback(chat_id, **kwargs):
    await send_message(chat_id, "Hmm, I didn't quite catch that. I'm still learning! Try /help to see all the ways I can help you find great movies. 🎬")
