import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

from services.logging_service import LoggingService, interaction_context

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Shared AsyncClient for connection pooling and efficiency
_client = httpx.AsyncClient(
    timeout=httpx.Timeout(20.0, connect=5.0),
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
)

def _clean_media_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned or not cleaned.startswith(("http://", "https://")):
        return ""
    return cleaned

async def _post_telegram_async(method: str, payload: dict, chat_id=None):
    url = f"{BASE_URL}/{method}"
    loop = asyncio.get_event_loop()
    start = loop.time()
    try:
        resp = await _client.post(url, json=payload)
        latency = int((loop.time() - start) * 1000)
        
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            # SUCCESS: Check for active interaction context to log Input/Output pair
            from services.logging_service import interaction_context, LoggingService
            import time
            from utils.time_utils import utc_now_iso
            
            ctx = interaction_context.get()
            if ctx and method in ["sendMessage", "sendPhoto", "editMessageText"]:
                bot_replied_at = utc_now_iso()
                latency = int((time.time() - ctx["start_time"]) * 1000)
                
                # Get response text
                response_text = payload.get("text") or payload.get("caption") or "[Media/Keyboard Update]"
                
                LoggingService.log_interaction(
                    chat_id=ctx["chat_id"],
                    input_text=ctx["input_text"],
                    response_text=response_text,
                    intent=ctx["intent"],
                    latency_ms=latency,
                    user_sent_at=ctx.get("user_sent_at"),
                    bot_replied_at=bot_replied_at
                )
            
            return data

        # Log Failure
        LoggingService.log_event(
            chat_id, "telegram", f"{method}_failed",
            status="error", error_type="telegram_api_error",
            latency_ms=latency,
            extra={"status": resp.status_code, "response": data, "payload": payload}
        )
        return None

    except Exception as e:
        latency = int((loop.time() - start) * 1000)
        LoggingService.log_event(
            chat_id, "telegram", f"{method}_exception",
            status="error", error_type="telegram_network_error",
            latency_ms=latency,
            extra={"error": str(e), "payload": payload}
        )
        return None

# --- Async Messages ---

async def send_message(chat_id, text: str, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
    return await _post_telegram_async("sendMessage", payload, chat_id=chat_id)

async def edit_message(chat_id, message_id, text: str, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
    return await _post_telegram_async("editMessageText", payload, chat_id=chat_id)

async def edit_message_caption(chat_id, message_id, caption: str, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "message_id": message_id, "caption": caption, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
    return await _post_telegram_async("editMessageCaption", payload, chat_id=chat_id)

async def send_photo(chat_id, photo_url: str, caption: str = "", reply_markup=None, parse_mode="HTML"):
    photo = _clean_media_url(photo_url)
    if not photo:
        return await send_message(chat_id, caption, reply_markup, parse_mode)
    payload = {"chat_id": chat_id, "photo": photo, "caption": caption, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
    return await _post_telegram_async("sendPhoto", payload, chat_id=chat_id)

async def answer_callback_query(callback_query_id: str, text: str = "", chat_id=None):
    payload = {"callback_query_id": callback_query_id, "text": text}
    res = await _post_telegram_async("answerCallbackQuery", payload, chat_id=chat_id)
    return bool(res)

async def show_typing(chat_id):
    """Signals to the user that the bot is thinking."""
    return await _post_telegram_async("sendChatAction", {"chat_id": chat_id, "action": "typing"}, chat_id=chat_id)

async def set_webhook(webhook_url: str):
    payload = {"url": webhook_url, "allowed_updates": ["message", "callback_query"]}
    res = await _post_telegram_async("setWebhook", payload)
    return res or {"ok": False}

# --- Keyboards (Synchronous helpers) ---

def build_movie_buttons(movie: dict, chat_id=None) -> dict:
    mid = (movie or {}).get("movie_id", "")
    trailer = (movie or {}).get("trailer", "")
    primary = [
        {"text": "✅ Watched", "callback_data": f"watched_{mid}"},
        {"text": "👍 Like", "callback_data": f"like_{mid}"},
        {"text": "👎 Dislike", "callback_data": f"dislike_{mid}"},
    ]
    secondary = [
        {"text": "📂 Save", "callback_data": f"save_{mid}"},
        {"text": "🔄 More Like This", "callback_data": f"more_like_{mid}"},
    ]
    if trailer:
        secondary.append({"text": "🎥 Trailer", "url": trailer})
    return {"inline_keyboard": [primary, secondary]}

def build_question_keyboard(q_key: str, options: list, selected: list = None, show_skip=True, show_done=False) -> dict:
    keyboard = []
    selected = selected or []
    row = []
    for opt in options:
        label = f"✅ {opt}" if opt in selected else opt
        row.append({"text": label, "callback_data": f"q_{q_key}_{opt}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    controls = []
    if show_skip: controls.append({"text": "Skip ⏭️", "callback_data": f"q_skip_{q_key}"})
    if show_done: controls.append({"text": "Done ✅", "callback_data": f"q_done_{q_key}"})
    if controls: keyboard.append(controls)
    return {"inline_keyboard": keyboard}

def build_iteration_buttons() -> dict:
    return {"inline_keyboard": [[
        {"text": "Next 5 Picks ➡️", "callback_data": "q_more_recs"},
        {"text": "Reset / Start Over 🔄", "callback_data": "q_reset"}
    ]]}

def build_pagination_keyboard(cmd_prefix: str, current_page: int, has_more: bool) -> dict:
    btns = []
    if current_page > 1:
        btns.append({"text": "⬅️ Previous", "callback_data": f"{cmd_prefix}p{current_page - 1}"})
    if has_more:
        btns.append({"text": "Next ➡️", "callback_data": f"{cmd_prefix}p{current_page + 1}"})
    return {"inline_keyboard": [btns]} if btns else None

# --- Formatting (Synchronous helpers) ---

def format_history_list(history: list, page: int = 1) -> str:
    if not history: return "Your history is empty."
    lines = [f"<b>🎬 Your Movie History (Page {page})</b>\n"]
    for item in history:
        title = item.get("title", "Unknown")
        year = item.get("year", "")
        watched = item.get("watched", False)
        status = "✅" if watched else "⏳"
        lines.append(f"{status} <b>{title}</b> ({year})")
    return "\n".join(lines)

def format_watchlist_list(watchlist: list, page: int = 1) -> str:
    if not watchlist: return "Your watchlist is empty."
    lines = [f"<b>📂 Your Watchlist (Page {page})</b>\n"]
    for item in watchlist:
        title = item.get("title", "Unknown")
        year = f" ({item.get('year')})" if item.get('year') else ""
        streaming = item.get("streaming", "")
        if streaming and "Not currently available" not in streaming:
            streaming_text = f"\n   📺 <i>{streaming}</i>"
        else:
            streaming_text = ""
        lines.append(f"- <b>{title}</b>{year}{streaming_text}")
    return "\n".join(lines)
