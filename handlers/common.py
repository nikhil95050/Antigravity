import json
import asyncio
from typing import Optional
from services.container import session_service, movie_service, rec_service
from clients.telegram_helpers import (
    send_message, send_photo, build_movie_buttons, build_iteration_buttons, 
    build_pagination_keyboard
)

async def send_movies_async(chat_id: str, movies: list, intro: str = "", include_more: bool = False, deferred: bool = False, intent: str = "recs"):
    """Truly concurrent movie card delivery with optional background enrichment."""
    if intro: await send_message(chat_id, intro)
    
    tasks = []
    for idx, movie in enumerate(movies, 1):
        tasks.append(send_single_movie_async(chat_id, movie, idx, len(movies), deferred=deferred, intent=intent))
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    if include_more:
        await send_message(chat_id, "Want more?", build_iteration_buttons())

async def send_single_movie_async(chat_id, movie, index, total, deferred=False, intent="recs"):
    reason = f"\n\n✨ <i>{movie.get('reason')}</i>" if movie.get("reason") else ""
    streaming_text = f"\n   📺 <i>{movie.get('streaming', '') or '🔄 Loading streaming info...'}</i>"
    caption = f"<b>{index}/{total}: {movie.get('title')}</b>\n\n{movie.get('description', '')[:450]}{reason}{streaming_text}"
    markup = build_movie_buttons(movie, chat_id)
    poster = movie.get("poster")
    
    if poster: 
        resp = await send_photo(chat_id, poster, caption[:1020], markup)
    else: 
        resp = await send_message(chat_id, caption, markup)
    
    # If deferred, launch background enrichment task
    if deferred and resp and resp.get("ok"):
        message_id = resp["result"]["message_id"]
        from services.container import rec_service
        asyncio.create_task(rec_service.background_enrich_single_update(
            chat_id, message_id, movie, index, total, intent
        ))

async def _process_and_send_recs(chat_id, session, full_list, intro_text):
    if not full_list:
        await send_message(chat_id, "I couldn't find any matches. Try /reset!")
        return

    top_5 = full_list[:5]
    overflow = full_list[5:14] 
    
    # 1. Faster Enrichment (Metadata Mirroring)
    enriched = await rec_service.enrich_movies(top_5, chat_id, "init_recs")
    _update_last_recs_and_history(chat_id, enriched, overflow)
    
    # 2. Parallel Dispatch with Background Lazy Enrichment
    await send_movies_async(chat_id, enriched, intro_text, include_more=bool(overflow), deferred=True, intent="init_recs")

def _update_last_recs_and_history(chat_id, enriched_recs, overflow_list=None):
    """Saves enriched movies to history and updates session cache."""
    movie_service.add_to_history(chat_id, enriched_recs)
    patch = {"last_recs_json": json.dumps(enriched_recs)}
    if overflow_list is not None:
        patch["overflow_buffer_json"] = json.dumps(overflow_list)
    session_service.upsert_session(chat_id, patch)

def _update_last_recs(chat_id, recs):
    session_service.upsert_session(chat_id, {"last_recs_json": json.dumps(recs)})

def _get_page(input_text: str) -> int:
    if "p" not in input_text: return 1
    try: return int(input_text.split("p")[-1])
    except: return 1

def _get_last_recs(session) -> list:
    try:
        raw = session.get("last_recs_json", "[]")
        return json.loads(raw) if isinstance(raw, str) else raw
    except: return []

def _find_movie_in_recs(movies: list, movie_id: str) -> Optional[dict]:
    return next((m for m in movies if str(m.get("movie_id")) == str(movie_id)), None)
