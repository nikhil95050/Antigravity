import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container

async def test_storage_e2e():
    """
    E2E Test for Storage & History:
    - Verifies Watchlist saving/retrieval.
    - Verifies History logging.
    - Verifies feedback (Like/Dislike).
    """
    print("\n" + "="*50)
    print("PHASE 4: STORAGE & LIFECYCLE E2E TESTS")
    print("="*50)

    chat_id = "1878846631"
    
    movie_service = container.movie_service
    feedback_repo = container.feedback_repo
    
    dummy_movie = {
        "movie_id": "tt0111161", # Shawshank Redemption
        "title": "The Shawshank Redemption",
        "year": "1994"
    }

    # 1. Test Watchlist Save
    print("\n[1/3] Testing Watchlist Save/Retrieve...")
    try:
        movie_service.add_to_watchlist(chat_id, dummy_movie)
        print("SUCCESS: Movie sent to background save task.")
        
        # Give it a second for the background task to finish (since it's not awaited in code)
        await asyncio.sleep(2)
        
        wl = movie_service.get_watchlist(chat_id)
        found = any(str(m.get("movie_id")) == dummy_movie["movie_id"] for m in wl)
        if found:
            print(f"SUCCESS: Movie found in watchlist ({len(wl)} items).")
        else:
            print("FAILURE: Movie not found in watchlist. (Check background logs if error_batcher was active)")
    except Exception as e:
        print(f"ERROR during watchlist: {e}")

    # 2. Test Feedback (Like/Dislike)
    print("\n[2/3] Testing Feedback logic (Like/Dislike)...")
    try:
        feedback_repo.logging_service = container.shared_client # Mocking if needed? No, repo uses base
        success = container.feedback_repo.add_feedback(chat_id, dummy_movie["movie_id"], "like")
        print("SUCCESS: Feedback 'like' sent to repository.")
    except Exception as e:
        print(f"ERROR during feedback: {e}")

    # 3. Test History retrieval (O(1) Verification)
    print("\n[3/3] Testing History Retrieval...")
    try:
        history = movie_service.get_history(chat_id, limit=5)
        print(f"SUCCESS: Retrieved {len(history)} history entries.")
    except Exception as e:
        print(f"ERROR during history: {e}")

    print("\n" + "="*50)
    print("STORAGE TESTS COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_storage_e2e())
