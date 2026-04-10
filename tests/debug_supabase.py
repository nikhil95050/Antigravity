import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_API_KEY")

async def debug_supabase_insert():
    print(f"Testing Supabase Insert to 'api_usage'...")
    url = f"{SUPABASE_URL}/rest/v1/api_usage"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    # Minimal payload
    payload = {
        "chat_id": "1878846631",
        "provider": "TestProvider",
        "action": "test_action",
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")

if __name__ == "__main__":
    asyncio.run(debug_supabase_insert())
