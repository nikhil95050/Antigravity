"""
Auto-create Airtable tables that match the current runtime schema.
"""
import os
import sys
import requests

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
META_URL = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}

TABLES = [
    {
        "name": "Sessions",
        "fields": [
            {"name": "Chat ID", "type": "number", "options": {"precision": 0}},
            {"name": "Session State", "type": "singleLineText"},
            {"name": "Question Index", "type": "number", "options": {"precision": 0}},
            {"name": "Pending Question", "type": "singleLineText"},
            {"name": "Answers Mood", "type": "singleLineText"},
            {"name": "Answers Genre", "type": "singleLineText"},
            {"name": "Answers Language", "type": "singleLineText"},
            {"name": "Answers Era", "type": "singleLineText"},
            {"name": "Answers Context", "type": "singleLineText"},
            {"name": "Answers Avoid", "type": "singleLineText"},
            {"name": "Last Recs JSON", "type": "multilineText"},
            {"name": "Sim Depth", "type": "number", "options": {"precision": 0}},
            {"name": "Last Active", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "Updated At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
        ],
    },
    {
        "name": "Users",
        "fields": [
            {"name": "Chat ID", "type": "number", "options": {"precision": 0}},
            {"name": "Username", "type": "singleLineText"},
            {"name": "Preferred Genres", "type": "multilineText"},
            {"name": "Disliked Genres", "type": "multilineText"},
            {"name": "Preferred Language", "type": "singleLineText"},
            {"name": "Preferred Era", "type": "singleLineText"},
            {"name": "Watch Context", "type": "singleLineText"},
            {"name": "Avg Rating Preference", "type": "number", "options": {"precision": 1}},
            {"name": "Updated At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
        ],
    },
    {
        "name": "History",
        "fields": [
            {"name": "Title", "type": "singleLineText"},
            {"name": "Chat ID", "type": "number", "options": {"precision": 0}},
            {"name": "Movie ID", "type": "singleLineText"},
            {"name": "Year", "type": "singleLineText"},
            {"name": "Genres", "type": "multilineText"},
            {"name": "Language", "type": "singleLineText"},
            {"name": "Rating", "type": "singleLineText"},
            {"name": "Recommended At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "Watched", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "Watched At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
        ],
    },
    {
        "name": "Watchlist",
        "fields": [
            {"name": "Title", "type": "singleLineText"},
            {"name": "Chat ID", "type": "number", "options": {"precision": 0}},
            {"name": "Movie ID", "type": "singleLineText"},
            {"name": "Year", "type": "singleLineText"},
            {"name": "Language", "type": "singleLineText"},
            {"name": "Rating", "type": "singleLineText"},
            {"name": "Genres", "type": "multilineText"},
            {"name": "Added At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
        ],
    },
    {
        "name": "Trailer Cache",
        "fields": [
            {"name": "Movie ID", "type": "singleLineText"},
            {"name": "Trailer URL", "type": "url"},
            {"name": "Cached At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
        ],
    },
    {
        "name": "Error Logs",
        "fields": [
            {"name": "Timestamp", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "Chat ID", "type": "number", "options": {"precision": 0}},
            {"name": "Workflow Step", "type": "singleLineText"},
            {"name": "Intent", "type": "singleLineText"},
            {"name": "Error Type", "type": "singleLineText"},
            {"name": "Error Message", "type": "multilineText"},
            {"name": "Raw Payload", "type": "multilineText"},
            {"name": "Retry Status", "type": "singleLineText"},
            {"name": "Resolution Status", "type": "singleLineText"},
        ],
    },
]


def get_existing_tables():
    resp = requests.get(META_URL, headers=HEADERS, timeout=20)
    if resp.status_code == 200:
        return {t["name"] for t in resp.json().get("tables", [])}
    return None


def create_table(table_def: dict) -> bool:
    name = table_def["name"]
    resp = requests.post(META_URL, headers=HEADERS, json=table_def, timeout=30)
    if resp.status_code in (200, 201):
        print(f"Created table: {name}")
        return True
    try:
        err = resp.json()
        message = err.get("error", {}).get("message", resp.text[:200])
    except Exception:
        message = resp.text[:200]
    print(f"Failed to create '{name}': {message}")
    return False


def main():
    print("=" * 60)
    print("Airtable Table Auto-Setup")
    print("=" * 60)

    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        print("Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID environment variables.")
        sys.exit(1)

    print(f"\nBase ID: {AIRTABLE_BASE_ID}")
    print("Checking existing tables...")

    existing = get_existing_tables()
    if existing is None:
        print("\nCannot list tables with the current token. Will try to create everything.\n")
        existing = set()
    else:
        print(f"Found existing tables: {existing or '(none)'}")

    created = 0
    skipped = 0
    failed = 0

    for table_def in TABLES:
        name = table_def["name"]
        if name in existing:
            print(f"Skipping '{name}' (already exists)")
            skipped += 1
            continue
        if create_table(table_def):
            created += 1
        else:
            failed += 1

    print(f"\nDone: {created} created, {skipped} skipped, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("All runtime tables are ready.")


if __name__ == "__main__":
    main()
