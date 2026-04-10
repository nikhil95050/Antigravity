import json
import re
from typing import Optional
from services.logging_service import get_logger

logger = get_logger("semantic_service")

class SemanticService:
    """Service for classifying natural language inputs into structured bot intents."""
    
    INTENT_DESCRIPTIONS = {
        "start": "Initialize the bot, show welcome message, or start the movie questionnaire.",
        "trending": "Show currently popular or trending movies.",
        "surprise": "Suggest hidden gems or underrated movies.",
        "watchlist": "View or manage the user's saved watchlist.",
        "history": "View movies the user has already seen or liked.",
        "movie_search": "Find a specific movie by name or description.",
        "help": "Explain how the bot works or show command list."
    }

    @staticmethod
    async def classify_intent(text: str, chat_id: str = "system") -> Optional[str]:
        """Uses Perplexity to categorize natural language into a bot intent."""
        from config.redis_cache import get_json, set_json
        import hashlib
        
        # 1. Cache Check
        clean_text = text.lower().strip()
        text_hash = hashlib.sha256(clean_text.encode()).hexdigest()
        cache_key = f"semantic_intent:{text_hash}"
        cached = get_json(cache_key)
        if cached:
            return cached if cached != "unknown" else None

        # 2. Perplexity Classification
        from clients.perplexity_client import ask_perplexity
        
        prompt = (
            f"You are a routing engine for a Movie Recommendation Bot. "
            f"Classify the following user message into exactly ONE of these categories: "
            f"{', '.join(SemanticService.INTENT_DESCRIPTIONS.keys())}, or 'unknown'.\n\n"
            f"User message: '{text}'\n\n"
            f"Return ONLY the category name as a single word."
        )
        
        raw_output = await ask_perplexity(prompt, chat_id=chat_id)
        if not raw_output:
            return None
            
        # Clean response
        classified = raw_output.lower().strip().split('\n')[0].strip('., ')
        
        # Validate against known intents
        final_intent = None
        if classified in SemanticService.INTENT_DESCRIPTIONS:
            # Map movie_search to 'search' for compatibility
            final_intent = "search" if classified == "movie_search" else classified
        
        # 3. Store result (even unknown) to avoid re-calls
        set_json(cache_key, final_intent or "unknown", ttl=86400) # 24h cache
        
        logger.info(f"Classified '{text[:20]}...' as '{final_intent}'")
        return final_intent
