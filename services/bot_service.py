from services.session_service import SessionService
from services.user_service import UserService
from services.movie_service import MovieService
from services.recommendation_service import RecommendationService
from adapters.perplexity_adapter import PerplexityAdapter

class BotService:
    """Orchestration service for the Telegram Movie Bot."""

    def __init__(self):
        self.session_service = SessionService()
        self.user_service = UserService()
        self.movie_service = MovieService()
        self.recommendation_service = RecommendationService()
        self.perplexity_adapter = PerplexityAdapter()
    
    # This will be the main entry point for the business logic in Wave 3+
