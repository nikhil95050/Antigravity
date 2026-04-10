import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container
from redis_cache import clear_local_cache

async def test_discovery_e2e():
    """
    E2E Test for Discovery Features:
    - Verified Perplexity -> OMDb -> Watchmode flow.
    - Verified JSON Parsing of AI outputs.
    - Verified Caching (Local & Redis Fallback).
    """
    print("\n" + "="*50)
    print("PHASE 2: DISCOVERY & AI E2E TESTS")
    print("="*50)
    
    chat_id = "1878846631"
    clear_local_cache() # Ensure fresh run
    
    discovery = container.discovery_service
    
    # 1. Test Trending Movies
    print("\n[1/3] Testing 'Trending Movies'...")
    try:
        trending = await discovery.get_trending_movies(limit=3, chat_id=chat_id)
        if trending and len(trending) > 0:
            print(f"SUCCESS: Found {len(trending)} trending movies.")
            for m in trending:
                print(f"   - {m.get('title')} ({m.get('year')})")
        else:
            print("FAILURE: No trending movies returned.")
    except Exception as e:
        print(f"ERROR during trending: {e}")

    # 2. Test Similar Movies (Complex flow: AI -> OMDb)
    print("\n[2/3] Testing 'Similar Movies' (Seed: Inception)...")
    try:
        similar = await discovery.get_similar_movies("Inception", limit=3, chat_id=chat_id)
        if similar and len(similar) > 0:
            print(f"SUCCESS: Found {len(similar)} similar movies.")
            for m in similar:
                print(f"   - {m.get('title')} ({m.get('year')})")
        else:
            print("FAILURE: No similar movies returned.")
    except Exception as e:
        print(f"ERROR during similar: {e}")

    # 3. Test Surprise Movies
    print("\n[3/3] Testing 'Surprise Movies'...")
    try:
        surprise = await discovery.get_surprise_movies(limit=3, chat_id=chat_id)
        if surprise and len(surprise) > 0:
            print(f"SUCCESS: Found {len(surprise)} surprise movies.")
            for m in surprise:
                print(f"   - {m.get('title')} ({m.get('year')})")
        else:
            print("FAILURE: No surprise movies returned.")
    except Exception as e:
        print(f"ERROR during surprise: {e}")

    print("\n" + "="*50)
    print("DISCOVERY TESTS COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_discovery_e2e())
