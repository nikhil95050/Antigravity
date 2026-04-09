import json
from datetime import datetime

from airtable_client import (
    get_session, upsert_session, reset_session, get_user, upsert_user,
    get_history, insert_history_rows, update_history_watched,
    get_movie_from_history, save_to_watchlist, now_iso,
)
from recommendation_engine import (
    get_next_question, run_recommendation, lookup_movie, QUESTIONS, QUESTION_KEYS
)
from telegram_helpers import (
    send_message, send_photo, build_movie_buttons, format_movie_list, format_history_list
)
from perplexity_client import generate_explanation


def normalize_input(update: dict) -> dict:
    """Extract chat_id, username, input_text, action_type from Telegram update."""
    result = {
        "chat_id": None,
        "username": "",
        "input_text": "",
        "action_type": "message",
        "callback_query_id": None,
    }
    if "message" in update:
        msg = update["message"]
        result["chat_id"] = msg.get("chat", {}).get("id")
        result["username"] = msg.get("from", {}).get("username", "")
        result["input_text"] = msg.get("text", "").strip()
        result["action_type"] = "message"
    elif "callback_query" in update:
        cq = update["callback_query"]
        result["chat_id"] = cq.get("message", {}).get("chat", {}).get("id")
        result["username"] = cq.get("from", {}).get("username", "")
        result["input_text"] = cq.get("data", "").strip()
        result["action_type"] = "callback"
        result["callback_query_id"] = cq.get("id")
    return result


def detect_intent(input_text: str, session: dict) -> str:
    """Detect intent from input text and session state."""
    text = input_text.lower().strip()

    if text.startswith("/start"):
        return "start"
    if text.startswith("/reset"):
        return "reset"
    if text.startswith("/help"):
        return "help"
    if text.startswith("/movie "):
        return "movie"
    if text == "/movie":
        return "movie_prompt"
    if text.startswith("/history"):
        return "history"
    if text.startswith("watched_"):
        return "watched"
    if text.startswith("like_"):
        return "like"
    if text.startswith("dislike_"):
        return "dislike"
    if text.startswith("save_"):
        return "save"
    if text.startswith("more_like_"):
        return "more_like"
    if text in ("trending", "/trending"):
        return "trending"
    if text in ("surprise", "/surprise"):
        return "surprise"

    session_state = (session or {}).get("session_state", "idle")
    if session_state == "questioning":
        return "questioning"

    return "fallback"


def _save_movies_to_history(chat_id, movies: list):
    """Batch insert movies into history."""
    rows = [
        {
            "chat_id": str(chat_id),
            "movie_id": m.get("movie_id", ""),
            "title": m.get("title", ""),
            "year": str(m.get("year", "")),
            "genres": m.get("genres", ""),
            "language": m.get("language", ""),
            "rating": str(m.get("rating", "")),
            "watched": False,
        }
        for m in movies if m.get("movie_id")
    ]
    if rows:
        insert_history_rows(rows)


def _save_last_recs(chat_id, movies: list):
    """Persist last recommendations in session for dedup."""
    last_recs = json.dumps([
        {"movie_id": m.get("movie_id", ""), "title": m.get("title", "")}
        for m in movies
    ])
    upsert_session(chat_id, {"last_recs_json": last_recs})


def send_movies(chat_id, movies: list, intro: str = ""):
    """Send movie recommendations with photo (if available) and buttons."""
    if not movies:
        send_message(chat_id,
            "Sorry, I couldn't find any movies right now. Try again or use /reset to start fresh.")
        return

    text = ""
    if intro:
        text = f"{intro}\n\n"
    text += format_movie_list(movies)
    text += "\n\n<i>Use the buttons below to interact with each movie:</i>"

    markup = build_movie_buttons(movies, chat_id)
    first_poster = next((m.get("poster") for m in movies if m.get("poster")), None)

    if first_poster:
        send_photo(chat_id, first_poster, text[:1020], markup)
    else:
        for chunk_start in range(0, len(text), 4000):
            chunk = text[chunk_start:chunk_start + 4000]
            if chunk_start == 0:
                send_message(chat_id, chunk, markup)
            else:
                send_message(chat_id, chunk)


