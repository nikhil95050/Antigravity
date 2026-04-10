import json
import concurrent.futures
from datetime import datetime

from services.session_service import SessionService
from services.user_service import UserService
from services.movie_service import MovieService
from services.recommendation_service import RecommendationService
from repositories.feedback_repository import FeedbackRepository
from repositories.api_usage_repository import ApiUsageRepository
from repositories.admin_repository import AdminRepository

# Initialize services
session_service = SessionService()
user_service = UserService()
movie_service = MovieService()
rec_service = RecommendationService()
feedback_repo = FeedbackRepository()
usage_repo = ApiUsageRepository()
admin_repo = AdminRepository()

from recommendation_engine import QUESTIONS, QUESTION_KEYS
from telegram_helpers import (
    send_message, edit_message, send_photo, build_movie_buttons, build_question_keyboard, build_iteration_buttons,
    format_history_list, format_watchlist_list,
)
from app_config import is_feature_enabled

def normalize_input(update: dict) -> dict:
    result = {"chat_id": None, "username": "", "input_text": "", "action_type": "unknown", "callback_query_id": None}
    if "message" in update:
        msg = update["message"]; chat = msg.get("chat", {})
        result["chat_id"] = chat.get("id"); result["username"] = msg.get("from", {}).get("username", "")
        result["input_text"] = msg.get("text", "").strip(); result["action_type"] = "message"
    elif "callback_query" in update:
        cq = update["callback_query"]; msg = cq.get("message", {}); chat = msg.get("chat", {})
        result["chat_id"] = chat.get("id"); result["username"] = cq.get("from", {}).get("username", "")
        result["input_text"] = cq.get("data", "").strip(); result["action_type"] = "callback"
        result["callback_query_id"] = cq.get("id")
    return result

def detect_intent(input_text: str, session: dict) -> str:
    text = input_text.lower().strip()
    if text.startswith("/start"): return "start"
    if text.startswith("/reset"): return "reset"
    if text.startswith("/help"): return "help"
    if text.startswith("/movie "): return "movie"
    if text == "/movie": return "movie_prompt"
    if text.startswith("/history"): return "history"
    if text.startswith("/watchlist"): return "watchlist"
    if text.startswith("watched_"): return "watched"
    if text.startswith("like_"): return "like"
    if text.startswith("dislike_"): return "dislike"
    if text.startswith("save_"): return "save"
    if text.startswith("more_like_"): return "more_like"
    if text in ("trending", "/trending"): return "trending"
    if text in ("surprise", "/surprise"): return "surprise"
    if text == "q_more_recs": return "questioning_more"
    if text == "q_reset": return "reset"
    if text.startswith("q_"): return "questioning"
    if (session or {}).get("session_state") == "questioning": return "questioning"
    if text.startswith("/admin_"): return text[1:] 
    return "fallback"

def _check_admin(chat_id) -> bool:
    if not admin_repo.is_admin(chat_id):
        send_message(chat_id, "🔒 <b>Access Denied</b>\nThis command is reserved for authorized administrators.")
        return False
    return True

def _build_movie_caption(movie: dict, index: int, total: int) -> str:
    title = movie.get("title", "Movie")
    year = str(movie.get("year", "") or "")
    rating = str(movie.get("rating", "") or "")
    genres = movie.get("genres", "") or ""
    desc = movie.get("description", "") or ""
    trailer = movie.get("trailer", "") or ""
    streaming = movie.get("streaming", "") or ""

    header = f"<b>Pick {index} of {total}: {title}</b>"
    lines = [header, f"<b>{title}</b>{f' ({year})' if year else ''}"]
    if rating:
        lines.append(f"Rating: <b>{rating}</b>")
    if genres:
        lines.append(f"Genres: {genres}")
    if streaming:
        lines.append(f"📺 Watch on: <b>{streaming}</b>")
    if desc:
        lines.append(desc[:420] + ("..." if len(desc) > 420 else ""))
    if trailer: lines.append(f'<a href="{trailer}">Watch trailer</a>')
    lines.append("<i>The buttons below apply to this movie only.</i>")
    return "\n\n".join(lines)

