export const NATIVE_HOST_NAME = "com.multimodal.browser_agent";

export const MSG = Object.freeze({
  TASK_START: "task.start",
  TASK_STOP: "task.stop",
  USER_ANSWER: "user.answer",
  NATIVE_STATUS: "native.status",
  AGENT_OUTPUT: "agent.output",
  AGENT_ASK_USER: "agent.ask_user",
  BROWSER_REQUEST: "browser.request",
  BROWSER_RESPONSE: "browser.response",
  SIDEPANEL_READY: "sidepanel.ready",
  OFFSCREEN_PING: "offscreen.ping"
});

export function newId() {
  return `${Date.now().toString(36)}-${crypto.randomUUID()}`;
}

export function backgroundMessage(type, payload = {}) {
  return { target: "background", type, ...payload };
}

export function sidepanelMessage(type, payload = {}) {
  return { target: "sidepanel", type, ...payload };
}