def handle_start(chat_id, username, session, user):
    reset_session(chat_id)
    upsert_user(chat_id, username)
    q_key, q_text = QUESTIONS[0]
    upsert_session(chat_id, {
        "session_state": "questioning",
        "question_index": 0,
        "pending_question": q_key,
        "last_active": now_iso(),
    })
    is_returning = bool(user and user.get("username"))
    welcome = (
        f"👋 Welcome{'  back' if is_returning else ''}, <b>{username or 'Movie Fan'}</b>!\n\n"
        "I'm your personal movie recommendation assistant. Let me ask you a few quick questions "
        "to find the perfect films for you.\n\n"
        f"<b>Question 1/{len(QUESTIONS)}:</b> {q_text}"
    )
    send_message(chat_id, welcome)


def handle_reset(chat_id, username):
    reset_session(chat_id)
    send_message(chat_id,
        "🔄 Session reset! Send /start to begin fresh, or type <code>trending</code> or <code>surprise</code>.")


def handle_help(chat_id):
    help_text = (
        "<b>🎬 Movie Bot Commands</b>\n\n"
        "/start — Start a new recommendation session\n"
        "/reset — Reset your session\n"
        "/movie [title] — Search for a specific movie\n"
        "/history — View your recommendation history\n\n"
        "<b>Quick commands:</b>\n"
        "• <code>trending</code> — See trending movies\n"
        "• <code>surprise</code> — Get a surprise recommendation\n\n"
        "<b>Inline buttons on movies:</b>\n"
        "✅ Watched — Mark as watched\n"
        "❤️ Like — Save preference (improves future recs)\n"
        "👎 Dislike — Note dislike\n"
        "💾 Save — Add to watchlist\n"
        "🎬 More Like — Find similar movies"
    )
    send_message(chat_id, help_text)


def handle_movie(chat_id, input_text, session, user):
    parts = input_text.strip().split(None, 1)
    if len(parts) < 2:
        send_message(chat_id,
            "Please provide a movie title. Example: <code>/movie Interstellar</code>")
        return
    title = parts[1].strip()
    send_message(chat_id, f"🔍 Looking up <b>{title}</b> and finding similar movies...")
    movies = lookup_movie(title)
    if not movies:
        send_message(chat_id,
            f"❌ Couldn't find <b>{title}</b>. Please check the title and try again.")
        return

    _save_movies_to_history(chat_id, movies)
    _save_last_recs(chat_id, movies)
    send_movies(chat_id, movies, f"🎬 Here's what I found for <b>{title}</b>:")


def handle_history(chat_id):
    history = get_history(chat_id, limit=20)
    text = format_history_list(history)
    send_message(chat_id, text)


def handle_watched(chat_id, callback_data):
    movie_id = callback_data.replace("watched_", "", 1)
    update_history_watched(chat_id, movie_id, watched=True)
    send_message(chat_id, "✅ Marked as watched! Great choice.")


def handle_like(chat_id, callback_data, user):
    movie_id = callback_data.replace("like_", "", 1)
    movie = get_movie_from_history(chat_id, movie_id)
    if movie:
        genres = movie.get("genres", "")
        current = (user or {}).get("preferred_genres", "")
        new_genres = set(g.strip() for g in current.split(",") if g.strip())
        new_genres.update(g.strip() for g in genres.split(",") if g.strip())
        upsert_user(chat_id, "", {"preferred_genres": ", ".join(new_genres)})
        send_message(chat_id,
            f"❤️ Got it! I'll recommend more movies like <b>{movie.get('title', 'this')}</b>.")
    else:
        send_message(chat_id, "❤️ Preference saved!")


def handle_dislike(chat_id, callback_data, user):
    movie_id = callback_data.replace("dislike_", "", 1)
    movie = get_movie_from_history(chat_id, movie_id)
    if movie:
        genres = movie.get("genres", "")
        current = (user or {}).get("disliked_genres", "")
        new_genres = set(g.strip() for g in current.split(",") if g.strip())
        new_genres.update(g.strip() for g in genres.split(",") if g.strip())
        upsert_user(chat_id, "", {"disliked_genres": ", ".join(new_genres)})
        send_message(chat_id,
            f"👎 Noted! I'll avoid movies like <b>{movie.get('title', 'this')}</b>.")
    else:
        send_message(chat_id, "👎 Preference noted!")


def handle_save(chat_id, callback_data, user):
    movie_id = callback_data.replace("save_", "", 1)
    movie = get_movie_from_history(chat_id, movie_id)
    if movie:
        added = save_to_watchlist(chat_id, movie)
        if added:
            send_message(chat_id,
                f"💾 <b>{movie.get('title', 'Movie')}</b> added to your watchlist!")
        else:
            send_message(chat_id,
                f"<b>{movie.get('title', 'Movie')}</b> is already in your watchlist.")
    else:
        send_message(chat_id,
            "❌ Could not find that movie. It may not be in your history yet.")


