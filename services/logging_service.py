import json
import time
from datetime import datetime
from typing import Optional, Dict, Any
from repositories.admin_repository import AdminRepository

class LoggingService:
    """Service for structured logging, performance profiling, and persistent stats."""
    
    _admin_repo = AdminRepository()

    @staticmethod
    def log_event(
        chat_id: str,
        intent: str,
        step: str,
        request_id: str,
        provider: Optional[str] = None,
        latency_ms: Optional[int] = None,
        status: str = "success",
        error_type: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        # 1. Increment Persistent Stats if it's a completion event
        if step == "completed" and status == "success":
            # Map intents to metrics
            metric_map = {
                "start": "total_sessions",
                "movie": "total_lookups",
                "trending": "total_recommendations",
                "surprise": "total_recommendations",
                "question_engine": "total_recommendations",
            }
            metric = metric_map.get(intent)
            if metric:
                LoggingService._admin_repo.increment_stat(metric)
            LoggingService._admin_repo.increment_stat("total_events")

        # 2. Console Logging
        perf_tag = f" [{latency_ms}ms]" if latency_ms is not None else ""
        provider_tag = f" <{provider}>" if provider else ""
        print(f"[EVENT]{perf_tag}{provider_tag} {intent}:{step} -> {status}")
        
        if status == "error" or latency_ms and latency_ms > 2000:
            print(f"  +- Data: {json.dumps(extra)}")

    @staticmethod
    def profile_call(chat_id: str, intent: str, step: str, provider: str, func, *args, **kwargs):
        """Wraps a function call to profile its latency and report results."""
        start = time.time()
        status = "success"
        error_message = None
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            status = "error"
            error_message = str(e)
            from airtable_client import log_error
            log_error(chat_id, f"{intent}.{step}", intent, "api_error", str(e), raw_payload={"provider": provider})
            raise e
        finally:
            latency = int((time.time() - start) * 1000)
            LoggingService.log_event(
                chat_id=chat_id,
                intent=intent,
                step=step,
                request_id="PROF",
                provider=provider,
                latency_ms=latency,
                status=status,
                extra={"error_message": error_message} if error_message else None
            )
