"""
Auto-create all required Airtable tables for the Movie Bot.
Requires your Airtable token to have: schema.bases:write and data.records:write scopes.

Run once: python create_airtable_tables.py
"""
import os
import sys
import json
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
        "name": "sessions",
        "fields": [
            {"name": "chat_id", "type": "singleLineText"},
            {"name": "session_state", "type": "singleLineText"},
            {"name": "question_index", "type": "number", "options": {"precision": 0}},
            {"name": "pending_question", "type": "singleLineText"},
            {"name": "answers_mood", "type": "singleLineText"},
            {"name": "answers_genre", "type": "singleLineText"},
            {"name": "answers_language", "type": "singleLineText"},
            {"name": "answers_era", "type": "singleLineText"},
            {"name": "answers_context", "type": "singleLineText"},
            {"name": "answers_avoid", "type": "singleLineText"},
            {"name": "last_recs_json", "type": "multilineText"},
            {"name": "sim_depth", "type": "number", "options": {"precision": 0}},
            {"name": "last_active", "type": "singleLineText"},
            {"name": "updated_at", "type": "singleLineText"},
        ],
    },
    {
        "name": "users",
        "fields": [
            {"name": "chat_id", "type": "singleLineText"},
            {"name": "username", "type": "singleLineText"},
            {"name": "preferred_genres", "type": "singleLineText"},
            {"name": "disliked_genres", "type": "singleLineText"},
            {"name": "preferred_language", "type": "singleLineText"},
            {"name": "preferred_era", "type": "singleLineText"},
            {"name": "watch_context", "type": "singleLineText"},
            {"name": "avg_rating_preference", "type": "singleLineText"},
            {"name": "updated_at", "type": "singleLineText"},
        ],
    },
    {
        "name": "history",
        "fields": [
            {"name": "chat_id", "type": "singleLineText"},
            {"name": "movie_id", "type": "singleLineText"},
            {"name": "title", "type": "singleLineText"},
            {"name": "year", "type": "singleLineText"},
            {"name": "genres", "type": "singleLineText"},
            {"name": "language", "type": "singleLineText"},
            {"name": "rating", "type": "singleLineText"},
            {"name": "recommended_at", "type": "singleLineText"},
            {"name": "watched", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
            {"name": "watched_at", "type": "singleLineText"},
        ],
    },
    {
        "name": "watchlist",
        "fields": [
            {"name": "chat_id", "type": "singleLineText"},
            {"name": "movie_id", "type": "singleLineText"},
            {"name": "title", "type": "singleLineText"},
            {"name": "year", "type": "singleLineText"},
            {"name": "language", "type": "singleLineText"},
            {"name": "rating", "type": "singleLineText"},
            {"name": "genres", "type": "singleLineText"},
        ],
    },
    {
        "name": "trailer_cache",
        "fields": [
            {"name": "movie_id", "type": "singleLineText"},
            {"name": "trailer_url", "type": "singleLineText"},
            {"name": "cached_at", "type": "singleLineText"},
        ],
    },
]


def get_existing_tables():
    resp = requests.get(META_URL, headers=HEADERS)
    if resp.status_code == 200:
        return {t["name"] for t in resp.json().get("tables", [])}
    return None


def create_table(table_def: dict) -> bool:
    name = table_def["name"]
    resp = requests.post(META_URL, headers=HEADERS, json=table_def)
    if resp.status_code in (200, 201):
        print(f"  ✅ Created table: {name}")
        return True
    else:
        err = resp.json()
        print(f"  ❌ Failed to create '{name}': {err.get('error', {}).get('message', resp.text[:200])}")
        return False


def main():
    print("=" * 60)
    print("Airtable Table Auto-Setup")
    print("=" * 60)

    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        print("❌ Missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID environment variables.")
        sys.exit(1)

    print(f"\nBase ID: {AIRTABLE_BASE_ID}")
    print("Checking existing tables...")

    existing = get_existing_tables()
    if existing is None:
        print(
            "\n⚠️  Cannot list tables (token may lack 'schema.bases:read' scope).\n"
            "   Will attempt to create all tables anyway.\n"
        )
        existing = set()
    else:
        print(f"Found existing tables: {existing or '(none)'}")

    print("\nCreating missing tables...")
    created = 0
    skipped = 0
    failed = 0

    for table_def in TABLES:
        name = table_def["name"]
        if name in existing:
            print(f"  ⏭️  Skipping '{name}' (already exists)")
            skipped += 1
        else:
            ok = create_table(table_def)
            if ok:
                created += 1
            else:
                failed += 1

    print(f"\nDone: {created} created, {skipped} skipped, {failed} failed")

    if failed > 0:
        print(
            "\n⚠️  Some tables could not be created automatically.\n"
            "   Your Airtable token needs these scopes:\n"
            "     • schema.bases:write\n"
            "     • schema.bases:read\n"
            "     • data.records:read\n"
            "     • data.records:write\n\n"
            "   To fix:\n"
            "   1. Go to https://airtable.com/create/tokens\n"
            "   2. Create a new token with all the scopes above\n"
            "   3. Update the AIRTABLE_API_KEY secret\n"
            "   4. Run this script again\n\n"
            "   OR create the tables manually — visit /airtable-status in the app for the schema."
        )
        sys.exit(1)
    else:
        print("\n✅ All tables ready! Your bot is fully operational.")
        print("   Next: Visit /setup-webhook to register the Telegram webhook if not done.")


if __name__ == "__main__":
    main()
