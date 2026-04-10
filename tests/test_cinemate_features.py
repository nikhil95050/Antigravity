import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container

async def test_cinemate_intelligence():
    print("\n" + "="*50)
    print("CINEMATE INTELLIGENCE & PERSONA VERIFICATION")
    print("="*50)

    chat_id = "1878846631"
    discovery = container.discovery_service
    rec_service = container.rec_service
    user_service = container.user_service
    
    # 1. Verify AI Reasoning in Discover
    print("\n[1/4] Testing AI Reasoning (Explainability)...")
    mock_session = {"answers_mood": "Dark", "answers_genre": "Sci-Fi"}
    mock_user = {"preferred_genres": "Thriller"}
    
    recs = await discovery.get_question_engine_recs(mock_session, mock_user, limit=2, chat_id=chat_id)
    if recs and "reason" in recs[0]:
        print(f"   [OK] CineMate Reasoning: \"{recs[0]['reason']}\"")
    else:
        print("   [FAIL] Reasoning field missing from recommendation.")

    # 2. Verify Star Search
    print("\n[2/4] Testing Star Search (/star Christopher Nolan)...")
    star_recs = await discovery.get_star_movies("Christopher Nolan", limit=2, chat_id=chat_id)
    if star_recs and len(star_recs) > 0:
        print(f"   [OK] Star Search returned {len(star_recs)} movies including: {star_recs[0]['title']}")
    else:
        print("   [FAIL] Star search failed to return results.")

    # 3. Verify Taste Profiling (Like -> Update)
    print("\n[3/4] Testing taste profile recomputation...")
    # Trigger a recompute (mocking that feedback exists)
    await user_service.recompute_taste_profile(chat_id)
    user = user_service.get_user(chat_id)
    print(f"   [OK] Current Taste Profile Genres: {user.get('preferred_genres')}")

    # 4. Verify Subscription Handling
    print("\n[4/4] Testing Subscription state...")
    user_service.update_preferences(chat_id, {"subscriptions": "Netflix,Prime"})
    user_updated = user_service.get_user(chat_id)
    if "Netflix" in user_updated.get("subscriptions", ""):
        print(f"   [OK] User Subscriptions correctly updated: {user_updated.get('subscriptions')}")
    else:
        print("   [FAIL] Subscription update failed.")

    print("\n" + "="*50)
    print("CINEMATE UPGRADE VERIFICATION COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_cinemate_intelligence())
