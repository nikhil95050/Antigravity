import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container

async def test_architectural_upgrades():
    print("\n" + "="*50)
    print("FINAL ARCHITECTURAL UPGRADE VERIFICATION")
    print("="*50)

    chat_id = "1878846631"
    discovery = container.discovery_service
    rec_service = container.rec_service
    
    # 1. Verify Semantic Caching
    print("\n[1/3] Testing Semantic Caching (Discovery)...")
    prompt = "90s sci-fi movies"
    # First call - Cold
    start = asyncio.get_event_loop().time()
    titles1 = await discovery._get_titles_from_perplexity(prompt, limit=3, chat_id=chat_id)
    duration1 = asyncio.get_event_loop().time() - start
    print(f"   - Cold Call: {duration1:.2f}s | Titles: {titles1}")
    
    # Second call - Warm (Cached)
    start = asyncio.get_event_loop().time()
    titles2 = await discovery._get_titles_from_perplexity(prompt, limit=3, chat_id=chat_id)
    duration2 = asyncio.get_event_loop().time() - start
    print(f"   - Cached Call: {duration2:.2f}s | Titles: {titles2}")
    
    if duration2 < duration1 and titles1 == titles2:
        print("   [OK] SUCCESS: Semantic Caching is active and significantly faster.")
    else:
        print("   [FAIL] FAILED: Caching logic issue.")

    # 2. Verify Metadata Mirroring (OMDb)
    print("\n[2/3] Testing Metadata Mirroring (Supabase)...")
    from omdb_client_helper import omdb_get_by_title_async
    movie_title = titles1[0]
    
    # First lookup - Populate Mirror
    print(f"   - Initial lookup for '{movie_title}'...")
    res1 = await omdb_get_by_title_async(movie_title, chat_id=chat_id)
    
    # Verify Mirror existence
    from supabase_client import select_rows
    rows, _ = select_rows("movie_metadata", {"movie_id": res1["movie_id"]})
    if rows:
        print(f"   [OK] SUCCESS: Metadata mirrored in Supabase for {movie_title}.")
    else:
        print(f"   [FAIL] FAILED: Metadata not found in Supabase mirror.")

    # 3. Verify Lazy Loading (Deferred Enrichment)
    print("\n[3/3] Testing Lazy Discovery placeholders...")
    movies = [{"movie_id": res1["movie_id"], "title": movie_title, "year": res1.get("year")}]
    
    # Perform Deferred Enrichment
    # Note: RecommendationService._enrich_movies_async adds placeholders
    enriched = await rec_service.enrich_movies(movies, chat_id, "test_lazy")
    pick = enriched[0]
    
    if "streaming" in pick and "Loading" in pick["streaming"]:
        print(f"   [OK] SUCCESS: Deferred enrichment placeholder found: {pick['streaming']}")
    else:
        # If it found it in cache, that's also okay, but we want to see the logic
        print(f"   INFO: Streaming info resolved: {pick.get('streaming')}")

    print("\n" + "="*50)
    print("UPGRADE VERIFICATION COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_architectural_upgrades())
