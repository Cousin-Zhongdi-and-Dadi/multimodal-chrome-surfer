import time
from typing import Any

from browser_bridge import BrowserBridge, BrowserBridgeError
from config import DEFAULT_BROWSER_TIMEOUT_SECONDS
from logger import build_logger

logger = build_logger("native_driver")


class NativeMessagingDriver:
    """A TMWebDriver-compatible facade backed by the Chrome extension."""

    def __init__(self, bridge: BrowserBridge):
        self.bridge = bridge
        self.default_session_id: str | None = None
        self.latest_session_id: str | None = None

    def get_all_sessions(self) -> list[dict[str, Any]]:
        started_at = time.monotonic()
        tabs = self.bridge.request("list_tabs") or []
        sessions = []

        for tab in tabs:
            session = {
                "id": str(tab.get("id")),
                "url": tab.get("url", ""),
                "title": tab.get("title", ""),
                "active": bool(tab.get("active")),
            }
            sessions.append(session)
            self.latest_session_id = session["id"]
            if session["active"] or self.default_session_id is None:
                self.default_session_id = session["id"]

        logger.info(
            "list_tabs done tab_count=%s elapsed_ms=%.1f",
            len(sessions),
            (time.monotonic() - started_at) * 1000,
        )
        return sessions

    def get_session_dict(self) -> dict[str, str]:
        return {session["id"]: session["url"] for session in self.get_all_sessions()}

    def find_session(self, url_pattern: str) -> list[tuple[str, dict[str, Any]]]:
        matches = []
        for session in self.get_all_sessions():
            if not url_pattern or url_pattern in session["url"]:
                matches.append((session["id"], session))
        return matches

    def set_session(self, url_pattern: str) -> str | None:
        matches = self.find_session(url_pattern)
        if not matches:
            return None
        self.default_session_id = matches[0][0]
        return self.default_session_id

    def execute_js(
        self,
        code: str,
        timeout: float = DEFAULT_BROWSER_TIMEOUT_SECONDS,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        target_id = str(session_id or self.default_session_id)
        if not target_id or target_id == "None":
            raise ValueError("No active browser tab available")

        started_at = time.monotonic()
        result = self.bridge.request(
            "execute_js",
            {"tabId": target_id, "code": code},
            timeout=timeout,
        )
        logger.info(
            "execute_js done target_tab=%s code_chars=%s elapsed_ms=%.1f",
            target_id,
            len(code),
            (time.monotonic() - started_at) * 1000,
        )

        if isinstance(result, dict):
            if result.get("ok") is False:
                raise BrowserBridgeError(str(result.get("error")))
            value = result.get("value")
        else:
            value = result

        return {
            "data": value,
            "newTabs": (result or {}).get("newTabs", []) if isinstance(result, dict) else [],
        }

    def jump(self, url: str, timeout: float = 10) -> dict[str, Any]:
        return self.execute_js(f"window.location.href={url!r}", timeout=timeout)
