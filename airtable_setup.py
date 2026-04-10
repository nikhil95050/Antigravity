"""
Airtable setup helpers for the current runtime schema.
"""

REQUIRED_TABLES = {
    "Sessions": [
        ("Chat ID", "Number"),
        ("Session State", "Single line text"),
        ("Question Index", "Number"),
        ("Pending Question", "Single line text"),
        ("Answers Mood", "Single line text"),
        ("Answers Genre", "Single line text"),
        ("Answers Language", "Single line text"),
        ("Answers Era", "Single line text"),
        ("Answers Context", "Single line text"),
        ("Answers Avoid", "Single line text"),
        ("Last Recs JSON", "Long text"),
        ("Sim Depth", "Number"),
        ("Last Active", "Date/time"),
        ("Updated At", "Date/time"),
    ],
    "Users": [
        ("Chat ID", "Number"),
        ("Username", "Single line text"),
        ("Preferred Genres", "Long text"),
        ("Disliked Genres", "Long text"),
        ("Preferred Language", "Single line text"),
        ("Preferred Era", "Single line text"),
        ("Watch Context", "Single line text"),
        ("Avg Rating Preference", "Number"),
        ("Updated At", "Date/time"),
    ],
    "History": [
        ("Title", "Single line text"),
        ("Chat ID", "Number"),
        ("Movie ID", "Single line text"),
        ("Year", "Single line text"),
        ("Genres", "Long text"),
        ("Language", "Single line text"),
        ("Rating", "Single line text"),
        ("Recommended At", "Date/time"),
        ("Watched", "Checkbox"),
        ("Watched At", "Date/time"),
    ],
    "Watchlist": [
        ("Title", "Single line text"),
        ("Chat ID", "Number"),
        ("Movie ID", "Single line text"),
        ("Year", "Single line text"),
        ("Language", "Single line text"),
        ("Rating", "Single line text"),
        ("Genres", "Long text"),
        ("Added At", "Date/time"),
    ],
    "Trailer Cache": [
        ("Movie ID", "Single line text"),
        ("Trailer URL", "URL"),
        ("Cached At", "Date/time"),
    ],
    "Error Logs": [
        ("Timestamp", "Date/time"),
        ("Chat ID", "Number"),
        ("Workflow Step", "Single line text"),
        ("Intent", "Single line text"),
        ("Error Type", "Single line text"),
        ("Error Message", "Long text"),
        ("Raw Payload", "Long text"),
        ("Retry Status", "Single line text"),
        ("Resolution Status", "Single line text"),
    ],
}


def print_setup_guide():
    print("=" * 60)
    print("AIRTABLE SETUP GUIDE")
    print("=" * 60)
    print("\nCreate the following tables in your Airtable base:\n")
    for table, fields in REQUIRED_TABLES.items():
        print(f"\nTable: {table}")
        for field_name, field_type in fields:
            print(f"  - {field_name} ({field_type})")
    print("\n" + "=" * 60)


def verify_tables():
    """Try to access each required table using the runtime table names."""
    from airtable_client import get_table

    results = {}
    for table_name in REQUIRED_TABLES:
        try:
            t = get_table(table_name)
            t.all(max_records=1)
            results[table_name] = "OK"
        except Exception as e:
            results[table_name] = f"Error: {e}"
    return results


if __name__ == "__main__":
    print_setup_guide()
    print("\nVerifying table access...")
    results = verify_tables()
    for table, status in results.items():
        print(f"  {table}: {status}")
