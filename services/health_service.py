import time
import threading
from typing import Dict, List
from app_config import is_feature_enabled, set_feature_flag
from repositories.admin_repository import AdminRepository

class HealthService:
    """Service for monitoring provider health and managing circuit breakers with persistence."""
    
    _admin_repo = AdminRepository()
    _failure_counts = {}
    _last_failure_time = {}
    _lock = threading.Lock()
    THRESHOLD = 3
    RECOVERY_TIME = 300 # 5 minutes

    @classmethod
    def _ensure_loaded(cls):
        """Synchronize in-memory state with the Admin Database on first access."""
        with cls._lock:
            if not cls._failure_counts:
                states = cls._admin_repo.get_provider_health()
                for s in states:
                    p = s["provider_name"]
                    cls._failure_counts[p] = s["failure_count"]
                    # Convert ISO string to timestamp if needed
                    cls._last_failure_time[p] = time.time() # Approximation for initial load
                    if not s["is_enabled"]:
                        set_feature_flag(p, False)

    @classmethod
    def report_failure(cls, provider: str):
        cls._ensure_loaded()
        with cls._lock:
            cls._failure_counts[provider] = cls._failure_counts.get(provider, 0) + 1
            last_failure_at = time.time()
            cls._last_failure_time[provider] = last_failure_at
            
            is_enabled = True
            if cls._failure_counts[provider] >= cls.THRESHOLD:
                print(f"[Health] Circuit broken for {provider}. Disabling feature.")
                set_feature_flag(provider, False)
                is_enabled = False

        # Persist to DB outside the lock to avoid blocking
        cls._admin_repo.update_provider_health(
            provider_name=provider,
            is_enabled=is_enabled,
            failure_count=cls._failure_counts[provider],
            last_failure_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(last_failure_at))
        )

    @classmethod
    def is_healthy(cls, provider: str) -> bool:
        cls._ensure_loaded()
        if not is_feature_enabled(provider):
            with cls._lock:
                last_fail = cls._last_failure_time.get(provider, 0)
            if time.time() - last_fail > cls.RECOVERY_TIME:
                print(f"[Health] Attempting recovery for {provider}.")
                cls.report_success(provider)
                return True
            return False
        return True

    @classmethod
    def report_success(cls, provider: str):
        cls._ensure_loaded()
        with cls._lock:
            needs_update = cls._failure_counts.get(provider, 0) > 0
            if needs_update:
                cls._failure_counts[provider] = 0
                set_feature_flag(provider, True)

        if needs_update:
            cls._admin_repo.update_provider_health(
                provider_name=provider,
                is_enabled=True,
                failure_count=0,
                last_failure_at=None
            )
