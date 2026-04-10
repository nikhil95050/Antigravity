from services.container import movie_service, user_service, feedback_repo
from clients.telegram_helpers import answer_callback_query, edit_message
from .common import _get_last_recs, _find_movie_in_recs

async def handle_watched(chat_id, input_text, **kwargs):
    movie_id = input_text.replace("watched_", "", 1)
    movie_service.mark_watched(chat_id, movie_id)
    await answer_callback_query(kwargs.get("callback_query_id", ""), "Nice! Ticked off the list. ✅")

async def handle_save(chat_id, input_text, session, **kwargs):
    movie_id = input_text.replace("save_", "", 1)
    movie = _find_movie_in_recs(_get_last_recs(session), movie_id)
    if movie:
        movie_service.add_to_watchlist(chat_id, movie)
        await answer_callback_query(kwargs.get("callback_query_id", ""), "Great choice! I've tucked it into your watchlist. 📂")
    else:
        movie = movie_service.get_movie_from_history(chat_id, movie_id)
        if movie:
            movie_service.add_to_watchlist(chat_id, movie)
            await answer_callback_query(kwargs.get("callback_query_id", ""), "Moved from history to your watchlist! 📂")
        else:
            await answer_callback_query(kwargs.get("callback_query_id", ""), "Hmm, I couldn't find that one to save. Try again?")

async def handle_like(chat_id, input_text, session, **kwargs):
    movie_id = input_text.replace("like_", "", 1)
    feedback_repo.log_reaction(chat_id, movie_id, "like")
    
    # Trigger Profile Update in background
    import asyncio
    asyncio.create_task(user_service.recompute_taste_profile(chat_id))
    
    await answer_callback_query(kwargs.get("callback_query_id", ""), "Excellent taste! I'm taking notes... 👍")

async def handle_dislike(chat_id, input_text, session, **kwargs):
    movie_id = input_text.replace("dislike_", "", 1)
    feedback_repo.log_reaction(chat_id, movie_id, "dislike")
    
    movie = _find_movie_in_recs(_get_last_recs(session), movie_id)
    if movie and movie.get("genres"):
        user_service.add_preference(chat_id, movie["genres"], liked=False)
        
    await answer_callback_query(kwargs.get("callback_query_id", ""), "Got it. I'll steer clear of those vibes in the future. 🚫")
