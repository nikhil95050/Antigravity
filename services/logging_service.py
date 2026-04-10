import logging
import sys
import threading
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from utils.time_utils import utc_now_iso
from config.supabase_client import insert_rows, is_configured as is_supabase_configured
from pythonjsonlogger import jsonlogger
from contextvars import ContextVar

# Central context for logging interaction turns (User Input -> Bot Response)
interaction_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar("interaction_context", default=None)

# Setup standard structured logging
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            log_record['timestamp'] = utc_now_iso()
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logHandler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
    logHandler.setFormatter(formatter)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.addHandler(logHandler)
    return logger

_logger = setup_logging()

def get_logger(name):
    return logging.getLogger(name)

class BatchLogger:
    """Manages a queue of log items and flushes them in batches to Supabase."""
    def __init__(self, table_name: str, batch_size=10, flush_interval=5):
        self.table_name = table_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue = []
        self._lock = threading.Lock()
        self._timer = None
        self._shutdown = False

    def emit(self, item: dict):
        if self._shutdown: return
        with self._lock:
            self._queue.append(item)
            if len(self._queue) >= self.batch_size:
                self.flush()
            elif self._timer is None:
                self._timer = threading.Timer(self.flush_interval, self.flush)
                self._timer.daemon = True
                self._timer.start()

    def flush(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            if not self._queue:
                return
            batch = list(self._queue)
            self._queue.clear()

        try:
            if is_supabase_configured():
                # Perform insert via sync client helper
                insert_rows(self.table_name, batch)
        except Exception as e:
            _logger.error(f"[BatchLogger] Failed to flush {len(batch)} items to {self.table_name}: {e}")

    def shutdown(self):
        self._shutdown = True
        self.flush()

# Universal batch loggers
interaction_batcher = BatchLogger("user_interactions", batch_size=5, flush_interval=5)
error_batcher = BatchLogger("error_logs", batch_size=1, flush_interval=1)

class LoggingService:
    """Service for structured logging, performance profiling, and persistent stats."""
    
    _admin_repo_instance = None

    @classmethod
    def _get_admin_repo(cls):
        """Lazy load AdminRepository to break circular dependencies."""
        if cls._admin_repo_instance is None:
            from repositories.admin_repository import AdminRepository
            cls._admin_repo_instance = AdminRepository()
        return cls._admin_repo_instance

    @staticmethod
    def log_event(
        chat_id: str,
        intent: str,
        step: str,
        request_id: str = "N/A",
        provider: Optional[str] = None,
        latency_ms: Optional[int] = None,
        status: str = "success",
        error_type: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        # 1. Persistent Stats (O(1) updates)
        if step == "completed" and status == "success":
            metric_map = {
                "start": "total_sessions",
                "movie": "total_lookups",
                "trending": "total_recommendations",
                "surprise": "total_recommendations",
                "question_engine": "total_recommendations",
            }
            metric = metric_map.get(intent)
            admin_repo = LoggingService._get_admin_repo()
            if metric:
                admin_repo.increment_stat(metric)
            admin_repo.increment_stat("total_events")

        # 2. Structured JSON Logging
        log_data = {
            "chat_id": chat_id,
            "intent": intent,
            "step": step,
            "provider": provider,
            "latency_ms": latency_ms,
            "status": status,
            "error_type": error_type,
            **(extra or {})
        }
        
        if status == "error":
            _logger.error(f"Event {intent}:{step} failed", extra=log_data)
            error_batcher.emit({
                "chat_id": str(chat_id),
                "error_type": error_type or str(intent),
                "message": f"{step}: {json.dumps(extra or {})}",
                "request_id": request_id,
                "timestamp": utc_now_iso(),
            })
        elif isinstance(latency_ms, int) and latency_ms > 2000:
            _logger.warning(f"Event {intent}:{step} was slow", extra=log_data)
        else:
            _logger.info(f"Event {intent}:{step} processed", extra=log_data)

    @staticmethod
    def profile_call(chat_id, intent, step, provider, func, *args, request_id="N/A", **kwargs):
        start = time.time()
        status = "success"
        error_message = None
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            status = "error"
            error_message = str(e)
            LoggingService._get_admin_repo().log_admin_action("SYSTEM", f"ERROR:{provider}", f"{intent}.{step}: {str(e)}")
            raise e
        finally:
            latency = int((time.time() - start) * 1000)
            LoggingService.log_event(
                chat_id=chat_id, intent=intent, step=step, request_id=request_id,
                provider=provider, latency_ms=latency, status=status,
                extra={"err": error_message} if error_message else None
            )

    @staticmethod
    async def profile_call_async(chat_id, intent, step, provider, func, *args, request_id="N/A", **kwargs):
        start = time.time()
        status = "success"
        error_message = None
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            status = "error"
            error_message = str(e)
            LoggingService._get_admin_repo().log_admin_action("SYSTEM", f"ERROR:{provider}", f"{intent}.{step}: {str(e)}")
            raise e
        finally:
            latency = int((time.time() - start) * 1000)
            LoggingService.log_event(
                chat_id=chat_id, intent=intent, step=step, request_id=request_id,
                provider=provider, latency_ms=latency, status=status,
                extra={"err": error_message} if error_message else None
            )
    @staticmethod
    def log_interaction(
        chat_id: str, 
        input_text: str, 
        response_text: str, 
        intent: str, 
        latency_ms: int = 0,
        user_sent_at: str = None,
        bot_replied_at: str = None
    ):
        """Persist a full conversational turn with precise input/output timestamps."""
        interaction_batcher.emit({
            "chat_id": str(chat_id),
            "input_text": input_text[:1000] if input_text else "",
            "bot_response": response_text[:2000] if response_text else "",
            "intent": intent,
            "latency_ms": latency_ms,
            "user_sent_at": user_sent_at or utc_now_iso(),
            "bot_replied_at": bot_replied_at or utc_now_iso(),
            "timestamp": utc_now_iso() # Deprecated soon, use bot_replied_at
        })
