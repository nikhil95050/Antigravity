import os
import json
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_message(chat_id, text: str, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=15)
        return r.json()
    except Exception as e:
        print(f"[TG] send_message error: {e}")

def send_photo(chat_id, photo_url: str, caption: str = "", reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
    try:
        r = requests.post(f"{BASE_URL}/sendPhoto", json=payload, timeout=15)
        result = r.json()
        if not result.get("ok"):
            send_message(chat_id, caption, reply_markup, parse_mode)
        return result
    except Exception as e:
        print(f"[TG] send_photo error: {e}")
        send_message(chat_id, caption, reply_markup, parse_mode)

def answer_callback_query(callback_query_id: str, text: str = ""):
    try:
        requests.post(
            f"{BASE_URL}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"[TG] answer_callback error: {e}")

def set_webhook(webhook_url: str):
    r = requests.post(
        f"{BASE_URL}/setWebhook",
        json={"url": webhook_url, "allowed_updates": ["message", "callback_query"]},
        timeout=15
    )
    return r.json()

def build_movie_buttons(movies: list, chat_id=None) -> dict:
    """Build inline keyboard with action buttons for each movie."""
    keyboard = []
    for movie in movies:
        mid = movie.get("movie_id", "")
        title = movie.get("title", "Unknown")[:20]
        trailer = movie.get("trailer", "")
        row_buttons = [
            {"text": f"✅ Watched", "callback_data": f"watched_{mid}"},
            {"text": f"❤️ Like", "callback_data": f"like_{mid}"},
            {"text": f"👎 Dislike", "callback_data": f"dislike_{mid}"},
        ]
        row2 = [
            {"text": f"💾 Save", "callback_data": f"save_{mid}"},
            {"text": f"🎬 More Like", "callback_data": f"more_like_{mid}"},
        ]
        if trailer:
            row2.append({"text": "▶️ Trailer", "url": trailer})
        keyboard.append(row_buttons)
        keyboard.append(row2)
    return {"inline_keyboard": keyboard}

def format_movie_list(movies: list) -> str:
    """Format a list of movies as HTML text."""
    if not movies:
        return "No movies found."
    lines = []
    for i, movie in enumerate(movies, 1):
        title = movie.get("title", "Unknown")
        year = movie.get("year", "")
        rating = movie.get("rating", "N/A")
        genres = movie.get("genres", "")
        desc = movie.get("description", "")
        line = f"<b>{i}. {title}</b> ({year})"
        if rating:
            line += f" ⭐ {rating}"
        if genres:
            line += f"\n🎭 {genres}"
        if desc:
            line += f"\n📖 {desc[:120]}{'...' if len(desc) > 120 else ''}"
        lines.append(line)
    return "\n\n".join(lines)

def format_history_list(history: list) -> str:
    if not history:
        return "Your history is empty. Start by getting recommendations!"
    lines = ["<b>📽 Your Movie History:</b>\n"]
    for item in history[:20]:
        title = item.get("title", "Unknown")
        year = item.get("year", "")
        watched = item.get("watched", False)
        status = "✅ Watched" if watched else "🕐 Pending"
        lines.append(f"• <b>{title}</b> ({year}) — {status}")
    return "\n".join(lines)
