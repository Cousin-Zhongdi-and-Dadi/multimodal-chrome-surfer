import queue
import re
import threading
import uuid
from typing import Any, Callable, Dict

from browser_bridge import BrowserBridge
from config import PLUGIN_OUTPUT_ENABLED
from generic_agent_adapter import GenericAgentAdapter
from messages import (
    AGENT_ASK_USER,
    AGENT_FINAL,
    AGENT_OUTPUT,
    BROWSER_RESPONSE,
    TASK_START,
    TASK_STOP,
    USER_ANSWER,
)
from logger import build_agent_output_logger, build_logger
from native_driver import NativeMessagingDriver

logger = build_logger("agent_service")


class LocalAgentService:
    def __init__(self, send_to_extension: Callable[[Dict[str, Any]], None]):
        self.send_to_extension = send_to_extension
        self.bridge = BrowserBridge(send_to_extension)
        self.driver = NativeMessagingDriver(self.bridge)
        self.adapter = GenericAgentAdapter(self.driver, self._emit_output)
        self.agent_output_logger = build_agent_output_logger()
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.active_task_id: str | None = None
        self._lock = threading.RLock()

    def start(self) -> None:
        self.adapter.start()

    def handle_message(self, message: Dict[str, Any]) -> None:
        message_type = message.get("type")

        if message_type == "ping":
            return

        if message_type == BROWSER_RESPONSE:
            self.bridge.handle_response(message)
            return

        if message_type == TASK_START:
            self.start_task(
                message.get("taskId") or str(uuid.uuid4()),
                str(message.get("text") or ""),
            )
            return

        if message_type == TASK_STOP:
            self.stop_task(message.get("taskId"))
            return

        if message_type == USER_ANSWER:
            self.handle_user_answer(
                message.get("questionId"),
                message.get("answer"),
            )
            return

        logger.warning("Unhandled local message type: %s", message_type)

    def start_task(self, task_id: str, text: str) -> None:
        logger.info("task start task_id=%s text_chars=%s", task_id, len(text))
        if not text.strip():
            self._emit_output(task_id, "[系统] 任务内容为空\n")
            return

        if not self.adapter.is_ready():
            self._emit_output(task_id, "[系统] 本地 Generic Agent 尚未准备好\n")
            return

        if not getattr(getattr(self.adapter, "agent", None), "llmclient", None):
            self._emit_output(task_id, "[系统] 尚未配置可用的 LLM 客户端，请先准备 GenericAgent 的 mykey.py 配置\n")
            return

        try:
            output_queue = self.adapter.submit_task(text)
        except Exception as exc:
            self._emit_output(task_id, f"[系统] 提交任务失败：{exc}\n")
            return

        with self._lock:
            self.active_task_id = task_id
            self.tasks[task_id] = {
                "queue": output_queue,
                "thread": None,
                "event_buffer": "",
            }

        thread = threading.Thread(
            target=self._pump_task,
            args=(task_id, output_queue),
            name=f"task-pump-{task_id}",
            daemon=True,
        )
        with self._lock:
            self.tasks[task_id]["thread"] = thread
        thread.start()

    def stop_task(self, task_id: str | None = None) -> None:
        logger.info("task stop task_id=%s active_task_id=%s", task_id, self.active_task_id)
        self.adapter.stop()
        target_id = task_id or self.active_task_id or "task"
        self._emit_output(target_id, "\n[系统] 任务已停止\n")

    def handle_user_answer(self, question_id: str | None, answer: Any) -> None:
        answer_text = str(answer or "").strip()
        logger.info("user answer question_id=%s answer_chars=%s", question_id, len(answer_text))
        if not answer_text:
            self._emit_output(self.active_task_id, "[系统] 用户未提供回答\n")
            return

        self._emit_output(self.active_task_id, f"\n[用户] {answer_text}\n")
        self.start_task(str(uuid.uuid4()), answer_text)

    def _pump_task(self, task_id: str, output_queue: queue.Queue) -> None:
        while True:
            try:
                item = output_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            if "next" in item:
                chunk = str(item["next"])
                self._log_agent_output(task_id, chunk)
                self._forward_main_events(task_id, chunk)
                continue

            if "done" in item:
                done_text = str(item.get("done") or "")
                self._log_agent_output(task_id, done_text)
                self._forward_main_events(task_id, "", flush=True)
                final_answer = self._extract_final_answer(done_text)
                self._send_final_answer(task_id, final_answer)
                self._maybe_emit_question(task_id, done_text)
                with self._lock:
                    if self.active_task_id == task_id:
                        self.active_task_id = None
                break

    @staticmethod
    def _extract_final_answer(done_text: str) -> str:
        matches = list(re.finditer(r"LLM Running \(Turn\s+\d+\)[^\n]*", done_text))
        if matches:
            candidate = done_text[matches[-1].end():]
            if candidate.strip():
                return candidate.strip()

        return done_text.strip()

    def _log_agent_output(self, task_id: str, text: str) -> None:
        if text:
            self.agent_output_logger.info("task=%s | %s", task_id, text.rstrip("\n"))

    def _forward_main_events(self, task_id: str, text: str, flush: bool = False) -> None:
        with self._lock:
            state = self.tasks.setdefault(task_id, {})
            buffer = state.get("event_buffer", "") + text

            if text and not text.endswith(("\n", "\r")):
                lines = buffer.splitlines(keepends=True)
                state["event_buffer"] = lines.pop() if lines else ""
            else:
                lines = buffer.splitlines(keepends=True)
                state["event_buffer"] = ""

        for line in lines:
            event = self._event_from_line(line)
            if event:
                self._send_plugin_event(task_id, event)

        if flush:
            with self._lock:
                remaining = self.tasks.get(task_id, {}).get("event_buffer", "")
                if remaining:
                    self.tasks[task_id]["event_buffer"] = ""
            if remaining:
                event = self._event_from_line(remaining)
                if event:
                    self._send_plugin_event(task_id, event)

    @staticmethod
    def _event_from_line(line: str) -> str | None:
        stripped = line.strip()
        if not stripped:
            return None

        if "LLM Running" in stripped or re.search(r"\bTurn\s+\d+", stripped):
            match = re.search(r"Turn\s+(\d+)", stripped)
            if match:
                return f"[迭代] 第 {match.group(1)} 轮"
            return stripped

        tool_match = re.search(r"Tool:\s*`([^`]+)`", stripped)
        if tool_match:
            return f"[工具] {tool_match.group(1)}"

        if "Backend Error" in stripped or "Error:" in stripped:
            return f"[错误] {stripped[:240]}"

        return None

    def _maybe_emit_question(self, task_id: str, text: str) -> None:
        if "Waiting for your answer" not in text:
            return

        self.send_to_extension({
            "type": AGENT_ASK_USER,
            "questionId": task_id,
            "question": text.strip() or "Agent 请求确认",
        })

    def _emit_output(self, task_id: str | None, text: str) -> None:
        self._send_plugin_event(task_id, text)

    def _send_plugin_event(self, task_id: str | None, text: str) -> None:
        if not PLUGIN_OUTPUT_ENABLED:
            return
        if not text:
            return
        self.send_to_extension({
            "type": AGENT_OUTPUT,
            "taskId": task_id,
            "text": text,
        })

    def _send_final_answer(self, task_id: str, text: str) -> None:
        if not PLUGIN_OUTPUT_ENABLED:
            return
        if not text:
            return
        self.send_to_extension({
            "type": AGENT_FINAL,
            "taskId": task_id,
            "text": text,
        })
