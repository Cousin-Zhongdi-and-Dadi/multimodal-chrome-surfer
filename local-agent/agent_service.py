import queue
import threading
import uuid
from typing import Any, Callable, Dict

from browser_bridge import BrowserBridge
from generic_agent_adapter import GenericAgentAdapter
from messages import (
    AGENT_ASK_USER,
    AGENT_OUTPUT,
    BROWSER_RESPONSE,
    TASK_START,
    TASK_STOP,
    USER_ANSWER,
)
from logger import build_logger
from native_driver import NativeMessagingDriver

logger = build_logger("agent_service")


class LocalAgentService:
    def __init__(self, send_to_extension: Callable[[Dict[str, Any]], None]):
        self.send_to_extension = send_to_extension
        self.bridge = BrowserBridge(send_to_extension)
        self.driver = NativeMessagingDriver(self.bridge)
        self.adapter = GenericAgentAdapter(self.driver, self._emit_output)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.active_task_id: str | None = None
        self._lock = threading.RLock()

    def start(self) -> None:
        self.adapter.start()

    def handle_message(self, message: Dict[str, Any]) -> None:
        message_type = message.get("type")

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
        self.adapter.stop()
        target_id = task_id or self.active_task_id or "task"
        self._emit_output(target_id, "\n[系统] 任务已停止\n")

    def handle_user_answer(self, question_id: str | None, answer: Any) -> None:
        answer_text = str(answer or "").strip()
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
                self._emit_output(task_id, item["next"])
                continue

            if "done" in item:
                done_text = str(item.get("done") or "")
                self._emit_output(task_id, done_text)
                self._maybe_emit_question(task_id, done_text)
                with self._lock:
                    if self.active_task_id == task_id:
                        self.active_task_id = None
                break

    def _maybe_emit_question(self, task_id: str, text: str) -> None:
        if "Waiting for your answer" not in text:
            return

        self.send_to_extension({
            "type": AGENT_ASK_USER,
            "questionId": task_id,
            "question": text.strip() or "Agent 请求确认",
        })

    def _emit_output(self, task_id: str | None, text: str) -> None:
        if not text:
            return
        self.send_to_extension({
            "type": AGENT_OUTPUT,
            "taskId": task_id,
            "text": text,
        })
