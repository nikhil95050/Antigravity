import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container

async def test_full_user_journey_e2e():
    """
    Final Integration Test:
    - Simulates a user profile (Questionnaire answers).
    - Fetches recommendations (AI + Normalization).
    - Enriches with streaming/trailers.
    - Persists to history.
    - Verifies DB integrity.
    """
    print("\n" + "="*50)
    print("PHASE 7: FINAL INTEGRATED JOURNEY E2E")
    print("="*50)

    chat_id = "1878846631"
    rec_service = container.rec_service
    movie_service = container.movie_service
    session_repo = container.session_repo
    
    # 1. Setup Mock User Session (Step 8 complete)
    print("\n[1/4] Setting up mock questionnaire profile...")
    mock_session = {
        "answers_mood": "Nostalgic and Melancholic",
        "answers_genre": "Sci-Fi, Drama",
        "answers_language": "English",
        "answers_era": "90s",
        "answers_context": "Deep space or time travel",
        "answers_time": "Long movie",
        "answers_avoid": "Horror",
        "answers_favorites": "Interstellar, Inception",
        "session_state": "idle",
        "question_index": 8
    }
    session_repo.upsert_session(chat_id, mock_session)
    print("SUCCESS: Session prepared with 8 answers.")

    # 2. Fetch Personalized Recommendations
    print("\n[2/4] Fetching recommendations based on profile...")
    try:
        # Load user for preference weighting
        user = container.user_service.get_user(chat_id)
        
        full_list = await rec_service.get_recommendations(
            mock_session, user, mode="question_engine", chat_id=chat_id, limit=3
        )
        
        if full_list:
            print(f"SUCCESS: Generated {len(full_list)} personalized recommendations.")
            for i, m in enumerate(full_list):
                 print(f"   {i+1}. {m.get('title')} ({m.get('year')}) - Score: {m.get('_score')}")
        else:
            print("FAILURE: No recommendations generated.")
            return
    except Exception as e:
        print(f"ERROR during recommendation gen: {e}")
        return

    # 3. Enrich top pick with Streaming/Trailers
    print("\n[3/4] Enriched top pick with Streaming/Trailers...")
    try:
        top_list = full_list[:1]
        enriched = await rec_service.enrich_movies(top_list, chat_id, "final_journey")
        pick = enriched[0]
        print(f"SUCCESS: Top pick enriched.")
        print(f"   - Title: {pick.get('title')}")
        print(f"   - Trailer: {pick.get('trailer')}")
        print(f"   - Streaming: {pick.get('streaming')[:60]}...")
    except Exception as e:
        print(f"ERROR during enrichment: {e}")

    # 4. Final DB Integrity Check
    print("\n[4/4] Verifying History Persistence...")
    try:
        movie_service.add_to_history(chat_id, enriched)
        # Give background task time
        await asyncio.sleep(2)
        
        history = movie_service.get_history(chat_id, limit=1)
        if history and history[0].get("movie_id") == pick.get("movie_id"):
            print("SUCCESS: Full journey persisted correctly in Supabase.")
        else:
            print("FAILURE: History entry not found or mismatch.")
            
    except Exception as e:
        print(f"ERROR during history verification: {e}")

    print("\n" + "="*50)
    print("INTEGRATED JOURNEY COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_full_user_journey_e2e())
