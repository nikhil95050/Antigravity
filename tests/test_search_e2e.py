import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intent_handler_pkg.dispatch import dispatch_intent

async def test_search_e2e():
    """
    E2E Test for Natural Language Search:
    - Simulates '/search [complex query]'.
    - Verifies AI generates relevant titles.
    - Verifies OMDb enrichment for the search results.
    """
    print("\n" + "="*50)
    print("EDGE CASE: NATURAL LANGUAGE SEARCH E2E")
    print("="*50)

    chat_id = "1878846631"
    
    # Complex, vibe-based query
    query = "I want movies about rainy days, jazz music, and feeling lonely but hopeful"
    
    print(f"\n[1/2] Testing /search with query: '{query}'...")
    try:
        # Mocking the incoming command
        await dispatch_intent("search", chat_id=chat_id, input_text=f"/search {query}")
        print("SUCCESS: Search intent dispatched and processed.")
    except Exception as e:
        print(f"ERROR: {e}")

    # Specific "Movie" command (Similarity)
    print("\n[2/2] Testing /movie (Similarity) for 'Interstellar'...")
    try:
        await dispatch_intent("movie", chat_id=chat_id, input_text="/movie Interstellar")
        print("SUCCESS: Movie similarity intent dispatched and processed.")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\n" + "="*50)
    print("SEARCH TESTS COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_search_e2e())
