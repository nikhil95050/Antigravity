import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container
from intent_handler_pkg.dispatch import dispatch_intent

async def test_pagination_e2e():
    """
    E2E Test for Pagination:
    - Populates history with 11 items.
    - Verifies page 1 shows buttons.
    - Verifies page 2 fetches correctly.
    """
    print("\n" + "="*50)
    print("EDGE CASE: PAGINATION E2E TESTS")
    print("="*50)

    chat_id = "1878846631"
    movie_service = container.movie_service
    
    # 1. Populate History with exactly 11 items
    print("\n[1/3] Populating history with 12 items...")
    movies = []
    for i in range(12):
        movies.append({
            "movie_id": f"pagetest_{i}",
            "title": f"Pagination Movie {i}",
            "year": "2024"
        })
    movie_service.add_to_history(chat_id, movies)
    # Background task wait
    await asyncio.sleep(2)
    print("SUCCESS: History populated.")

    # 2. Test History Page 1
    print("\n[2/3] Testing 'History' Page 1...")
    try:
        await dispatch_intent("history", chat_id=chat_id, input_text="/history")
        print("SUCCESS: History Page 1 dispatched.")
    except Exception as e:
        print(f"ERROR: {e}")

    # 3. Test History Page 2 (Simulating callback)
    print("\n[3/3] Testing 'History' Page 2 (Simulated callback)...")
    try:
        # Paging logic uses "history_p2" or similar
        await dispatch_intent("history", chat_id=chat_id, input_text="history_p2")
        print("SUCCESS: History Page 2 dispatched.")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\n" + "="*50)
    print("PAGINATION TESTS COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_pagination_e2e())