def send_movies(chat_id: str, movies: list, intro: str = "", include_more: bool = False):
    if not movies:
        send_message(chat_id, "I couldn't pull together a strong set of movie picks just yet. Please try again in a moment.")
        return
    if intro:
        send_message(chat_id, intro + "\n\n<i>Each recommendation arrives as its own card, and the buttons belong to the card right above them.</i>")
    
    total = len(movies)
    
    def _send_single(idx_movie):
        index, movie = idx_movie
        caption = _build_movie_caption(movie, index, total)
        markup = build_movie_buttons(movie, chat_id)
        poster = movie.get("poster") or ""
        if poster: send_photo(chat_id, poster, caption[:1020], markup)
        else: send_message(chat_id, caption, markup)

    # Dispatch cards in parallel for visual speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(_send_single, enumerate(movies, start=1))
    
    if include_more:
        send_message(chat_id, "Not seeing a match? Or want to keep looking?", build_iteration_buttons())

def _send_current_question(chat_id, session):
    idx = int((session or {}).get("question_index", 0))
    if idx >= len(QUESTIONS):
        _finalize(chat_id, session, first_run=True)
        return

    q_key, q_text, q_opts = QUESTIONS[idx]
    show_skip = True
    show_done = (q_key == "genre")
    
    selected = []
    if q_key == "genre":
        selected = [s.strip() for s in session.get("answers_genre", "").split(",") if s.strip()]

    markup = build_question_keyboard(q_key, q_opts, selected=selected, show_skip=show_skip, show_done=show_done)
    progress = f"<b>Question {idx+1}/{len(QUESTIONS)}</b>\n\n"
    full_text = progress + q_text
    
    last_msg_id = session.get("last_question_msg_id")
    if last_msg_id:
        res = edit_message(chat_id, last_msg_id, full_text, markup)
        if not res or not res.get("ok"):
            res = send_message(chat_id, full_text, markup)
    else:
        res = send_message(chat_id, full_text, markup)
    
    if res and res.get("ok"):
        new_msg_id = res.get("result", {}).get("message_id")
        session_service.upsert_session(chat_id, {"last_question_msg_id": new_msg_id})

def handle_start(chat_id, username, session, user):
    session_service.reset_session(chat_id)
    user_service.upsert_user(chat_id, username)
    new_session = {"session_state": "questioning", "question_index": 0}
    session_service.upsert_session(chat_id, new_session)
    
    index = abs(hash(username or "user")) % 3
    greeting = ["Welcome back", "Great to see you again", "Glad you're back"][index] if user else "Welcome to your personal cinema guide"
    welcome = f"<b>{greeting}, {username or 'Movie Fan'}.</b>\n\nI'm here to find movies that match your exact mood.\n\nLet's get started with a few quick questions."
    send_message(chat_id, welcome)
    _send_current_question(chat_id, new_session)

def handle_questioning(chat_id, input_text, session, user):
    idx = int((session or {}).get("question_index", 0))
    if idx >= len(QUESTIONS):
         _finalize(chat_id, session, first_run=False)
         return
    
    current_key = QUESTIONS[idx][0]
    
    if input_text.startswith("q_"):
        if input_text == "q_more_recs": return handle_questioning_more(chat_id, session)
        if input_text == "q_reset": return handle_reset(chat_id, user.get("username", ""))

        if input_text.startswith("q_skip_") or input_text.startswith("q_done_"):
             target_key = input_text.split("_")[-1]
             if target_key != current_key: return 
        elif input_text.startswith(f"q_{current_key}_"):
             pass 
        else:
             return

    ans = input_text
    if input_text.startswith("q_skip_"):
        ans = "[Skipped]"
        _move_next(chat_id, session, idx, current_key, ans)
        return
    
    if input_text.startswith("q_done_"):
        _move_next(chat_id, session, idx, current_key, session.get(f"answers_{current_key}", ""))
        return

    if input_text.startswith(f"q_{current_key}_"):
        choice = input_text.replace(f"q_{current_key}_", "", 1)
        if current_key == "genre":
            current_ans = session.get("answers_genre", "")
            selected = [s.strip() for s in current_ans.split(",") if s.strip()]
            if choice in selected: selected.remove(choice)
            else: selected.append(choice)
            new_ans = ",".join(selected)
            session_service.upsert_session(chat_id, {"answers_genre": new_ans})
            session["answers_genre"] = new_ans 
            _send_current_question(chat_id, session)
            return
        else:
            ans = choice
            _move_next(chat_id, session, idx, current_key, ans)
            return

    _move_next(chat_id, session, idx, current_key, ans)

def handle_questioning_more(chat_id, session):
    _finalize(chat_id, session, first_run=False)

def _move_next(chat_id, session, current_idx, key, value):
    next_idx = current_idx + 1
    session_service.upsert_session(chat_id, {f"answers_{key}": value, "question_index": next_idx})
    new_session = session_service.get_session(chat_id)
    if next_idx < len(QUESTIONS):
        _send_current_question(chat_id, new_session)
    else:
        session_service.upsert_session(chat_id, {"session_state": "idle"})
        _finalize(chat_id, new_session, first_run=True)

