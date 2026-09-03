import sys
import threading
from typing import Any, Callable

from config import GENERIC_AGENT_ROOT
from logger import build_logger

logger = build_logger("generic_agent_adapter")


class GenericAgentAdapter:
    """Wraps the cloned GenericAgent runtime and connects it to the extension bridge."""

    def __init__(
        self,
        browser_driver: Any,
        send_output: Callable[[str | None, str], None],
    ):
        self.browser_driver = browser_driver
        self.send_output = send_output
        self.agent = None
        self.agent_main = None
        self.ga_module = None
        self.run_thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def start(self) -> bool:
        with self._lock:
            if self.agent is not None:
                return True

            if not GENERIC_AGENT_ROOT.exists():
                self.send_output(None, "[本地 Agent 启动失败] 找不到 GenericAgent 目录\n")
                return False

            sys.path.insert(0, str(GENERIC_AGENT_ROOT))

            try:
                import agentmain
                import ga as ga_module

                ga_module.driver = self.browser_driver
                self._install_optimized_web_tools(ga_module)

                self.agent_main = agentmain
                self.ga_module = ga_module
                self.agent = agentmain.GeneraticAgent()

                if getattr(self.agent, "llmclients", None):
                    self.agent.next_llm(0)

                self.run_thread = threading.Thread(
                    target=self.agent.run,
                    name="generic-agent-runner",
                    daemon=True,
                )
                self.run_thread.start()
                return True
            except Exception as exc:
                logger.exception("Failed to start GenericAgent adapter")
                self.send_output(None, f"[本地 Agent 启动失败] {exc}\n")
                return False

    def is_ready(self) -> bool:
        return self.agent is not None

    def submit_task(self, text: str):
        if not self.is_ready():
            raise RuntimeError("GenericAgent adapter is not ready")
        return self.agent.put_task(text, source="extension")

    def stop(self) -> None:
        if self.agent is not None and getattr(self.agent, "is_running", False):
            self.agent.abort()

    def _install_optimized_web_tools(self, ga_module: Any) -> None:
        """Replace GenericAgent's heavy DOM-scanning web tools with lightweight bridge calls."""

        driver = self.browser_driver

        def web_scan(tabs_only=False, switch_tab_id=None, text_only=False, maxlen=35000):
            try:
                sessions = driver.get_all_sessions()
            except Exception as exc:
                return {"status": "error", "msg": str(exc)}

            if not sessions:
                return {"status": "error", "msg": "没有可用的浏览器标签页"}

            if switch_tab_id:
                driver.default_session_id = str(switch_tab_id)

            tabs = []
            for session in sessions:
                tab = {
                    "id": session.get("id"),
                    "url": session.get("url", "")[:80],
                    "title": session.get("title", "")[:80],
                }
                tabs.append(tab)

            result = {
                "status": "success",
                "metadata": {
                    "tabs_count": len(tabs),
                    "tabs": tabs,
                    "active_tab": driver.default_session_id,
                },
            }

            if not tabs_only:
                target_id = str(switch_tab_id or driver.default_session_id)
                try:
                    snapshot = driver.bridge.request(
                        "snapshot",
                        {
                            "tabId": target_id,
                            "textOnly": bool(text_only),
                            "maxElements": 120,
                        },
                    )
                    content = self._snapshot_to_text(snapshot, text_only=bool(text_only))
                except Exception as exc:
                    content = f"[页面快照失败] {exc}"
                if content:
                    result["content"] = content[:maxlen]

            return result

        def web_execute_js(script, switch_tab_id=None, no_monitor=False):
            if switch_tab_id:
                driver.default_session_id = str(switch_tab_id)

            try:
                response = driver.execute_js(script)
                return {
                    "status": "success",
                    "js_return": response.get("data"),
                    "tab_id": driver.default_session_id,
                    "newTabs": response.get("newTabs", []),
                }
            except Exception as exc:
                return {
                    "status": "failed",
                    "error": str(exc),
                    "tab_id": driver.default_session_id,
                }

        ga_module.web_scan = web_scan
        ga_module.web_execute_js = web_execute_js

    @staticmethod
    def _snapshot_to_text(snapshot: Any, text_only: bool) -> str:
        if not isinstance(snapshot, dict):
            return str(snapshot)

        if text_only:
            return snapshot.get("bodyText") or ""

        lines = [
            f"title: {snapshot.get('title', '')}",
            f"url: {snapshot.get('url', '')}",
            f"readyState: {snapshot.get('readyState', '')}",
        ]

        elements = snapshot.get("elements") or []
        lines.append(f"elements: {len(elements)}")
        for element in elements[:120]:
            text = element.get("text") or ""
            tag = element.get("tag") or ""
            selector = element.get("selector") or ""
            lines.append(
                f"[{element.get('index')}] <{tag}> {text[:120]} | {selector[:180]}"
            )

        body_text = snapshot.get("bodyText") or ""
        if body_text:
            lines.append("bodyText: " + body_text[:3000])

        return "\n".join(lines)
