def normalize_input(update: dict) -> dict:
    """Extracts core fields from a Telegram update object."""
    result = {
        "chat_id": None, 
        "username": "", 
        "input_text": "", 
        "action_type": "unknown", 
        "callback_query_id": None,
        "message_id": None
    }
    if "message" in update:
        msg = update["message"]
        chat = msg.get("chat", {})
        result["chat_id"] = chat.get("id")
        result["username"] = msg.get("from", {}).get("username", "")
        result["input_text"] = msg.get("text", "").strip()
        result["action_type"] = "message"
        result["message_id"] = msg.get("message_id")
        import datetime
        ts = msg.get("date")
        if ts: result["sent_at"] = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()
    elif "callback_query" in update:
        cq = update["callback_query"]
        msg = cq.get("message", {})
        chat = msg.get("chat", {})
        result["chat_id"] = chat.get("id")
        result["username"] = cq.get("from", {}).get("username", "")
        result["input_text"] = cq.get("data", "").strip()
        result["action_type"] = "callback"
        result["callback_query_id"] = cq.get("id")
        result["message_id"] = msg.get("message_id")
        import datetime
        ts = msg.get("date") # message.date for the message the callback is on
        if ts: result["sent_at"] = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()
    return result

def detect_intent(input_text: str, session: dict) -> str:
    """Maps raw input text to a logical bot intent."""
    text = input_text.lower().strip()
    
    # Simple commands
    if text.startswith("/start"): return "start"
    if text.startswith("/reset"): return "reset"
    if text.startswith("/help"):  return "help"
    if text.startswith("/rating") or text.startswith("/min_rating"): return "min_rating"
    if text.startswith("/movie"): return "movie"
    if text.startswith("/search"):
        # Check for inline query
        query = input_text[7:].strip()
        if query: 
            # Store temporarily in session? No, pass as kwargs via dispatch
            return "search"
        return "search"
    if text in ("trending", "/trending"): return "trending"
    if text in ("surprise", "/surprise"): return "surprise"
    
    # Repository views
    if text.startswith("/history") or text.startswith("history_p"): return "history"
    if text.startswith("/watchlist") or text.startswith("watchlist_p"): return "watchlist"
    
    # Callback actions
    if text.startswith("watched_"):   return "watched"
    if text.startswith("save_"):      return "save"
    if text.startswith("more_like_"): return "more_like"
    if text.startswith("like_"):      return "like"
    if text.startswith("dislike_"):   return "dislike"
    if text == "/more_suggestions" or text == "more_suggestions_action": return "more_suggestions"
    
    # Questionnaire flow
    if text.startswith("q_"):
        if text == "q_more_recs": return "more_suggestions"
        if text == "q_reset":     return "reset"
        return "questioning"
    
    # Admin commands
    if text.startswith("/admin_"):
        # Split out specific admin routes
        route = text.replace("/", "", 1)
        return route # e.g. "admin_health", "admin_stats"
        
    # State-based fallback
    if (session or {}).get("session_state") == "questioning":
        return "questioning"
        
    return "fallback"
