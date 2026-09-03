import { MSG, backgroundMessage, newId } from "./protocol.js";

const taskInput = document.getElementById("task");
const sendButton = document.getElementById("send");
const stopButton = document.getElementById("stop");
const statusElement = document.getElementById("status");
const outputElement = document.getElementById("output");
const workingIndicator = document.getElementById("working-indicator");

const activityElement = document.createElement("div");
activityElement.className = "activity-card";
activityElement.hidden = true;

let activeTaskId = null;
let isRunning = false;

sendButton.addEventListener("click", submitTask);
stopButton.addEventListener("click", stopTask);
taskInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitTask();
  }
});
taskInput.addEventListener("input", autoResize);

function autoResize() {
  taskInput.style.height = "auto";
  taskInput.style.height = `${Math.min(taskInput.scrollHeight, 200)}px`;
}

autoResize();

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.target !== "sidepanel") {
    return;
  }

  switch (message.type) {
    case MSG.NATIVE_STATUS:
      setStatus(message.connected);
      break;
    case MSG.AGENT_OUTPUT:
      addOutputMessage(message.text || "");
      break;
    case MSG.AGENT_FINAL:
      hideActivity();
      hideWorking();
      setRunning(false);
      addMessage("assistant", message.text || "");
      break;
    case MSG.AGENT_ASK_USER:
      hideActivity();
      renderQuestion(message);
      break;
    default:
      break;
  }
});

function submitTask() {
  if (isRunning) {
    return;
  }

  const text = taskInput.value.trim();
  if (!text) {
    return;
  }

  activeTaskId = newId();
  taskInput.value = "";
  hideActivity();
  showWorking();
  setRunning(true);
  addMessage("user", text);
  ensureActivityInStream();
  sendMessage(backgroundMessage(MSG.TASK_START, {
    taskId: activeTaskId,
    text
  }));
}

function stopTask() {
  if (!activeTaskId) {
    return;
  }

  sendMessage(backgroundMessage(MSG.TASK_STOP, {
    taskId: activeTaskId
  }));
  hideWorking();
  setRunning(false);
  updateActivity("任务已停止");
}

function setRunning(running) {
  isRunning = Boolean(running);
  sendButton.disabled = isRunning;
  stopButton.disabled = !isRunning;
}

function setStatus(connected) {
  const statusText = statusElement.querySelector(".status-text");
  statusText.textContent = connected ? "已连接" : "未连接";
  statusElement.classList.toggle("connected", Boolean(connected));
  statusElement.classList.toggle("disconnected", !connected);
}

function sendMessage(message) {
  chrome.runtime.sendMessage(message).catch((error) => {
    updateActivity(`错误：${error.message}`, "error");
  });
}

function addOutputMessage(text) {
  const trimmed = text.trim();
  if (!trimmed) {
    return;
  }

  if (trimmed.startsWith("[错误]")) {
    updateActivity(trimmed.replace(/^\[错误\]\s*/, ""), "error");
    return;
  }

  if (trimmed.startsWith("[系统]")) {
    updateActivity(trimmed.replace(/^\[系统\]\s*/, ""));
    return;
  }

  if (trimmed.startsWith("[迭代]") || trimmed.startsWith("[工具]")) {
    updateActivity(trimmed.replace(/^\[(迭代|工具)\]\s*/, ""));
    return;
  }

  updateActivity(trimmed);
}

function addMessage(kind, text) {
  const row = document.createElement("div");
  row.className = `row ${kind}`;

  if (kind === "user") {
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = "你";
    row.appendChild(meta);
  }

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (kind === "assistant") {
    bubble.innerHTML = renderMarkdown(text);
  } else {
    bubble.textContent = text;
  }
  row.appendChild(bubble);

  outputElement.appendChild(row);
  outputElement.scrollTop = outputElement.scrollHeight;
}

function updateActivity(text, kind = "tool") {
  ensureActivityInStream();
  activityElement.hidden = false;
  activityElement.textContent = text;
  activityElement.className = `activity-card${kind === "error" ? " error" : ""}`;
  outputElement.scrollTop = outputElement.scrollHeight;
}

function hideActivity() {
  activityElement.hidden = true;
  activityElement.textContent = "";
  activityElement.className = "activity-card";
  activityElement.remove();
}

function ensureActivityInStream() {
  if (activityElement.parentElement !== outputElement) {
    outputElement.appendChild(activityElement);
  }
}

function showWorking() {
  workingIndicator.hidden = false;
}

function hideWorking() {
  workingIndicator.hidden = true;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderMarkdown(text) {
  if (typeof marked === "undefined") {
    return escapeHtml(text).replace(/\n/g, "<br>");
  }

  marked.setOptions({
    gfm: true,
    breaks: true,
    mangle: false,
    headerIds: false
  });

  const html = marked.parse(String(text || ""));
  return sanitizeHtml(html);
}

function sanitizeHtml(html) {
  const template = document.createElement("template");
  template.innerHTML = html;

  const allowedTags = new Set([
    "p", "br", "strong", "em", "b", "i", "u", "s", "del",
    "code", "pre", "blockquote", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "a", "img", "hr", "input"
  ]);

  const allowedAttrs = new Set([
    "href", "src", "alt", "title", "align", "class",
    "colspan", "rowspan", "start", "type", "checked", "disabled"
  ]);

  for (const element of Array.from(template.content.querySelectorAll("*"))) {
    const tag = element.tagName.toLowerCase();
    if (!allowedTags.has(tag)) {
      element.replaceWith(...element.childNodes);
      continue;
    }

    for (const attr of Array.from(element.attributes)) {
      const name = attr.name.toLowerCase();
      if (!allowedAttrs.has(name) || name.startsWith("on")) {
        element.removeAttribute(attr.name);
      }
    }

    if (tag === "a") {
      const href = (element.getAttribute("href") || "").trim().toLowerCase();
      if (href.startsWith("javascript:") || href.startsWith("data:")) {
        element.removeAttribute("href");
      }
    }

    if (tag === "img") {
      const src = (element.getAttribute("src") || "").trim().toLowerCase();
      if (src.startsWith("javascript:") || src.startsWith("data:")) {
        element.removeAttribute("src");
      }
    }
  }

  return template.innerHTML;
}

function renderQuestion(message) {
  const row = document.createElement("div");
  row.className = "row question";

  const container = document.createElement("div");
  container.className = "question";

  const label = document.createElement("div");
  label.className = "q-label";
  label.textContent = message.question || "Agent 请求确认";
  container.appendChild(label);

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "输入回答";
  container.appendChild(input);

  const answerButton = document.createElement("button");
  answerButton.type = "button";
  answerButton.textContent = "提交";
  answerButton.addEventListener("click", () => {
    sendMessage(backgroundMessage(MSG.USER_ANSWER, {
      questionId: message.questionId || "",
      answer: input.value
    }));
    container.remove();
  });
  container.appendChild(answerButton);

  row.appendChild(container);
  outputElement.appendChild(row);
  outputElement.scrollTop = outputElement.scrollHeight;
}

sendMessage(backgroundMessage(MSG.SIDEPANEL_READY));
sendMessage(backgroundMessage(MSG.NATIVE_STATUS));
