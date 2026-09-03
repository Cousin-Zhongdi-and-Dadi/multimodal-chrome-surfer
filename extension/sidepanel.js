import { MSG, backgroundMessage, newId } from "./protocol.js";

const taskInput = document.getElementById("task");
const sendButton = document.getElementById("send");
const stopButton = document.getElementById("stop");
const statusElement = document.getElementById("status");
const outputElement = document.getElementById("output");

let activeTaskId = null;

sendButton.addEventListener("click", () => {
  const text = taskInput.value.trim();
  if (!text) {
    return;
  }

  activeTaskId = newId();
  outputElement.textContent = "";
  appendOutput(`[系统] 任务已创建：${text}\n\n`);
  sendMessage(backgroundMessage(MSG.TASK_START, {
    taskId: activeTaskId,
    text
  }));
});

stopButton.addEventListener("click", () => {
  if (!activeTaskId) {
    return;
  }

  sendMessage(backgroundMessage(MSG.TASK_STOP, {
    taskId: activeTaskId
  }));
  appendOutput("\n[系统] 已发送停止请求\n");
});

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.target !== "sidepanel") {
    return;
  }

  switch (message.type) {
    case MSG.NATIVE_STATUS:
      statusElement.textContent = message.connected
        ? "本地 Generic Agent 服务已连接"
        : "本地 Generic Agent 服务未连接";
      break;
    case MSG.AGENT_OUTPUT:
      appendOutput(message.text || "");
      break;
    case MSG.AGENT_ASK_USER:
      renderQuestion(message);
      break;
    default:
      break;
  }
});

function sendMessage(message) {
  chrome.runtime.sendMessage(message).catch((error) => {
    appendOutput(`\n[错误] ${error.message}\n`);
  });
}

function appendOutput(text) {
  outputElement.textContent += text;
  outputElement.scrollTop = outputElement.scrollHeight;
}

function renderQuestion(message) {
  const container = document.createElement("div");
  container.className = "question";

  const label = document.createElement("div");
  label.textContent = message.question || "Agent 请求确认";
  container.appendChild(label);

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "输入回答";
  container.appendChild(input);

  const answerButton = document.createElement("button");
  answerButton.textContent = "提交回答";
  answerButton.addEventListener("click", () => {
    sendMessage(backgroundMessage(MSG.USER_ANSWER, {
      questionId: message.questionId || "",
      answer: input.value
    }));
    container.remove();
  });
  container.appendChild(answerButton);

  outputElement.appendChild(container);
}

sendMessage(backgroundMessage(MSG.SIDEPANEL_READY));
sendMessage(backgroundMessage(MSG.NATIVE_STATUS));
