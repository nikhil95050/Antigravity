import os
import json
from dotenv import load_dotenv

load_dotenv()
import requests

from airtable_client import log_error

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _should_retry(status_code: int) -> bool:
    return status_code in (429, 500, 502, 503, 504)


def _clean_media_url(url: str, validate: bool = False) -> str:
    cleaned = (url or "").strip()
    if not cleaned or not cleaned.startswith(("http://", "https://")):
        return ""
    
    return cleaned


def _post_telegram(method: str, payload: dict, timeout: int, chat_id=None, step: str = "telegram"):
    url = f"{BASE_URL}/{method}"
    for attempt in ("first", "retry"):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            status = r.status_code
            try:
                data = r.json()
            except Exception:
                data = None

            if status == 200 and isinstance(data, dict) and data.get("ok") is True:
                return data

            if attempt == "first" and _should_retry(status):
                continue

            log_error(
                chat_id,
                f"{step}.{method}",
                "",
                "telegram_api_failed",
                f"Telegram {method} failed with status {status}",
                raw_payload={
                    "payload": payload,
                    "response": {
                        "status_code": status,
                        "text": r.text[:500],
                        "json": data if isinstance(data, dict) else None,
                    },
                },
                retry_status="retried" if attempt == "retry" else "not_retried",
                resolution_status="open",
            )
            return None
        except Exception as e:
            if attempt == "first":
                continue
            log_error(
                chat_id,
                f"{step}.{method}",
                "",
                "telegram_request_exception",
                str(e),
                raw_payload={"payload": payload},
                retry_status="retried",
                resolution_status="open",
            )
            return None
    return None


def send_message(chat_id, text: str, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
    return _post_telegram("sendMessage", payload, timeout=15, chat_id=chat_id, step="telegram")


def edit_message(chat_id, message_id, text: str, reply_markup=None, parse_mode="HTML"):
    """Edits an existing text message."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
    return _post_telegram("editMessageText", payload, timeout=10, chat_id=chat_id, step="telegram")


def delete_message(chat_id, message_id):
    """Deletes a message from the chat."""
    payload = {"chat_id": chat_id, "message_id": message_id}
    return _post_telegram("deleteMessage", payload, timeout=8, chat_id=chat_id, step="telegram")


def send_photo(chat_id, photo_url: str, caption: str = "", reply_markup=None, parse_mode="HTML"):
    cleaned_photo = _clean_media_url(photo_url)
    if not cleaned_photo:
        return send_message(chat_id, caption, reply_markup, parse_mode)

    payload = {
        "chat_id": chat_id,
        "photo": cleaned_photo,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup

    result = _post_telegram("sendPhoto", payload, timeout=15, chat_id=chat_id, step="telegram")
    if not result:
        fallback = caption + "\n\n<i>Poster unavailable right now, but the movie details are still below.</i>"
        return send_message(chat_id, fallback, reply_markup, parse_mode)
    return result


def answer_callback_query(callback_query_id: str, text: str = "", chat_id=None):
    payload = {"callback_query_id": callback_query_id, "text": text}
    result = _post_telegram("answerCallbackQuery", payload, timeout=10, chat_id=chat_id, step="telegram")
    return bool(result)


def set_webhook(webhook_url: str):
    payload = {"url": webhook_url, "allowed_updates": ["message", "callback_query"]}
    return _post_telegram("setWebhook", payload, timeout=15, chat_id=None, step="telegram") or {"ok": False}


def build_movie_buttons(movie: dict, chat_id=None) -> dict:
    mid = (movie or {}).get("movie_id", "")
    trailer = (movie or {}).get("trailer", "")

    primary = [
        {"text": "Watched", "callback_data": f"watched_{mid}"},
        {"text": "Like this", "callback_data": f"like_{mid}"},
        {"text": "Dislike", "callback_data": f"dislike_{mid}"},
    ]
    secondary = [
        {"text": "Save this", "callback_data": f"save_{mid}"},
        {"text": "More like this", "callback_data": f"more_like_{mid}"},
    ]
    if trailer:
        secondary.append({"text": "Trailer", "url": trailer})
    return {"inline_keyboard": [primary, secondary]}


def build_question_keyboard(q_key: str, options: list, selected: list = None, show_skip=True, show_done=False) -> dict:
    """Builds a keyboard for questions with choice and skip buttons."""
    keyboard = []
    selected = selected or []
    
    row = []
    for opt in options:
        label = f"✅ {opt}" if opt in selected else opt
        row.append({"text": label, "callback_data": f"q_{q_key}_{opt}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    controls = []
    if show_skip:
        controls.append({"text": "Skip ➡️", "callback_data": f"q_skip_{q_key}"})
    if show_done:
        controls.append({"text": "Done ✅", "callback_data": f"q_done_{q_key}"})
    
    if controls:
        keyboard.append(controls)
        
    return {"inline_keyboard": keyboard}


def build_iteration_buttons() -> dict:
    """Buttons to either get more suggestions or finish the session."""
    return {"inline_keyboard": [
        [
            {"text": "Next 5 Suggestions ➡️", "callback_data": "q_more_recs"},
            {"text": "Done ✅", "callback_data": "q_reset"}
        ]
    ]}


def format_history_list(history: list) -> str:
    if not history:
        return "Your history is empty. Start by getting recommendations!"
    lines = ["<b>Your Movie History</b>\n"]
    for item in history[:20]:
        title = item.get("title", "Unknown")
        year = item.get("year", "")
        watched = item.get("watched", False)
        status = "Watched" if watched else "Pending"
        lines.append(f"- <b>{title}</b> ({year}) - {status}")
    return "\n".join(lines)


def format_watchlist_list(watchlist: list) -> str:
    if not watchlist:
        return "Your watchlist is empty right now. Save a movie from any recommendation card to build it up."
    lines = ["<b>Your Watchlist</b>\n"]
    for item in watchlist[:25]:
        title = item.get("title", "Unknown")
        year = item.get("year", "")
        rating = item.get("rating", "")
        genres = item.get("genres", "")
        line = f"- <b>{title}</b>"
        if year:
            line += f" ({year})"
        if rating:
            line += f" - Rating {rating}"
        if genres:
            line += f"\n  {genres}"
        lines.append(line)
    return "\n".join(lines)
