import threading
import time
import uuid
from typing import Any, Callable, Dict

from config import DEFAULT_BROWSER_TIMEOUT_SECONDS
from messages import browser_request
from logger import build_logger

logger = build_logger("browser_bridge")


class BrowserBridgeError(RuntimeError):
    pass


class BrowserBridge:
    def __init__(self, sender: Callable[[Dict[str, Any]], None]):
        self.sender = sender
        self._lock = threading.RLock()
        self._pending: Dict[str, tuple[threading.Event, Dict[str, Any]]] = {}

    def request(
        self,
        method: str,
        params: Dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        request_id = str(uuid.uuid4())
        event = threading.Event()
        result_box: Dict[str, Any] = {}
        timeout = timeout or DEFAULT_BROWSER_TIMEOUT_SECONDS
        started_at = time.monotonic()
        logger.info(
            "browser request start request_id=%s method=%s timeout=%s",
            request_id,
            method,
            timeout,
        )

        with self._lock:
            self._pending[request_id] = (event, result_box)

        try:
            self.sender(browser_request(request_id, method, params))
        except Exception as exc:
            with self._lock:
                self._pending.pop(request_id, None)
            logger.exception(
                "browser request send failed request_id=%s method=%s",
                request_id,
                method,
            )
            raise BrowserBridgeError(f"Failed to send browser request: {exc}") from exc

        if not event.wait(timeout):
            with self._lock:
                self._pending.pop(request_id, None)
            logger.warning(
                "browser request timed out request_id=%s method=%s elapsed_ms=%.1f",
                request_id,
                method,
                (time.monotonic() - started_at) * 1000,
            )
            raise TimeoutError(f"Browser request timed out: method={method}")

        if not result_box.get("ok"):
            error = result_box.get("error")
            logger.warning(
                "browser request failed request_id=%s method=%s error=%s elapsed_ms=%.1f",
                request_id,
                method,
                error,
                (time.monotonic() - started_at) * 1000,
            )
            raise BrowserBridgeError(str(error))

        logger.info(
            "browser request done request_id=%s method=%s elapsed_ms=%.1f",
            request_id,
            method,
            (time.monotonic() - started_at) * 1000,
        )
        return result_box.get("result")

    def handle_response(self, message: Dict[str, Any]) -> None:
        request_id = message.get("requestId")
        if not request_id:
            return

        with self._lock:
            pending = self._pending.pop(request_id, None)

        if not pending:
            logger.warning("Received response for unknown browser request: %s", request_id)
            return

        event, result_box = pending
        result_box["ok"] = message.get("ok", False)
        result_box["result"] = message.get("result")
        result_box["error"] = message.get("error")
        event.set()
