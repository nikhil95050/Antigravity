import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_client import select_rows

def audit_schema():
    tables = [
        "users", 
        "sessions", 
        "history", 
        "watchlist", 
        "feedback", 
        "api_usage", 
        "error_logs", 
        "movie_metadata"
    ]
    
    print("="*60)
    print(" LIVE SUPABASE DATABASE AUDIT ")
    print("="*60)
    
    for table in tables:
        # Request 1 row to inspect columns
        data, err = select_rows(table, limit=1)
        
        if err:
            if "status 404" in err or "does not exist" in err.lower():
                print(f"\n[TABLE] {table}: MISSING")
            else:
                print(f"\n[TABLE] {table}: ERROR ACCESSING")
                print(f"   Detail: {err}")
            continue
            
        print(f"\n[TABLE] {table}: EXISTS")
        if data and len(data) > 0:
            columns = sorted(list(data[0].keys()))
            print(f"   Columns: {', '.join(columns)}")
        else:
            # If empty, let's try to get columns via a zero-row select if PostgREST allows, 
            # otherwise just mark as empty.
            print("   Status: Exists but is currently empty. Cannot inspect columns via sampling.")

if __name__ == "__main__":
    audit_schema()
