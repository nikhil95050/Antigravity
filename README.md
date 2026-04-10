# 🎬 Movie Bot: High-Performance Recommendation System

A production-grade Telegram bot that delivers personalized movie recommendations with extreme speed using an asynchronous "Fan-Out" architecture.

## 🚀 Key Features

### 🧠 Advanced Recommendation Engine
*   **Question Engine**: An interactive 8-question survey that analyzes mood, genre, era, and context to provide hyper-personalized suggestions.
*   **Similarity Search**: Find movies similar to your favorites using Perplexity AI.
*   **Trending & Surprise Me**: Discover currently popular movies or hidden gems from around the world.
*   **AI Explanations**: Every recommendation comes with a 2-sentence explanation of why it fits your specific vibe.

### ⚡ Performance & Scalability
*   **< 3s Latency**: Optimized pipeline for individual movie lookups.
*   **Async Fan-Out**: Concurrent fetching of trailers (YouTube), streaming availability (Watchmode), and metadata (OMDb).
*   **Shared Connection Pooling**: Reuses TLS connections to minimize network overhead.
*   **Candidate Buffering**: Fetches 14 candidates but displays 5 at a time. The "More Suggestions" button provides near-instant access to the remaining 9 without hitting the AI again.
*   **Multi-Layer Caching**: Tiered strategy using Redis (L2) and ultra-fast in-memory storage (L1).

### 📺 Rich Media & Localization
*   **Instant Media**: Auto-generated posters and official trailer links.
*   **Streaming Availability**: India-specific streaming results (`regions=IN`) for platforms like Netflix, Prime Video, and Disney+.
*   **Global Search**: Integrated OMDb data for accurate ratings and actors.

### 🛡️ Admin & Management
*   **Admin Dashboard**: `/admin_stats`, `/admin_health`, and `/admin_clear_cache`.
*   **Circuit Breakers**: Restricted commands to manually disable/enable API providers (e.g., Perplexity, Watchmode) in case of downtime.
*   **Error Auditing**: `/admin_errors` to retrieve the most recent system exceptions directly from the database.
*   **Security**: Restricted access to admin commands based on authorized Chat IDs.

---

## 🏗️ Technical Stack
- **Core**: Python (Asynchronous asyncio/httpx)
- **AI**: Perplexity SONAR (LLM)
- **Database**: Supabase (Unified storage for Users, Sessions, Logs, and Audit Trails)
- **Caching**: Upstash Redis + Local Memory
- **APIs**: Watchmode (Streaming), OMDb (Metadata)

---

## 🧪 Testing Suite
The bot includes a robust E2E test suite:
- `tests/test_infrastructure.py`: Validates DB and Cache connectivity.
- `tests/test_e2e_user.py`: Verifies latency and recommendation logic.
- `tests/test_e2e_admin.py`: Tests security and admin tools.

---

## 🛠️ Commands
- `/start`: Begin the interactive recommendation questionnaire.
- `/trending`: See what's popular now.
- `/surprise`: Get a diverse "hidden gem" recommendation.
- `/admin_stats`: (Admin only) View bot usage metrics.
- `/admin_health`: (Admin only) Check service uptimes.
- `/admin_errors`: (Admin only) View recent system failures.
- `/admin_disable_provider`: (Admin only) Toggle a feature/provider OFF manually.