def _finalize(chat_id, session, first_run=True):
    try:
        if first_run:
            send_message(chat_id, "✨ <b>Profile complete!</b>\n\nI know exactly what you like now. Fetching personalized recommendations...\n🎬 <b>Finding your perfect movies...</b>")
        
        full_session = session_service.get_session(chat_id)
        user = user_service.get_user(chat_id)
        
        # Usage Tracking (InBackground)
        usage_repo.log_usage("Perplexity", "generate_recommendations", str(chat_id))
        
        movies = rec_service.get_recommendations(full_session, user, mode="question_engine")
        
        if not movies:
            send_message(chat_id, "I've run out of recommendations that fit your current profile perfectly! Try <code>/start</code> fresh?")
            return

        seen_raw = full_session.get("last_recs_json") or "[]"
        try: seen = json.loads(seen_raw)
        except: seen = []
        
        new_seen = [{"movie_id": m.get("movie_id"), "title": m.get("title")} for m in movies]
        all_seen = seen + new_seen
        session_service.upsert_session(chat_id, {"last_recs_json": json.dumps(all_seen)})
        
        # Enforce history enrichment by ensuring full metadata is passed
        movie_service.add_to_history(chat_id, movies)
        
        intro = "<b>Your personalized recommendations are ready.</b>" if first_run else "<b>Here are 5 more suggestions for you:</b>"
        send_movies(chat_id, movies, intro, include_more=True)
    except Exception as e:
        print(f"[Finalize] Critical Error: {e}")
        from airtable_client import log_error
        log_error(chat_id, "intent_handler._finalize", "question_engine", "finalize_crash", str(e))
        send_message(chat_id, "Oops! I ran into a small technical glitch while curating your picks. Please try tapping 'Next Suggestions' again or send /start to retry.")

def handle_reset(chat_id, username):
    session_service.reset_session(chat_id)
    send_message(chat_id, "Fresh slate. Send <code>/start</code> for a new guided session.")

def handle_movie(chat_id, input_text, session, user):
    parts = input_text.strip().split(None, 1)
    if len(parts) < 2:
        send_message(chat_id, "I need a title first. Try <code>/movie Inception</code>.")
        return
    title = parts[1].strip()
    
    # Usage Tracking
    usage_repo.log_usage("Apify/OMDb", "lookup_movie", str(chat_id))
    
    send_message(chat_id, f"Analyzing <b>{title}</b> and curating similar vibes for you...")
    movies = rec_service.lookup_movie_context(title)
    if not movies:
        send_message(chat_id, f"I couldn't track down <b>{title}</b>.")
        return
    movie_service.add_to_history(chat_id, movies)
    
    seen_raw = session.get("last_recs_json") or "[]"
    try: seen = json.loads(seen_raw)
    except: seen = []
    all_seen = seen + [{"movie_id": m.get("movie_id"), "title": m.get("title")} for m in movies]
    session_service.upsert_session(chat_id, {"last_recs_json": json.dumps(all_seen)})
    send_movies(chat_id, movies, f"<b>Based on {title}, here are some top-tier picks.</b>")

def handle_history(chat_id):
    history = movie_service.get_history(chat_id)
    send_message(chat_id, format_history_list(history))

def handle_watchlist(chat_id):
    wl = movie_service.get_watchlist(chat_id)
    send_message(chat_id, format_watchlist_list(wl))

def handle_watched(chat_id, callback_data):
    movie_id = callback_data.replace("watched_", "", 1)
    movie_service.mark_as_watched(chat_id, movie_id)
    send_message(chat_id, "Marked as watched. Nice one.")

def handle_save(chat_id, callback_data, user):
    movie_id = callback_data.replace("save_", "", 1)
    history = movie_service.get_history(chat_id)
    movie = next((m for m in history if str(m.get("movie_id")) == str(movie_id)), None)
    if movie:
        movie_service.add_to_watchlist(chat_id, movie)
        send_message(chat_id, f"Saved <b>{movie.get('title')}</b> to your watchlist.")
    else:
        send_message(chat_id, "Saved to your watchlist.")

def handle_more_like(chat_id, callback_data, session, user):
    movie_id = callback_data.replace("more_like_", "", 1)
    
    # Usage Tracking
    usage_repo.log_usage("Perplexity", "similarity_recs", str(chat_id))
    
    send_message(chat_id, "Building a tighter set of recommendations...")
    movies = rec_service.get_recommendations(session, user, mode="similarity", seed_title=movie_id)
    movie_service.add_to_history(chat_id, movies)
    send_movies(chat_id, movies, "More like that...")

