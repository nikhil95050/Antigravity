import os
import requests

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

def ask_perplexity(prompt: str, system: str = "", model: str = "sonar") -> str:
    """Send a prompt to Perplexity and return the response text."""
    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"[Perplexity] Error {resp.status_code}: {resp.text[:200]}")
            return ""
    except Exception as e:
        print(f"[Perplexity] ask_perplexity error: {e}")
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
