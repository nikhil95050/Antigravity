"""
Airtable Setup Script
Run this once to verify/document the required Airtable table structure.
Tables must be created manually in Airtable with the following fields.
"""

REQUIRED_TABLES = {
    "sessions": [
        ("chat_id", "Single line text"),
        ("session_state", "Single line text"),
        ("question_index", "Number"),
        ("pending_question", "Single line text"),
        ("answers_mood", "Single line text"),
        ("answers_genre", "Single line text"),
        ("answers_language", "Single line text"),
        ("answers_era", "Single line text"),
        ("answers_context", "Single line text"),
        ("answers_avoid", "Single line text"),
        ("last_recs_json", "Long text"),
        ("sim_depth", "Number"),
        ("last_active", "Single line text"),
        ("updated_at", "Single line text"),
    ],
    "users": [
        ("chat_id", "Single line text"),
        ("username", "Single line text"),
        ("preferred_genres", "Single line text"),
        ("disliked_genres", "Single line text"),
        ("preferred_language", "Single line text"),
        ("preferred_era", "Single line text"),
        ("watch_context", "Single line text"),
        ("avg_rating_preference", "Single line text"),
        ("updated_at", "Single line text"),
    ],
    "history": [
        ("chat_id", "Single line text"),
        ("movie_id", "Single line text"),
        ("title", "Single line text"),
        ("year", "Single line text"),
        ("genres", "Single line text"),
        ("language", "Single line text"),
        ("rating", "Single line text"),
        ("recommended_at", "Single line text"),
        ("watched", "Checkbox"),
        ("watched_at", "Single line text"),
    ],
    "watchlist": [
        ("chat_id", "Single line text"),
        ("movie_id", "Single line text"),
        ("title", "Single line text"),
        ("year", "Single line text"),
        ("language", "Single line text"),
        ("rating", "Single line text"),
        ("genres", "Single line text"),
    ],
    "trailer_cache": [
        ("movie_id", "Single line text"),
        ("trailer_url", "Single line text"),
        ("cached_at", "Single line text"),
    ],
}

def print_setup_guide():
    print("=" * 60)
    print("AIRTABLE SETUP GUIDE")
    print("=" * 60)
    print("\nCreate the following tables in your Airtable base:\n")
    for table, fields in REQUIRED_TABLES.items():
        print(f"\n📋 Table: {table}")
        for field_name, field_type in fields:
            print(f"   • {field_name} ({field_type})")
    print("\n" + "=" * 60)

def verify_tables():
    """Try to access each required table."""
    from airtable_client import get_table
    results = {}
    for table_name in REQUIRED_TABLES:
        try:
            t = get_table(table_name)
            t.all(max_records=1)
            results[table_name] = "✅ OK"
        except Exception as e:
            results[table_name] = f"❌ Error: {e}"
    return results

if __name__ == "__main__":
    print_setup_guide()
    print("\nVerifying table access...")
    results = verify_tables()
    for table, status in results.items():
        print(f"  {table}: {status}")
