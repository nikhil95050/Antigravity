# Telegram Movie Recommendation Bot

## Overview
A single-application Telegram bot that provides personalized movie recommendations. Uses Flask as the web server, Airtable as the database, Apify for movie data, and Perplexity AI for natural language understanding.

## Architecture

### Single Workflow (Flask webhook server)
The entire bot logic lives in one Python application:
- **Trigger**: Telegram webhook → `/webhook/<BOT_TOKEN>`
- **Input normalization**: Extracts chat_id, username, text/callback_data
- **Intent detection**: Routes to correct handler
- **Recommendation engine**: Fetches from Apify, scores, deduplicates
- **State management**: Airtable (sessions, users, history, watchlist, trailer_cache)
- **Response**: Sends formatted HTML messages + inline buttons via Telegram Bot API

### Files
- `main.py` — Flask app, webhook endpoint, URL routing
- `intent_handler.py` — All intent handlers (start, reset, movie, history, callbacks, questioning, trending, surprise, fallback)
- `recommendation_engine.py` — Scoring, query building, Apify fetching, trailer enrichment
- `airtable_client.py` — All Airtable CRUD operations (sessions, users, history, watchlist, trailer_cache)
- `apify_client_helper.py` — Apify actor calls for movie search/details/trailers
- `perplexity_client.py` — Perplexity API for NLU, explanations, translation
- `telegram_helpers.py` — Telegram API calls (sendMessage, sendPhoto, answerCallback, setWebhook)
- `airtable_setup.py` — Setup guide and table verification

## Airtable Schema

### sessions
`chat_id, session_state, question_index, pending_question, answers_mood, answers_genre, answers_language, answers_era, answers_context, answers_avoid, last_recs_json, sim_depth, last_active, updated_at`

### users
`chat_id, username, preferred_genres, disliked_genres, preferred_language, preferred_era, watch_context, avg_rating_preference, updated_at`

### history
`chat_id, movie_id, title, year, genres, language, rating, recommended_at, watched, watched_at`

### watchlist
`chat_id, movie_id, title, year, language, rating, genres`

### trailer_cache
`movie_id, trailer_url, cached_at`

## Environment Variables / Secrets Required
- `TELEGRAM_BOT_TOKEN` — From @BotFather
- `AIRTABLE_API_KEY` — Airtable personal access token
- `AIRTABLE_BASE_ID` — Airtable base ID (starts with `app...`)
- `APIFY_API_TOKEN` — Apify API token
- `PERPLEXITY_API_KEY` — Perplexity API key

## Setup Steps
1. Create all 5 Airtable tables with fields listed above
2. Visit `/setup-webhook` to register the Telegram webhook
3. Visit `/airtable-status` to verify all tables are accessible
4. Test with `/start` in Telegram

## Supported Intents
- `/start` — Begin question flow (6 questions: mood, genre, language, era, context, avoid)
- `/reset` — Clear session
- `/help` — Show command list
- `/movie [title]` — Look up specific movie + similar
- `/history` — View last 20 recommendations
- `trending` — Popular movies via Apify
- `surprise` — Random diverse picks
- Callbacks: `watched_`, `like_`, `dislike_`, `save_`, `more_like_`

## Key Design Decisions
- Uses Airtable instead of Supabase (as specified)
- Apify IMDB scraper for real movie data
- Perplexity for NLU of free-text answers and recommendation explanations
- Sim depth guard: stops similarity loops after 2 levels
- Trailer cache prevents repeated Apify calls
- Thread-per-update for non-blocking webhook responses
- Session stored per chat_id with upsert pattern

## Running
```
python main.py
```
Server runs on port 5000. After start, visit `/setup-webhook` once to register with Telegram.