def handle_more_like(chat_id, callback_data, session, user):
    movie_id = callback_data.replace("more_like_", "", 1)
    movie = get_movie_from_history(chat_id, movie_id)
    seed_title = movie.get("title", "") if movie else ""
    if not seed_title:
        send_message(chat_id, "❌ Could not find that movie in your history.")
        return

    sim_depth = int((session or {}).get("sim_depth", 0) or 0)
    if sim_depth >= 2:
        send_message(chat_id,
            "🔄 Similarity depth limit reached. Switching to general recommendations...")
        movies = run_recommendation(session, user, mode="question_engine")
        upsert_session(chat_id, {"sim_depth": 0})
    else:
        send_message(chat_id, f"🔍 Finding movies similar to <b>{seed_title}</b>...")
        movies = run_recommendation(session, user, mode="similarity",
                                    seed_title=seed_title, sim_depth=sim_depth)
        upsert_session(chat_id, {"sim_depth": sim_depth + 1})

    _save_movies_to_history(chat_id, movies)
    _save_last_recs(chat_id, movies)
    send_movies(chat_id, movies, f"🎬 Movies similar to <b>{seed_title}</b>:")


def handle_trending(chat_id, session, user):
    send_message(chat_id, "📈 Fetching trending movies...")
    movies = run_recommendation(session, user, mode="trending")
    _save_movies_to_history(chat_id, movies)
    _save_last_recs(chat_id, movies)
    send_movies(chat_id, movies, "📈 <b>Trending Movies Right Now:</b>")


def handle_surprise(chat_id, session, user):
    send_message(chat_id, "🎲 Picking a surprise selection for you...")
    movies = run_recommendation(session, user, mode="surprise")
    _save_movies_to_history(chat_id, movies)
    _save_last_recs(chat_id, movies)
    send_movies(chat_id, movies, "🎲 <b>Surprise Recommendations:</b>")


def handle_questioning(chat_id, input_text, session, user):
    """Handle user answers during the question flow."""
    session = session or {}
    question_index = int(session.get("question_index", 0) or 0)

    if question_index >= len(QUESTIONS):
        _finalize_questions(chat_id, session, user)
        return

    current_key = QUESTIONS[question_index][0]
    field_key = f"answers_{current_key}"
    answer = input_text.strip()

    next_index = question_index + 1
    patch = {
        field_key: answer,
        "question_index": next_index,
        "last_active": now_iso(),
    }

    if next_index < len(QUESTIONS):
        next_key, next_text = QUESTIONS[next_index]
        patch["pending_question"] = next_key
        patch["session_state"] = "questioning"
        upsert_session(chat_id, patch)
        send_message(
            chat_id,
            f"<b>Question {next_index + 1}/{len(QUESTIONS)}:</b> {next_text}"
        )
    else:
        patch["session_state"] = "idle"
        patch["pending_question"] = ""
        upsert_session(chat_id, patch)
        updated_session = {**session, **patch}
        _finalize_questions(chat_id, updated_session, user)


def _finalize_questions(chat_id, session, user):
    send_message(chat_id, "🎬 Perfect! Finding the best movies for you...")
    movies = run_recommendation(session, user, mode="question_engine")
    _save_movies_to_history(chat_id, movies)
    _save_last_recs(chat_id, movies)

    mood = session.get("answers_mood", "")
    genre = session.get("answers_genre", "")
    context_val = session.get("answers_context", "")
    ctx_desc = f"wants {genre or 'good'} movies with {mood or 'a great'} vibe, watching {context_val or 'for themselves'}"

    try:
        explanation = generate_explanation(movies, ctx_desc) if movies else ""
    except Exception:
        explanation = ""

    intro = "🎬 <b>Your Personalized Recommendations:</b>"
    if explanation:
        intro += f"\n\n<i>{explanation}</i>"
    send_movies(chat_id, movies, intro)


def handle_fallback(chat_id, input_text):
    text = (
        f"🤔 I'm not sure what you mean by <i>'{input_text[:50]}'</i>.\n\n"
        "Here's what you can do:\n"
        "• /start — Get personalized recommendations\n"
        "• /movie [title] — Search a specific film\n"
        "• <code>trending</code> — See what's popular\n"
        "• <code>surprise</code> — Random picks\n"
        "• /help — Full command list"
    )
    send_message(chat_id, text)
