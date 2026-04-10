import asyncio
import os
import sys
import time
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container

async def test_performance_e2e():
    """
    E2E Test for Performance & Enrichment:
    - Measures latency for multi-movie enrichment.
    - Verifies Watchmode and OMDb integration for deep links.
    - Verifies local cache speedup.
    """
    print("\n" + "="*50)
    print("PHASE 6: PERFORMANCE & STREAMING E2E TESTS")
    print("="*50)

    chat_id = "1878846631"
    rec_service = container.rec_service
    
    test_movies = [
        {"movie_id": "tt0111161", "title": "The Shawshank Redemption", "year": "1994"},
        {"movie_id": "tt0137523", "title": "Fight Club", "year": "1999"},
        {"movie_id": "tt0109830", "title": "Forrest Gump", "year": "1994"}
    ]

    # 1. Cold Enrichment (No cache)
    print("\n[1/3] Testing 'Cold Enrichment' (Batch of 3)...")
    from redis_cache import clear_local_cache
    clear_local_cache()
    
    start_time = time.time()
    try:
        enriched = await rec_service.enrich_movies(test_movies, chat_id, "perf_test")
        duration = time.time() - start_time
        print(f"SUCCESS: Enriched {len(enriched)} movies in {duration:.2f}s.")
        
        for m in enriched:
            streaming = m.get("streaming", "N/A")
            print(f"   - {m.get('title')}: {streaming[:60]}...")
            
    except Exception as e:
        print(f"ERROR during cold enrichment: {e}")

    # 2. Warm Enrichment (Cached)
    print("\n[2/3] Testing 'Warm Enrichment' (Cache speedup)...")
    start_time = time.time()
    try:
        enriched_warm = await rec_service.enrich_movies(test_movies, chat_id, "perf_test_warm")
        duration_warm = time.time() - start_time
        print(f"SUCCESS: Re-enriched from cache in {duration_warm:.4f}s.")
        if duration_warm < 0.1:
            print("INFO: Cache HIT confirmed (Sub-100ms response).")
        else:
            print(f"WARNING: Cache might be slow or MISSING: {duration_warm:.4f}s")
    except Exception as e:
        print(f"ERROR during warm enrichment: {e}")

    # 3. Watchmode Direct Deep Link Verification
    print("\n[3/3] Verifying Watchmode Source Accuracy...")
    try:
        sources = await container.watchmode_client.get_streaming_sources("tt0111161", "The Shawshank Redemption")
        if sources:
             print(f"SUCCESS: Found sources: {', '.join(sources[:3])}...")
        else:
             print("INFO: No streaming sources found for Shawshank in current region.")
    except Exception as e:
        print(f"ERROR during watchmode check: {e}")

    print("\n" + "="*50)
    print("PERFORMANCE TESTS COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_performance_e2e())
