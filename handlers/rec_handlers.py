import json
from services.container import session_service, movie_service, rec_service
from clients.telegram_helpers import (
    send_message, build_question_keyboard, build_movie_buttons, 
    build_iteration_buttons, show_typing, build_pagination_keyboard
)
from .common import _process_and_send_recs, send_movies_async, _update_last_recs_and_history, _update_last_recs, _get_last_recs, _find_movie_in_recs
from services.recommendation_engine import QUESTIONS

async def handle_movie(chat_id, input_text, session, user, **kwargs):
    parts = input_text.strip().split(None, 1)
    if len(parts) < 2:
        await send_message(chat_id, "I'd love to find something similar for you! Just tell me a movie you enjoyed, like this: <code>/movie Inception</code>.")
        return
    title = parts[1].strip()
    
    from services.logging_service import LoggingService
    LoggingService.log_event(chat_id, "movie", "search_start", extra={"title": title})
    
    await send_message(chat_id, f"Ah, <b>{title}</b>! That's a great choice. Let me find some cinematic twins for you... 🎬")
    await show_typing(chat_id)
    movies = await rec_service.lookup_movie_context(title)
    if not movies:
        await send_message(chat_id, f"I couldn't find any direct matches for <b>{title}</b> in my archives, but why not try a broader /search?")
        return
    
    movie_service.add_to_history(chat_id, movies)
    _update_last_recs(chat_id, session, movies)
    await send_movies_async(chat_id, movies, f"If you liked <b>{title}</b>, I think these will be right up your alley:")

async def handle_trending(chat_id, session, user, **kwargs):
    await send_message(chat_id, "Scanning the global charts to see what everyone's raving about... 📈")
    await show_typing(chat_id)
    full_list = await rec_service.get_recommendations(session, user, mode="trending")
    await _process_and_send_recs(chat_id, session, full_list, "<b>Here's what's currently taking the world by storm:</b>")

async def handle_surprise(chat_id, session, user, **kwargs):
    await send_message(chat_id, "Feeling adventurous? Let's go off the beaten path... 🎲")
    await show_typing(chat_id)
    full_list = await rec_service.get_recommendations(session, user, mode="surprise")
    await _process_and_send_recs(chat_id, session, full_list, "<b>I've dug up these hidden treasures just for you:</b>")

async def handle_questioning(chat_id, input_text, session, user, **kwargs):
    idx = int((session or {}).get("question_index", 0))
    if idx >= len(QUESTIONS):
        await _finalize(chat_id, session)
        return
    
    current_key = QUESTIONS[idx][0]
    
    if input_text.startswith("q_skip_"):
        await _move_next(chat_id, session, idx, current_key, "[Skipped]")
    elif input_text.startswith("q_done_"):
        await _move_next(chat_id, session, idx, current_key, session.get(f"answers_{current_key}", ""))
    elif input_text.startswith(f"q_{current_key}_"):
        choice = input_text.replace(f"q_{current_key}_", "", 1)
        if current_key == "genre":
            current_ans = session.get("answers_genre", "")
            selected = [s.strip() for s in current_ans.split(",") if s.strip()]
            if choice in selected: selected.remove(choice)
            else: selected.append(choice)
            new_ans = ",".join(selected)
            session_service.upsert_session(chat_id, {"answers_genre": new_ans})
            session["answers_genre"] = new_ans 
            await _send_current_question(chat_id, session)
        else:
            await _move_next(chat_id, session, idx, current_key, choice)

async def handle_more_like(chat_id, input_text, session, user, **kwargs):
    movie_id = input_text.replace("more_like_", "", 1)
    movie = _find_movie_in_recs(_get_last_recs(session), movie_id)
    title = movie.get("title") if movie else None
    if title:
        await send_message(chat_id, f"I love that vibe! Finding more gems like <b>{title}</b>... 🎞")
        full_list = await rec_service.get_recommendations(session, user, mode="similarity", seed_title=title)
        await _process_and_send_recs(chat_id, session, full_list, f"Expanding on the greatness of <b>{title}</b>:")
    else:
        from telegram_helpers import answer_callback_query
        await answer_callback_query(kwargs.get("callback_query_id", ""), "Sorry, I lost the trail on that one. Try a new search?")

