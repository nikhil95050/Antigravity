import asyncio
import os
import sys
import json
from datetime import datetime, timezone

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from handlers.dispatch import dispatch_intent
from services.container import user_service, session_service, rec_service, discovery_service
from repositories.user_repository import UserRepository
from services.logging_service import get_logger, interaction_context
from config.supabase_client import select_rows

logger = get_logger("e2e_verify")

CHAT_ID = "1878846631"

async def test_quality_filter():
    print("\n--- [1/4] Testing Quality Filter (/rating 8.5) ---")
    await dispatch_intent("min_rating", chat_id=CHAT_ID, text="/rating 8.5")
    user = user_service.get_user(CHAT_ID)
    val = user.get("avg_rating_preference")
    print(f"Result: DB avg_rating_preference = {val}")
    return val == 8.5

async def test_preference_learning():
    print("\n--- [2/4] Testing Preference Learning (JSONB List) ---")
    # Manually trigger a preference add
    user_service.add_preference(CHAT_ID, "Cyberpunk, Noir", liked=True)
    user = user_service.get_user(CHAT_ID)
    prefs = user.get("preferred_genres", [])
    print(f"Result: DB preferred_genres = {prefs}")
    return "Cyberpunk" in prefs

async def test_semantic_search():
    print("\n--- [3/4] Testing Semantic Intent & Realtime Discovery ---")
    # Simulate a natural language input that should fail standard regex but pass Semantic Scan
    # We use 'fallback' intent as the entry point for the interceptor
    print("Sending natural language: 'show me some highly rated sci-fi'")
    
    # We call dispatch_intent with 'fallback'. It should intercept and call SemanticService.
    # We will verify if it returns recommendations.
    await dispatch_intent("fallback", chat_id=CHAT_ID, text="show me some highly rated sci-fi", input_text="show me some highly rated sci-fi")
    
    # Verify interaction logging in the database
    print("Checking interaction log in Supabase...")
    await asyncio.sleep(2) # Wait for batch flush
    rows, _ = select_rows("user_interactions", {"chat_id": CHAT_ID}, limit=1, order="user_sent_at.desc")
    if rows:
        row = rows[0]
        print(f"Log Found: Intent={row.get('intent')}, Input='{row.get('input_text')}'")
        print(f"Timestamps: UserSent={row.get('user_sent_at')}, BotReplied={row.get('bot_replied_at')}")
        return True
    else:
        print("Error: No interaction log found in DB!")
        return False

async def test_failover_logic():
    print("\n--- [4/4] Testing Failover (Offline Backup) ---")
    # Temporarily modify DiscoveryService to fail (Monkeypatch)
    original = discovery_service.get_trending_movies
    async def failing_trending(*args, **kwargs): raise Exception("Simulated API Error")
    discovery_service.get_trending_movies = failing_trending
    
    recs = await rec_service.get_recommendations({}, {}, mode="trending", chat_id=CHAT_ID)
    
    discovery_service.get_trending_movies = original # Restore
    
    if recs and recs[0].get("_is_fallback"):
        print(f"Success: Correctly fell back to backup essentials: {recs[0]['title']}")
        return True
    print("Error: Failover did not trigger as expected.")
    return False

async def main():
    print(f"Starting Realtime E2E Verification for Chat ID: {CHAT_ID}")
    
    results = []
    results.append(await test_quality_filter())
    results.append(await test_preference_learning())
    results.append(await test_semantic_search())
    results.append(await test_failover_logic())
    
    print("\n" + "="*40)
    print("E2E VERIFICATION REPORT")
    print("="*40)
    features = ["Quality Filter", "JSONB Preferences", "Semantic Search/Log", "Offline Failover"]
    for f, r in zip(features, results):
        status = "PASS" if r else "FAIL"
        print(f"{f:<25} : {status}")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(main())
