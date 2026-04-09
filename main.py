import os
import json
import threading
from flask import Flask, request, jsonify

from telegram_helpers import set_webhook, answer_callback_query
from airtable_client import get_session, upsert_session, get_user
from intent_handler import (
    normalize_input, detect_intent,
    handle_start, handle_reset, handle_help, handle_movie,
    handle_history, handle_watched, handle_like, handle_dislike,
    handle_save, handle_more_like, handle_trending, handle_surprise,
    handle_questioning, handle_fallback,
)

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SECRET_PATH = f"/webhook/{TELEGRAM_BOT_TOKEN}"


def process_update(update: dict):
    """Main dispatcher — processes a single Telegram update."""
    try:
        normalized = normalize_input(update)
        chat_id = normalized["chat_id"]
        username = normalized["username"]
        input_text = normalized["input_text"]
        action_type = normalized["action_type"]
        callback_query_id = normalized["callback_query_id"]

        if not chat_id:
            print("[Bot] No chat_id found, skipping update.")
            return

        if action_type == "callback" and callback_query_id:
            answer_callback_query(callback_query_id)

        session = get_session(chat_id) or {}
        user = get_user(chat_id)

        upsert_session(chat_id, {"last_active": __import__('airtable_client').now_iso()})

        intent = detect_intent(input_text, session)
        print(f"[Bot] chat_id={chat_id} intent={intent} text='{input_text[:60]}'")

        if intent == "start":
            handle_start(chat_id, username, session, user)
        elif intent == "reset":
            handle_reset(chat_id, username)
        elif intent == "help":
            handle_help(chat_id)
        elif intent in ("movie", "movie_prompt"):
            handle_movie(chat_id, input_text, session, user)
        elif intent == "history":
            handle_history(chat_id)
        elif intent == "watched":
            handle_watched(chat_id, input_text)
        elif intent == "like":
            handle_like(chat_id, input_text, user)
        elif intent == "dislike":
            handle_dislike(chat_id, input_text, user)
        elif intent == "save":
            handle_save(chat_id, input_text, user)
        elif intent == "more_like":
            handle_more_like(chat_id, input_text, session, user)
        elif intent == "trending":
            handle_trending(chat_id, session, user)
        elif intent == "surprise":
            handle_surprise(chat_id, session, user)
        elif intent == "questioning":
            handle_questioning(chat_id, input_text, session, user)
        else:
            handle_fallback(chat_id, input_text)

    except Exception as e:
        print(f"[Bot] Unhandled error in process_update: {e}")
        import traceback
        traceback.print_exc()


@app.route(SECRET_PATH, methods=["POST"])
def webhook():
    """Telegram webhook endpoint."""
    try:
        update = request.get_json(force=True)
        if not update:
            return jsonify({"ok": False, "error": "empty body"}), 400
        thread = threading.Thread(target=process_update, args=(update,))
        thread.daemon = True
        thread.start()
        return jsonify({"ok": True}), 200
    except Exception as e:
        print(f"[Webhook] Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/setup-webhook", methods=["GET"])
def setup_webhook():
    """Register the webhook URL with Telegram."""
    domain = os.environ.get("REPLIT_DEV_DOMAIN", "")
    if not domain:
        return jsonify({"error": "REPLIT_DEV_DOMAIN not set"}), 500
    webhook_url = f"https://{domain}{SECRET_PATH}"
    result = set_webhook(webhook_url)
    print(f"[Setup] Webhook set to: {webhook_url}")
    print(f"[Setup] Telegram response: {result}")
    return jsonify({"webhook_url": webhook_url, "telegram_response": result})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Telegram Movie Bot (Airtable)"})


@app.route("/", methods=["GET"])
def index():
    domain = os.environ.get("REPLIT_DEV_DOMAIN", "localhost:5000")
    return f"""
    <html>
    <head>
      <title>Telegram Movie Bot</title>
      <style>
        body {{font-family:sans-serif;max-width:700px;margin:40px auto;padding:20px;line-height:1.6}}
        h1 {{color:#1a1a2e}} h2 {{color:#16213e;border-bottom:2px solid #e94560;padding-bottom:6px}}
        code {{background:#f4f4f4;padding:2px 6px;border-radius:4px;font-size:0.9em}}
        .card {{background:#f8f9fa;border-left:4px solid #e94560;padding:15px 20px;margin:15px 0;border-radius:4px}}
        .ok {{color:green;font-weight:bold}} .warn {{color:#e94560;font-weight:bold}}
        a.btn {{display:inline-block;padding:10px 20px;background:#e94560;color:white;text-decoration:none;border-radius:6px;margin:5px 3px}}
        a.btn:hover {{background:#c73652}}
        ol li {{margin:8px 0}}
      </style>
    </head>
    <body>
    <h1>🎬 Telegram Movie Recommendation Bot</h1>
    <div class="card">
      <p>✅ <strong>Bot server is running</strong> on <code>https://{domain}</code></p>
    </div>

    <h2>🚀 Setup Steps</h2>
    <ol>
      <li>
        <strong>Create Airtable tables</strong> — Your Airtable token needs the right scopes.<br>
        <a class="btn" href="/airtable-setup-guide">View Table Setup Guide</a>
        <a class="btn" href="/airtable-status">Check Table Status</a>
      </li>
      <li>
        <strong>Register Telegram webhook</strong> (do this after tables are ready)<br>
        <a class="btn" href="/setup-webhook">Register Webhook</a>
      </li>
      <li>
        <strong>Test in Telegram</strong> — send <code>/start</code> to your bot!
      </li>
    </ol>

    <h2>📋 Available Commands in Telegram</h2>
    <ul>
      <li><code>/start</code> — Start personalized recommendation flow (6-question wizard)</li>
      <li><code>/reset</code> — Reset your session</li>
      <li><code>/movie [title]</code> — Search a specific movie</li>
      <li><code>/history</code> — View your last 20 recommendations</li>
      <li><code>trending</code> — See what's popular right now</li>
      <li><code>surprise</code> — Get random diverse picks</li>
      <li><code>/help</code> — Full command list</li>
    </ul>

    <h2>🔘 Inline Button Actions</h2>
    <ul>
      <li>✅ Watched — Mark a movie as watched</li>
      <li>❤️ Like — Save preference (improves future recs)</li>
      <li>👎 Dislike — Avoid similar genres</li>
      <li>💾 Save — Add to watchlist</li>
      <li>🎬 More Like — Find similar movies</li>
    </ul>

    <h2>🔗 Quick Links</h2>
    <a class="btn" href="/health">Health Check</a>
    <a class="btn" href="/airtable-status">Airtable Status</a>
    <a class="btn" href="/airtable-setup-guide">Setup Guide</a>
    </body>
    </html>
    """