async def handle_more_suggestions(chat_id, session, user, **kwargs):
    buffer = json.loads(session.get("overflow_buffer_json", "[]"))
    if not buffer:
        await send_message(chat_id, "I've shown you everything I had in mind for this search! Ready for something /trending or a new /search?")
        return
    
    await send_message(chat_id, "Digging a little deeper into the collection... 📂")
    top_5 = buffer[:5]
    remaining = buffer[5:]
    
    enriched = await rec_service.enrich_movies(top_5, chat_id, "buffer_pull")
    _update_last_recs_and_history(chat_id, session, enriched)
    session_service.upsert_session(chat_id, {"overflow_buffer_json": json.dumps(remaining)})
    
    await send_movies_async(chat_id, enriched, "<b>Wait, there's more! Here are a few more fascinating picks:</b>", include_more=bool(remaining))

async def handle_star(chat_id, input_text, session, user, **kwargs):
    parts = input_text.strip().split(None, 1)
    if len(parts) < 2:
        await send_message(chat_id, "Who's your favorite star? Tell me their name and I'll find their best work! \nExample: <code>/star Leonardo DiCaprio</code>")
        return
    name = parts[1].strip()
    
    await send_message(chat_id, f"Oh, I love <b>{name}</b>! Let me scan the credits and find some of their standout performances for you... 🌟")
    await show_typing(chat_id)
    movies = await rec_service.discovery_service.get_star_movies(name, chat_id=chat_id)
    if not movies:
        await send_message(chat_id, f"I couldn't find a dedicated collection for <b>{name}</b>, but they've surely got some gems out there. Try a /search for one of their movies!")
        return
    
    movie_service.add_to_history(chat_id, movies)
    _update_last_recs(chat_id, session, movies)
    await send_movies_async(chat_id, movies, f"Here are some of <b>{name}'s</b> most fascinating cinematic moments:")

async def handle_share(chat_id, session, **kwargs):
    """Generate a shareable text card of the currently active recommendations."""
    recs = _get_last_recs(session)
    if not recs:
        await send_message(chat_id, "I don't have any active recommendations to share yet! Let's find some first with /start or /search. 🔍")
        return
        
    intro = "<b>🎬 My CineMate Discoveries!</b>\nCheck out these gems I found today:\n\n"
    lines = []
    for idx, m in enumerate(recs[:5], 1):
        line = f"🎥 <b>{m.get('title')}</b>"
        if m.get("reason"):
            line += f"\n   <i>\"{m.get('reason')}\"</i>"
        streaming = m.get("streaming")
        if streaming and "Loading" not in streaming and "Not currently available" not in streaming:
            line += f"\n   📺 {streaming}"
        lines.append(line)
        
    footer = "\n\n<i>Found with CineMate — your intelligent cinematic assistant.</i>"
    await send_message(chat_id, intro + "\n\n".join(lines) + footer)
    await send_message(chat_id, "There's your card! 👆 Feel free to forward this to your friends or copy the text. Happy watching! 🍿")

# ─── Internal Helpers ──────────────────────────────────────────────────────

async def _send_current_question(chat_id, session):
    idx = int((session or {}).get("question_index", 0))
    if idx >= len(QUESTIONS):
        await _finalize(chat_id, session)
        return
    q_key, q_text, q_opts = QUESTIONS[idx]
    markup = build_question_keyboard(q_key, q_opts, selected=[], show_skip=True, show_done=(q_key=="genre"))
    await send_message(chat_id, f"<b>Step {idx+1}/{len(QUESTIONS)}</b>\n\n{q_text}", markup)

async def _move_next(chat_id, session, current_idx, key, value):
    next_idx = current_idx + 1
    session_service.upsert_session(chat_id, {f"answers_{key}": value, "question_index": next_idx})
    new_session = session_service.get_session(chat_id)
    if next_idx < len(QUESTIONS):
        await _send_current_question(chat_id, new_session)
    else:
        session_service.upsert_session(chat_id, {"session_state": "idle"})
        await _finalize(chat_id, new_session)

async def _finalize(chat_id, session):
    await send_message(chat_id, "🎬 <b>Reviewing my notes and scanning the archives... I've got some winners for you!</b>")
    await show_typing(chat_id)
    full_list = await rec_service.get_recommendations(session, {}, mode="question_engine")
    await _process_and_send_recs(chat_id, session, full_list, "<b>Behold! I've curated these just for you:</b>")
