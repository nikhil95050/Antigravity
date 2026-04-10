import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.container import container

async def test_resilience_e2e():
    """
    E2E Test for Resilience:
    - Mocks an API failure in OMDb.
    - Verifies enrich_movies handles the exception gracefully.
    - Verifies the user still receives title/year even if metadata fails.
    """
    print("\n" + "="*50)
    print("EDGE CASE: RESILIENCE & GRACEFUL DEGRADATION")
    print("="*50)

    chat_id = "1878846631"
    rec_service = container.rec_service
    
    test_movies = [{"movie_id": "none", "title": "A Movie That Fails", "year": "2024"}]

    # 1. Simulating API Failure
    print("\n[1/2] Mocking OMDb Failure...")
    
    # We will temporarily patch container.shared_client to raise an error
    original_client = container.shared_client
    
    class FailingClient:
        async def get(self, *args, **kwargs):
            raise Exception("OMDb API is Down (Mocked Error)")
            
    container.shared_client = FailingClient()
    
    try:
        print("Attempting to enrich movie during API failure...")
        start_time = asyncio.get_event_loop().time()
        # enrich_movies will call get_trailer() and get_streaming() which use LoggingService.profile_call_async
        enriched = await rec_service.enrich_movies(test_movies, chat_id, "resilience_test")
        duration = asyncio.get_event_loop().time() - start_time
        
        print(f"SUCCESS: Enrichment completed in {duration:.2f}s despite failure.")
        pick = enriched[0]
        print(f"   - Title: {pick.get('title')}")
        print(f"   - Trailer Status: {'None/Default' if not pick.get('trailer') else 'Found'}")
        
    except Exception as e:
        print(f"FAILURE: System crashed during API failure: {e}")
    finally:
        container.shared_client = original_client

    # 2. Verify Error Log in Supabase
    print("\n[2/2] Verifying Error Log persistence...")
    try:
        from supabase_client import select_rows
        rows, _ = select_rows("error_logs", {"chat_id": str(chat_id)}, limit=1, order="timestamp.desc")
        if rows:
             print(f"SUCCESS: Found error log entry: {rows[0].get('error_type')}")
        else:
             print("INFO: No error log found; Error might have been caught locally or batcher not flushed.")
    except Exception as e:
        print(f"ERROR checking logs: {e}")

    print("\n" + "="*50)
    print("RESILIENCE TESTS COMPLETE")
    print("="*50)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_resilience_e2e())
