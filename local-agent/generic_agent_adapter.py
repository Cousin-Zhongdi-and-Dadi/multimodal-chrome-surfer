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
