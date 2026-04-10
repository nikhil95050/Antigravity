import os
import requests
import hashlib
from airtable_client import log_error
from app_config import is_feature_enabled
from redis_cache import get_json, set_json

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

def _should_retry(status_code: int) -> bool:
    return status_code in (429, 500, 502, 503, 504)

def _extract_content(data: dict) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    return content.strip() if isinstance(content, str) else ""

def ask_perplexity(prompt: str, system: str = "", model: str = "sonar") -> str:
    """Send a prompt to Perplexity and return the response text."""
    if not is_feature_enabled("perplexity"):
        return ""
    if not PERPLEXITY_API_KEY:
        log_error("", "perplexity.ask_perplexity", "", "missing_api_key", "PERPLEXITY_API_KEY missing", raw_payload={"model": model})
        return ""

    cache_key = "px_" + hashlib.md5((model + system + prompt).encode()).hexdigest()
    cached = get_json(cache_key)
    if cached:
        return cached

    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in ("first", "retry"):
            try:
                resp = requests.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json={"model": model, "messages": messages},
                    timeout=20,
                )

                status = resp.status_code
                try:
                    data = resp.json()
                except Exception:
                    data = None

                if status == 200 and isinstance(data, dict):
                    content = _extract_content(data)
                    
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", 0)
                    
                    from repositories.api_usage_repository import ApiUsageRepository
                    ApiUsageRepository().log_usage(
                        provider="Perplexity",
                        action="ask_perplexity",
                        chat_id="system",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens
                    )
                    
                    if content:
                        set_json(cache_key, content, ttl=86400 * 7)
                        return content
                    last_error = {"status_code": status, "error": "missing_content", "json": data}
                else:
                    last_error = {"status_code": status, "text": resp.text[:500], "json": data if isinstance(data, dict) else None}

                if attempt == "first" and _should_retry(status):
                    continue

                log_error(
                    "",
                    "perplexity.ask_perplexity",
                    "",
                    "perplexity_api_failed",
                    f"Perplexity failed with status {status}",
                    raw_payload={"model": model, "prompt": prompt[:800], "system": system[:800], "response": last_error},
                    retry_status="retried" if attempt == "retry" else "not_retried",
                    resolution_status="open",
                )
                return ""
            except Exception as e:
                if attempt == "first":
                    continue
                log_error(
                    "",
                    "perplexity.ask_perplexity",
                    "",
                    "perplexity_request_exception",
                    str(e),
                    raw_payload={"model": model, "prompt": prompt[:800], "system": system[:800]},
                    retry_status="retried",
                    resolution_status="open",
                )
                return ""
        return ""
    except Exception as e:
        log_error("", "perplexity.ask_perplexity", "", "unhandled_exception", str(e), raw_payload={"model": model})
        return ""

def understand_user_answer(question: str, answer: str) -> str:
    """Use Perplexity to normalize/understand a user's free-text answer."""
    prompt = (
        f"A user was asked: '{question}'\n"
        f"They replied: '{answer}'\n"
        f"Extract the key intent in 3-5 words. Return only the extracted phrase, nothing else."
    )
    result = ask_perplexity(prompt)
    return result or answer

def generate_explanation(movies: list, context: str) -> str:
    """Generate a brief explanation for why these movies were recommended."""
    titles = ", ".join([m.get("title", "") for m in movies[:5]])
    prompt = (
        f"In 2 sentences, explain why someone who {context} would enjoy: {titles}. "
        f"Be warm, concise, and enthusiastic."
    )
    return ask_perplexity(prompt)

def translate_text(text: str, target_lang: str) -> str:
    """Translate text to a target language."""
    prompt = f"Translate the following to {target_lang}. Return only the translation:\n\n{text}"
    return ask_perplexity(prompt)
