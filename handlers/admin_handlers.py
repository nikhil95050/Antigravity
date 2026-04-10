import asyncio
from services.container import admin_repo, usage_repo
from clients.telegram_helpers import send_message
from config.supabase_client import select_rows

def admin_only(func):
    """Decorator to restrict access to admin handlers."""
    async def wrapper(chat_id, **kwargs):
        if not admin_repo.is_admin(str(chat_id)):
            return
        return await func(chat_id, **kwargs)
    return wrapper

@admin_only
async def handle_admin_health(chat_id, **kwargs):
    from config.supabase_client import is_configured as supabase_ready
    from config.redis_cache import is_connected as redis_ready
    status = "Bot Health Report:\n"
    status += f"Supabase: {'✅' if supabase_ready() else '❌'}\n"
    status += f"Redis: {'✅' if redis_ready() else '❌'}\n"
    await send_message(chat_id, f"<code>{status}</code>")

@admin_only
async def handle_admin_stats(chat_id, **kwargs):
    stats = admin_repo.get_stats()
    text = "<b>Bot Statistics:</b>\n\n"
    for k, v in stats.items():
        text += f"- {k}: {v}\n"
    await send_message(chat_id, text)

@admin_only
async def handle_admin_clear_cache(chat_id, **kwargs):
    from redis_cache import get_redis
    client = get_redis()
    if client:
        client.flushall()
        await send_message(chat_id, "✅ Redis cache cleared.")
    else:
        await send_message(chat_id, "❌ Redis client not available.")

@admin_only
async def handle_admin_errors(chat_id, **kwargs):
    rows, err = select_rows("error_logs", {}, limit=5, order="timestamp.desc")
    if err:
        await send_message(chat_id, f"Error fetching logs: {err}")
        return
    if not rows:
        await send_message(chat_id, "No recent errors found.")
        return
    
    text = "<b>Recent System Errors (Last 5):</b>\n\n"
    for r in rows:
        text += f"📅 {r.get('timestamp')[:16]}\n⚠️ {r.get('error_type')}: <code>{r.get('message', '')[:100]}...</code>\n\n"
    await send_message(chat_id, text)

@admin_only
async def handle_admin_usage(chat_id, **kwargs):
    rows, err = select_rows("api_usage", {}, limit=2000, order="timestamp.desc")
    if err:
        await send_message(chat_id, f"Error fetching usage: {err}")
        return
        
    from collections import defaultdict
    summary = defaultdict(lambda: {"calls": 0, "tokens": 0})
    user_activity = defaultdict(int)
    
    for r in (rows or []):
        p = r.get("provider", "Unknown")
        summary[p]["calls"] += 1
        summary[p]["tokens"] += r.get("total_tokens", 0)
        u_id = r.get("chat_id", "system")
        user_activity[u_id] += 1
        
    text = "<b>📊 Advanced API Usage (Recent 2000):</b>\n\n"
    
    total_tokens = 0
    for p, s in summary.items():
        tokens = s['tokens']
        total_tokens += tokens
        # Rough cost estimate: $0.02 / 1k tokens (blended average placeholder)
        cost = (tokens / 1000) * 0.02 
        text += f"• <b>{p}</b>: {s['calls']} calls, {tokens:,} tks (~${cost:.2f})\n"
    
    text += f"\n<b>💰 Est. Total Cost:</b> ${ (total_tokens / 1000) * 0.02 :.2f}\n"
    
    # Identify Top 5 Users
    top_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]
    if top_users:
        text += "\n<b>🏆 Top Active Users:</b>\n"
        for uid, count in top_users:
            text += f"- <code>{uid}</code>: {count} interactions\n"
            
    await send_message(chat_id, text or "No usage data found.")

@admin_only
async def handle_admin_broadcast(chat_id, input_text, **kwargs):
    msg = input_text.replace("/admin_broadcast", "").strip()
    if not msg:
        await send_message(chat_id, "Usage: /admin_broadcast [message]")
        return
        
    rows, _ = select_rows("users", {}, limit=5000)
    count = len(rows) if rows else 0
    
    from clients.telegram_helpers import build_confirmation_keyboard
    markup = {
        "inline_keyboard": [[
            {"text": "🚀 Confirm & Send", "callback_data": f"admin_b_send_{len(msg)}"},
            {"text": "❌ Cancel", "callback_data": "admin_b_cancel"}
        ]]
    }
    
    # Store message temporarily in Redis for confirmation flow
    from redis_cache import set_json
    set_json(f"broadcast_pending:{chat_id}", {"msg": msg, "count": count}, ttl=300)
    
    await send_message(chat_id, f"📝 <b>Broadcast Preview:</b>\n\n{msg}\n\n⚠️ This will be sent to <b>{count} users</b>. Are you sure?", markup)

@admin_only
async def handle_admin_broadcast_confirm(chat_id, input_text, **kwargs):
    from redis_cache import get_json, delete_key
    pending = get_json(f"broadcast_pending:{chat_id}")
    if not pending:
        await send_message(chat_id, "❌ Broadcast session expired or not found.")
        return
        
    msg = pending["msg"]
    delete_key(f"broadcast_pending:{chat_id}")
    
    await send_message(chat_id, "🚀 Starting broadcast... this may take some time.")
    
    rows, _ = select_rows("users", {}, limit=5000)
    success = 0
    failed = 0
    
    if rows:
        admin_repo.log_admin_action(str(chat_id), "BROADCAST", f"Sent: {msg[:50]}...")
        for u in rows:
            target_id = u.get("chat_id")
            if not target_id: continue
            
            res = await send_message(target_id, f"📢 <b>Important Update from CineMate:</b>\n\n{msg}")
            if res: success += 1
            else: failed += 1
            
            # Rate limiting: ~2 messages per second to stay safe
            await asyncio.sleep(0.5)
            
    await send_message(chat_id, f"✅ <b>Broadcast Complete!</b>\n- Success: {success}\n- Failed: {failed}")

@admin_only
async def handle_admin_broadcast_cancel(chat_id, **kwargs):
    from redis_cache import delete_key
    delete_key(f"broadcast_pending:{chat_id}")
    await send_message(chat_id, "❌ Broadcast cancelled.")

@admin_only
async def handle_admin_disable_provider(chat_id, input_text, **kwargs):
    parts = input_text.split()
    if len(parts) >= 2:
        provider = parts[1].strip().lower()
        from app_config import set_feature_flag
        set_feature_flag(provider, False)
        await send_message(chat_id, f"🚫 Provider <b>{provider}</b> disabled.")

@admin_only
async def handle_admin_enable_provider(chat_id, input_text, **kwargs):
    parts = input_text.split()
    if len(parts) >= 2:
        provider = parts[1].strip().lower()
        from app_config import set_feature_flag
        set_feature_flag(provider, True)
        await send_message(chat_id, f"✅ Provider <b>{provider}</b> enabled.")
