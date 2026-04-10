from repositories.session_repository import SessionRepository
from repositories.user_repository import UserRepository
from repositories.history_repository import HistoryRepository
from repositories.watchlist_repository import WatchlistRepository
from repositories.feedback_repository import FeedbackRepository
from repositories.api_usage_repository import ApiUsageRepository
from repositories.trailer_repository import TrailerRepository
from repositories.admin_repository import AdminRepository
from repositories.metadata_repository import MetadataRepository

from services.session_service import SessionService
from services.user_service import UserService
from services.movie_service import MovieService
from services.recommendation_service import RecommendationService
from services.health_service import HealthService
from services.discovery_service import DiscoveryService
from services.logging_service import get_logger, interaction_batcher, error_batcher

import httpx
import os
import asyncio

logger = get_logger("container")

class ServiceContainer:
    def __init__(self):
        # 1. Repositories (Base dependencies)
        self.session_repo = SessionRepository()
        self.user_repo = UserRepository()
        self.history_repo = HistoryRepository()
        self.watchlist_repo = WatchlistRepository()
        self.feedback_repo = FeedbackRepository()
        self.usage_repo = ApiUsageRepository()
        self.trailer_repo = TrailerRepository()
        self.admin_repo = AdminRepository()
        self.metadata_repo = MetadataRepository()

        # 2. Shared Clients
        self.shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10)
        )
        
        from clients.watchmode_client import WatchmodeClient
        self.watchmode_client = WatchmodeClient(shared_client=self.shared_client)

        # 3. Services (With Injection)
        self.session_service = SessionService(session_repo=self.session_repo)
        self.user_service = UserService(user_repo=self.user_repo)
        
        self.movie_service = MovieService(
            history_repo=self.history_repo,
            watchlist_repo=self.watchlist_repo
        )
        
        self.discovery_service = DiscoveryService(shared_client=self.shared_client)
        
        self.rec_service = RecommendationService(
            watchmode_client=self.watchmode_client,
            trailer_repo=self.trailer_repo,
            discovery_service=self.discovery_service
        )
        
        self.health_service = HealthService()

    async def teardown(self):
        """Graceful shutdown of all shared resources."""
        logger.info("Starting container teardown...")
        
        # 1. Close HTTP clients
        await self.shared_client.aclose()
        
        # 2. Close Telegram client
        try:
            from clients.telegram_helpers import _client as telegram_client
            await telegram_client.aclose()
            logger.info("Telegram client closed.")
        except Exception as e:
            logger.error(f"Error closing Telegram client: {e}")

        # 3. Shutdown Logging Batchers
        try:
            interaction_batcher.shutdown()
            error_batcher.shutdown()
            logger.info("Logging batchers shut down.")
        except Exception as e:
            logger.error(f"Error shutting down batchers: {e}")

        # 4. Close Supabase clients
        try:
            from config.supabase_client import _async_client, _sync_client
            await _async_client.aclose()
            _sync_client.close()
            logger.info("Supabase clients closed.")
        except Exception as e:
            logger.error(f"Error closing Supabase clients: {e}")

        logger.info("Container teardown complete.")

# Singleton instance
container = ServiceContainer()

# Legacy aliases for backward compatibility
session_service = container.session_service
user_service = container.user_service
movie_service = container.movie_service
rec_service = container.rec_service
discovery_service = container.discovery_service
admin_repo = container.admin_repo
feedback_repo = container.feedback_repo
usage_repo = container.usage_repo
watchlist_repo = container.watchlist_repo
history_repo = container.history_repo
trailer_repo = container.trailer_repo
shared_client = container.shared_client
health_service = container.health_service
watchmode_client = container.watchmode_client
metadata_repo = container.metadata_repo
