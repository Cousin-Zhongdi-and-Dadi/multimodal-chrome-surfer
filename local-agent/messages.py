from typing import Any, Dict


TASK_START = "task.start"
TASK_STOP = "task.stop"
USER_ANSWER = "user.answer"
NATIVE_STATUS = "native.status"
AGENT_OUTPUT = "agent.output"
AGENT_ASK_USER = "agent.ask_user"
BROWSER_REQUEST = "browser.request"
BROWSER_RESPONSE = "browser.response"


def browser_request(request_id: str, method: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "type": BROWSER_REQUEST,
        "requestId": request_id,
        "method": method,
        "params": params or {},
    }


def browser_response(request_id: str, ok: bool, result: Any = None, error: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": BROWSER_RESPONSE,
        "requestId": request_id,
        "ok": ok,
    }
    if ok:
        payload["result"] = result
    else:
        payload["error"] = error
    return payload
