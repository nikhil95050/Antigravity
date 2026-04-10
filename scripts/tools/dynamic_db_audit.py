import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_API_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.environ.get("SUPABASE_API_KEY", "").strip()
)

def get_headers():
    return {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}"
    }

async def discover_tables():
    if not SUPABASE_URL or not SUPABASE_API_KEY:
        print("Error: Supabase credentials missing.")
        return

    url = f"{SUPABASE_URL}/rest/v1/"
    
    async with httpx.AsyncClient() as client:
        try:
            # PostgREST base endpoint returns the OpenAPI spec
            resp = await client.get(url, headers=get_headers())
            if resp.status_code != 200:
                print(f"Failed to fetch spec: {resp.status_code}")
                return

            spec = resp.json()
            # Tables are listed under "definitions"
            tables = spec.get("definitions", {}).keys()
            
            print(f"Discovered {len(tables)} tables: {', '.join(tables)}")
            
            results = {}
            for table in tables:
                table_url = f"{url}{table}"
                # Get 1 sample row to see actual column names
                sample_resp = await client.get(table_url, params={"limit": 1}, headers=get_headers())
                if sample_resp.status_code == 200:
                    data = sample_resp.json()
                    cols = list(data[0].keys()) if data else "Exists but empty"
                    results[table] = cols
                else:
                    results[table] = f"Error {sample_resp.status_code}"
            
            print("\n--- LIVE SCHEMA ANALYSIS ---")
            for table, cols in results.items():
                print(f"Table: {table}")
                print(f"Columns: {cols}")
                print("-" * 20)

        except Exception as e:
            print(f"Audit failed: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(discover_tables())