def handle_trending(chat_id, session, user):
    # Usage Tracking
    usage_repo.log_usage("Perplexity", "trending_list", str(chat_id))
    
    send_message(chat_id, "Scanning the crowd-pleasers...")
    movies = rec_service.get_recommendations(session, user, mode="trending")
    movie_service.add_to_history(chat_id, movies)
    send_movies(chat_id, movies, "<b>Trending right now</b>")

def handle_surprise(chat_id, session, user):
    # Usage Tracking
    usage_repo.log_usage("Perplexity", "surprise_list", str(chat_id))
    
    send_message(chat_id, "Finding some wildcards...")
    movies = rec_service.get_recommendations(session, user, mode="surprise")
    movie_service.add_to_history(chat_id, movies)
    send_movies(chat_id, movies, "<b>Surprise picks worth a look</b>")

def handle_fallback(chat_id, input_text):
    send_message(chat_id, "I'm not sure about that. Try <code>/start</code> or <code>/help</code>.")

def handle_help(chat_id):
    help_text = (
        "🎬 <b>Movie Bot Commands</b>\n\n"
        "<code>/start</code> - Start a new guided session\n"
        "<code>/movie [title]</code> - Find similar movies\n"
        "<code>/history</code> - View your recent recommendations\n"
        "<code>/watchlist</code> - View your saved movies\n"
        "<code>/trending</code> - See what's popular right now\n"
        "<code>/surprise</code> - Get hidden gem recommendations\n"
        "<code>/reset</code> - Reset your current session\n"
        "<code>/help</code> - Show this help message"
    )
    send_message(chat_id, help_text)

def handle_admin_health(chat_id):
    if not _check_admin(chat_id): return
    send_message(chat_id, "Health status active.") 

def handle_admin_stats(chat_id):
    if not _check_admin(chat_id): return
    admin_repo.cleanup_old_logs(days=7)
    stats = admin_repo.get_stats()
    lines = ["<b>Bot Performance Metrics</b>"]
    for k, v in stats.items():
        lines.append(f"- {k.replace('_', ' ').title()}: <b>{v}</b>")
    send_message(chat_id, "\n".join(lines))

def handle_like(chat_id, callback_data, user):
    movie_id = callback_data.replace("like_", "", 1)
    feedback_repo.log_reaction(chat_id, movie_id, "like")
    send_message(chat_id, "Locked in. I'll steer future picks closer to this vibe.")

def handle_dislike(chat_id, callback_data, user):
    movie_id = callback_data.replace("dislike_", "", 1)
    feedback_repo.log_reaction(chat_id, movie_id, "dislike")
    send_message(chat_id, "Noted. I'll avoid recommendations like that.")

def handle_admin_errors(chat_id):
    if not _check_admin(chat_id): return
    admin_repo.log_admin_action(chat_id, "admin_errors")
    from airtable_client import get_recent_errors
    errors = get_recent_errors(limit=5)
    if not errors:
        send_message(chat_id, "No errors reported in the last 24h.")
        return
    lines = ["<b>Recent System Errors</b>"]
    for e in errors:
        lines.append(f"⚠️ {e['intent']}.{e['workflow_step']}: {e['error_message'][:100]}")
    send_message(chat_id, "\n".join(lines))

def handle_admin_clear_cache(chat_id):
    if not _check_admin(chat_id): return
    admin_repo.log_admin_action(chat_id, "admin_clear_cache")
    from redis_cache import clear_local_cache
    clear_local_cache()
    send_message(chat_id, "Hot caches cleared successfully.")

def handle_admin_disable_provider(chat_id, provider_name):
    if not _check_admin(chat_id): return
    admin_repo.log_admin_action(chat_id, "admin_disable_provider", provider_name)
    from app_config import set_feature_flag
    set_feature_flag(provider_name, False)
    admin_repo.update_provider_health(provider_name, False, 10, datetime.utcnow().isoformat())
    send_message(chat_id, f"Provider <b>{provider_name}</b> has been manually disabled.")

def handle_admin_enable_provider(chat_id, provider_name):
    if not _check_admin(chat_id): return
    admin_repo.log_admin_action(chat_id, "admin_enable_provider", provider_name)
    from app_config import set_feature_flag
    set_feature_flag(provider_name, True)
    admin_repo.update_provider_health(provider_name, True, 0, None)
    send_message(chat_id, f"Provider <b>{provider_name}</b> has been manually enabled.")
