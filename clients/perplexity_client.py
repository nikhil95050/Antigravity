import os
import re
import hashlib
import json
import asyncio
import httpx
from services.logging_service import LoggingService, get_logger
from config.app_config import is_feature_enabled
from config.redis_cache import get_json, set_json

logger = get_logger("perplexity")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "").strip()

# Shared client to avoid connection overhead
_client = httpx.AsyncClient(timeout=30.0)

def _extract_content(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _normalize_prompt(prompt: str) -> str:
    prompt = prompt.lower().strip()
    prompt = re.sub(r'\b(recommend|suggest|give me|list)\b', 'list', prompt)
    return prompt

DAILY_TOKEN_CAP = 500000 # ~0.5M tokens per day

async def _is_budget_ok() -> bool:
    """Check if the daily Perplexity token budget has been exceeded."""
    from config.redis_cache import get_redis
    client = get_redis()
    if not client: return True
    try:
        usage = client.get("px_tokens_today")
        if usage and int(usage) >= DAILY_TOKEN_CAP:
            return False
        return True
    except:
        return True

async def ask_perplexity(prompt: str, system: str = "", model: str = "sonar", chat_id: str = "system") -> str:
    """Async: Send a prompt to Perplexity with exponential backoff and caching."""
    if not is_feature_enabled("perplexity") or not PERPLEXITY_API_KEY:
        return ""
    
    if not await _is_budget_ok():
        logger.warning(f"Perplexity daily budget exceeded ({DAILY_TOKEN_CAP} tokens). Blocked {chat_id}")
        return ""

    normalized = _normalize_prompt(prompt)
    if not system:
        system = "You are a movie recommendation assistant. Always respond with valid JSON arrays of strings only."

    cache_key = "px_" + hashlib.md5((model + system + normalized).encode()).hexdigest()
    cached = get_json(cache_key)
    if cached: return cached

    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
    messages = []
    if system: messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    backoff = 1
    for attempt in range(3):
        try:
            resp = await _client.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages},
            )
            if resp.status_code == 200:
                data = resp.json()
                content = _extract_content(data)
                
                usage = data.get("usage", {})
                total = usage.get("total_tokens", 0)
                from repositories.api_usage_repository import ApiUsageRepository
                from config.redis_cache import get_redis
                ApiUsageRepository().log_usage(
                    provider="Perplexity", action="ask_perplexity",
                    chat_id=chat_id,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=total
                )
                
                # Update daily budget counter
                client = get_redis()
                if client:
                    try:
                        new_usage = client.incrby("px_tokens_today", total)
                        if new_usage == total:
                            client.expire("px_tokens_today", 86400)
                    except: pass
                
                if content:
                    set_json(cache_key, content, ttl=86400 * 7)
                    return content
            
            if resp.status_code in (429, 500, 502, 503, 504):
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            break
        except Exception:
            await asyncio.sleep(backoff)
            backoff *= 2
    return ""

async def understand_user_answer(question, answer, chat_id="system"):
    system = "You are a movie expert. Normalize the user's free-text answer into a concise, searchable category or list."
    prompt = f"Question: {question}\nUser said: {answer}\nReturn ONLY the normalized answer."
    return await ask_perplexity(prompt, system, chat_id=chat_id)

async def generate_explanation(movies, context, chat_id="system"):
    system = "You are a movie critic. Explain why these movies were chosen."
    prompt = f"Movies: {movies}\nContext: {context}\nProvide a 2-sentence explanation of why these fit."
    return await ask_perplexity(prompt, system, chat_id=chat_id)

async def translate_text(text, target_lang, chat_id="system"):
    system = f"You are a translator. Translate to {target_lang}."
    prompt = f"Text: {text}"
    return await ask_perplexity(prompt, system, chat_id=chat_id)