@app.route("/airtable-setup-guide", methods=["GET"])
def airtable_setup_guide():
    from airtable_setup import REQUIRED_TABLES
    html = """<html><head><title>Airtable Setup Guide</title>
    <style>
      body {font-family:sans-serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.6}
      h1 {color:#1a1a2e} h2 {color:#16213e;margin-top:30px}
      code {background:#f4f4f4;padding:2px 6px;border-radius:4px}
      pre {background:#1a1a2e;color:#e2e8f0;padding:15px;border-radius:8px;overflow-x:auto}
      .step {background:#f8f9fa;border-left:4px solid #e94560;padding:15px 20px;margin:15px 0;border-radius:4px}
      a.btn {display:inline-block;padding:10px 18px;background:#e94560;color:white;text-decoration:none;border-radius:6px;margin:5px 3px}
      table {border-collapse:collapse;width:100%;margin:10px 0}
      th,td {border:1px solid #ddd;padding:8px 12px;text-align:left}
      th {background:#16213e;color:white}
    </style></head><body>
    <h1>🗄 Airtable Setup Guide</h1>
    <div class="step">
      <strong>Option A (Recommended): Create a token with schema permissions</strong><br>
      <ol>
        <li>Go to <a href="https://airtable.com/create/tokens" target="_blank">airtable.com/create/tokens</a></li>
        <li>Click <strong>Create new token</strong></li>
        <li>Add these scopes: <code>data.records:read</code>, <code>data.records:write</code>, <code>schema.bases:read</code>, <code>schema.bases:write</code></li>
        <li>Add your base under "Access" → select your base</li>
        <li>Copy the token and update the <strong>AIRTABLE_API_KEY</strong> secret in Replit</li>
        <li>Visit <a href="/run-auto-setup">/run-auto-setup</a> to auto-create all tables</li>
      </ol>
    </div>
    <div class="step">
      <strong>Option B: Create tables manually in Airtable</strong><br>
      Go to <a href="https://airtable.com" target="_blank">airtable.com</a>, open your base, and create each table below.
    </div>
    <h2>Required Tables & Fields</h2>"""

    for table_name, fields in REQUIRED_TABLES.items():
        html += f"<h2>📋 {table_name}</h2><table><tr><th>Field Name</th><th>Field Type</th></tr>"
        for fname, ftype in fields:
            html += f"<tr><td><code>{fname}</code></td><td>{ftype}</td></tr>"
        html += "</table>"

    html += "<p><a href='/'>← Back to Home</a> &nbsp; <a href='/run-auto-setup'>Try Auto-Setup →</a></p></body></html>"
    return html

@app.route("/run-auto-setup", methods=["GET"])
def run_auto_setup():
    """Try to auto-create Airtable tables."""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "create_airtable_tables.py"],
        capture_output=True, text=True, timeout=60
    )
    output = result.stdout + result.stderr
    success = result.returncode == 0
    color = "green" if success else "#e94560"
    return f"""<html><body style='font-family:sans-serif;max-width:700px;margin:40px auto;padding:20px'>
    <h1>Auto-Setup Result</h1>
    <pre style='background:#1a1a2e;color:#e2e8f0;padding:20px;border-radius:8px;white-space:pre-wrap'>{output}</pre>
    <p><a href='/airtable-status'>Check Table Status</a> | <a href='/'>Home</a> | <a href='/airtable-setup-guide'>Manual Setup Guide</a></p>
    </body></html>"""


@app.route("/airtable-status", methods=["GET"])
def airtable_status():
    """Check Airtable table connectivity."""
    from airtable_setup import verify_tables, REQUIRED_TABLES
    results = {}
    try:
        results = verify_tables()
    except Exception as e:
        results = {"error": str(e)}

    html = "<html><body style='font-family:sans-serif;max-width:700px;margin:40px auto;padding:20px'>"
    html += "<h1>🗄 Airtable Table Status</h1>"
    for table, status in results.items():
        color = "green" if "OK" in status else "red"
        html += f"<p style='color:{color}'><b>{table}</b>: {status}</p>"

    html += "<hr><h2>Required Table Structure</h2>"
    from airtable_setup import REQUIRED_TABLES
    for table, fields in REQUIRED_TABLES.items():
        html += f"<h3>📋 {table}</h3><ul>"
        for field_name, field_type in fields:
            html += f"<li><code>{field_name}</code> — {field_type}</li>"
        html += "</ul>"
    html += "<p><a href='/'>← Back</a></p></body></html>"
    return html


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[Bot] Starting on port {port}")
    print(f"[Bot] Webhook path: {SECRET_PATH}")
    app.run(host="0.0.0.0", port=port, debug=False)
