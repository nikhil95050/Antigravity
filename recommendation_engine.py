"""
Recommendation engine configuration.
"""

QUESTIONS = [
    ("mood",     "How are you feeling right now? Pick your mood:", ["Happy", "Sad", "Excited", "Relaxed", "Vibrant", "Dark"]),
    ("genre",    "What genres do you enjoy? (Multi-select, then tap Done)", ["Action", "Comedy", "Drama", "Sci-Fi", "Horror", "Romance", "Thriller", "Animation"]),
    ("language", "What language do you prefer for movies?", ["English", "Spanish", "Hindi", "French", "Japanese", "Korean"]),
    ("era",      "Any preferred era?", ["Modern (2020s)", "Recent (2010s)", "2000s", "Classic (90s/80s)", "Vintage"]),
    ("context",  "Who are you watching with?", ["Alone", "With Family", "With Friends", "Date Night"]),
    ("time",     "How much time do you have?", ["Under 90m", "Standard (2h)", "Epic (2.5h+)", "No limit"]),
    ("avoid",    "Any genres/themes you want to avoid? (Type them or tap Skip)", []),
    ("favorites","Name some all-time favorite movies, actors, or directors (Type or Skip)", []),
]

QUESTION_KEYS = [q[0] for q in QUESTIONS]

def get_next_question(question_index: int):
    if question_index < len(QUESTIONS):
        return QUESTIONS[question_index]
    return None

from services.recommendation_service import RecommendationService

def run_recommendation(session: dict, user: dict, mode: str = "question_engine",
                        seed_title: str = None, sim_depth: int = 0) -> list:
    return RecommendationService().get_recommendations(session, user, mode, seed_title, sim_depth)

def lookup_movie(title: str) -> list:
    return RecommendationService().lookup_movie_context(title)
