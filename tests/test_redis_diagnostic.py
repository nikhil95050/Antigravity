import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis_cache import get_redis, REDIS_URL, _is_placeholder

def run_diagnostic():
    print("\n" + "="*50)
    print("REDIS INTERFACE DIAGNOSTIC")
    print("="*50)

    load_dotenv()
    
    # 1. Check Configuration
    print(f"\n[1/4] Checking environment variables...")
    if not REDIS_URL:
        print("RESULT: REDIS_URL is empty or not configured.")
    else:
        # Mask password for security
        masked_url = REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL
        print(f"RESULT: Found REDIS_URL ending in ...{masked_url}")

    # 2. Check for Placeholders
    print(f"\n[2/4] Checking for placeholders...")
    if REDIS_URL and _is_placeholder(REDIS_URL):
        print("RESULT: [!] MATCH FOUND. URL contains placeholders (e.g., 'your-db.upstash.io').")
        print("ACTION: You must update your .env with real Upstash credentials.")
    else:
        print("RESULT: No obvious placeholders found.")

    # 3. Test Connection
    print(f"\n[3/4] Attempting connection...")
    client = get_redis()
    if client:
        try:
            latency = client.ping()
            print(f"RESULT: [OK] SUCCESS! Redis is connected and responsive.")
        except Exception as e:
            print(f"RESULT: [FAIL] FAILED. Error: {e}")
    else:
        print("RESULT: [SKIP] SKIPPED. No client initialized (likely due to missing config or placeholders).")

    # 4. Fallback Verification
    print(f"\n[4/4] Verifying Local Fallback...")
    from redis_cache import set_json, get_json
    test_key = "test:diagnostic:ping"
    set_json(test_key, {"status": "ok"}, ttl=10)
    val = get_json(test_key)
    if val and val.get("status") == "ok":
        print("RESULT: [OK] SUCCESS! Local In-Memory Cache is working correctly.")
    else:
        print("RESULT: [FAIL] FAILED. Local cache error.")

    print("\n" + "="*50)
    print("DIAGNOSTIC COMPLETE")
    print("="*50)

if __name__ == "__main__":
    run_diagnostic()
