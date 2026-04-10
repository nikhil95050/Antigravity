from perplexity_client import ask_perplexity, understand_user_answer, generate_explanation, translate_text

class PerplexityAdapter:
    """Adapter for Perplexity AI services."""

    def generate_titles(self, prompt: str, system: str, limit: int) -> list:
        # Business logic for title generation could move here
        # For now, it delegates to the client
        return [] # This will be filled when refactoring movie_data.py

    def normalize_answer(self, question: str, answer: str) -> str:
        return understand_user_answer(question, answer)

    def explain_recommendations(self, movies: list, context: str) -> str:
        return generate_explanation(movies, context)

    def translate(self, text: str, target_lang: str) -> str:
        return translate_text(text, target_lang)
