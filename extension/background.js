import { MSG, NATIVE_HOST_NAME, sidepanelMessage } from "./protocol.js";

const RECONNECT_DELAY_MS = 1000;

let nativePort = null;
let reconnectTimer = null;
let outputToSidepanel = true;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.target !== "background") {
    return false;
  }

  switch (message.type) {
    case MSG.TASK_START:
      sendToNative({ type: MSG.TASK_START, taskId: message.taskId, text: message.text });
      sendResponse({ accepted: Boolean(nativePort) });
      break;
    case MSG.TASK_STOP:
      sendToNative({ type: MSG.TASK_STOP, taskId: message.taskId });
      sendResponse({ accepted: Boolean(nativePort) });
      break;
    case MSG.USER_ANSWER:
      sendToNative({
        type: MSG.USER_ANSWER,
        questionId: message.questionId,
        answer: message.answer
      });
      sendResponse({ accepted: Boolean(nativePort) });
      break;
    case MSG.NATIVE_STATUS:
      sendResponse({ connected: Boolean(nativePort) });
      break;
    case MSG.SIDEPANEL_READY:
      broadcastToSidepanel({ type: MSG.NATIVE_STATUS, connected: Boolean(nativePort) });
      sendResponse({ ok: true });
      break;
    case MSG.OFFSCREEN_PING:
      sendResponse({ ok: true });
      break;
    default:
      sendResponse({ ok: false, error: `Unknown message type: ${message.type}` });
  }
  return false;
});

function connectNative() {
  if (nativePort) {
    return;
  }

  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);
  } catch (error) {
    console.error("[native] connectNative failed", error);
    scheduleReconnect();
    broadcastToSidepanel({ type: MSG.NATIVE_STATUS, connected: false });
    return;
  }

  nativePort.onMessage.addListener(handleNativeMessage);
  nativePort.onDisconnect.addListener(() => {
    const lastError = chrome.runtime.lastError;
    console.warn("[native] disconnected", lastError?.message || "");
    nativePort = null;
    scheduleReconnect();
    broadcastToSidepanel({ type: MSG.NATIVE_STATUS, connected: false });
  });

  broadcastToSidepanel({ type: MSG.NATIVE_STATUS, connected: true });
}

function scheduleReconnect() {
  if (reconnectTimer) {
    return;
  }
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectNative();
  }, RECONNECT_DELAY_MS);
}

function sendToNative(message) {
  if (!nativePort) {
    connectNative();
  }

  if (!nativePort) {
    console.warn("[native] cannot send message, no native port", message.type);
    return false;
  }

  try {
    nativePort.postMessage(message);
    return true;
  } catch (error) {
    console.error("[native] postMessage failed", error);
    return false;
  }
}

function broadcastToSidepanel(message) {
  if (!outputToSidepanel) {
    return;
  }

  chrome.runtime.sendMessage(sidepanelMessage(message.type, message)).catch(() => {});
}

function handleNativeMessage(message) {
  if (!message) {
    return;
  }

  if (message.type === MSG.BROWSER_REQUEST) {
    handleBrowserRequest(message);
    return;
  }

  if (message.type === MSG.AGENT_OUTPUT || message.type === MSG.AGENT_ASK_USER) {
    broadcastToSidepanel(message);
    return;
  }

  console.warn("[native] unhandled native message", message);
}

async function handleBrowserRequest(request) {
  const { requestId, method, params = {} } = request;

  try {
    const result = await executeBrowserMethod(method, params);
    sendToNative({
      type: MSG.BROWSER_RESPONSE,
      requestId,
      ok: true,
      result
    });
  } catch (error) {
    sendToNative({
      type: MSG.BROWSER_RESPONSE,
      requestId,
      ok: false,
      error: {
        name: error?.name || "BrowserError",
        message: error?.message || String(error)
      }
    });
  }
}

async function executeBrowserMethod(method, params) {
  switch (method) {
    case "list_tabs":
      return listTabs();
    case "switch_tab":
      return switchTab(params.tabId);
    case "snapshot":
      return executeScriptInTab(params.tabId, snapshotPage, [
        {
          textOnly: Boolean(params.textOnly),
          maxElements: Number(params.maxElements || 120)
        }
      ], "ISOLATED");
    case "action":
      return executeScriptInTab(params.tabId, executeActionInPage, [params.action || {}], "ISOLATED");
    case "execute_js":
      return executeScriptInTab(params.tabId, evaluatePageCode, [params.code || ""], "MAIN");
    default:
      throw new Error(`Unknown browser method: ${method}`);
  }
}

async function listTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs
    .filter((tab) => isScriptableUrl(tab.url))
    .map((tab) => ({
      id: String(tab.id),
      url: tab.url || "",
      title: tab.title || "",
      active: Boolean(tab.active),
      windowId: tab.windowId
    }));
}

async function switchTab(tabId) {
  const numericId = Number(tabId);
  const tab = await chrome.tabs.update(numericId, { active: true });
  if (tab.windowId !== undefined) {
    await chrome.windows.update(tab.windowId, { focused: true });
  }
  return {
    id: String(tab.id),
    url: tab.url || "",
    title: tab.title || ""
  };
}

async function executeScriptInTab(tabId, func, args, world) {
  const numericId = Number(tabId);
  const results = await chrome.scripting.executeScript({
    target: { tabId: numericId },
    world,
    func,
    args
  });

  if (!results || results.length === 0) {
    throw new Error("No script result returned from tab");
  }

  return results[0].result;
}

function isScriptableUrl(url) {
  return Boolean(url && /^https?:/i.test(url));
}

function snapshotPage({ textOnly = false, maxElements = 120 } = {}) {
  const root = document.body || document.documentElement;
  const title = document.title || "";
  const url = location.href;
  const readyState = document.readyState;

  const elements = [];
  const selectors = "button, a, input, textarea, select, [role='button'], [role='link'], [contenteditable='true']";
  const all = Array.from(root.querySelectorAll(selectors)).filter((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 1 && rect.height > 1;
  });

  for (const element of all.slice(0, maxElements)) {
    const rect = element.getBoundingClientRect();
    const tag = element.tagName.toLowerCase();
    const type = element.getAttribute("type") || "";
    elements.push({
      index: elements.length,
      tag,
      type,
      id: element.id || "",
      name: element.getAttribute("name") || "",
      role: element.getAttribute("role") || "",
      text: (element.innerText || element.value || element.getAttribute("aria-label") || element.getAttribute("placeholder") || "").trim().slice(0, 200),
      selector: buildSelector(element),
      rect: {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      },
      disabled: Boolean(element.disabled),
      checked: Boolean(element.checked),
      selected: element.tagName === "SELECT" ? element.value : undefined
    });
  }

  const bodyText = textOnly
    ? (root.innerText || "").replace(/\s+/g, " ").trim().slice(0, 12000)
    : "";

  return {
    ok: true,
    title,
    url,
    readyState,
    bodyText,
    elements
  };
}

function buildSelector(element) {
  if (element.id) {
    return `#${CSS.escape(element.id)}`;
  }

  const parts = [];
  let current = element;
  while (current && current !== document.body && parts.length < 4) {
    let part = current.tagName.toLowerCase();
    if (current.id) {
      part += `#${CSS.escape(current.id)}`;
    } else if (current.classList?.length) {
      part += "." + Array.from(current.classList).slice(0, 2).map((name) => CSS.escape(name)).join(".");
    }
    parts.unshift(part);
    current = current.parentElement;
  }
  return parts.join(" > ");
}

function executeActionInPage(action = {}) {
  const findElement = (target) => {
    if (!target) {
      return null;
    }
    if (typeof target.selector === "string" && target.selector) {
      const match = document.querySelector(target.selector);
      if (match) {
        return match;
      }
    }
    if (Number.isInteger(target.index)) {
      const all = Array.from(document.querySelectorAll("button, a, input, textarea, select, [role='button'], [role='link'], [contenteditable='true']"));
      const visible = all.filter((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 1 && rect.height > 1;
      });
      return visible[target.index] || null;
    }
    if (typeof target.text === "string" && target.text) {
      const candidates = Array.from(document.querySelectorAll("button, a, input[type='button'], input[type='submit'], [role='button'], label"));
      return candidates.find((element) => (element.innerText || element.value || "").trim().includes(target.text)) || null;
    }
    return null;
  };

  const setNativeValue = (element, value) => {
    const prototype = element instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
    if (descriptor?.set) {
      descriptor.set.call(element, value);
    } else {
      element.value = value;
    }
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  };

  const clickElement = (element) => {
    const rect = element.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    for (const eventName of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
      element.dispatchEvent(new MouseEvent(eventName, {
        bubbles: true,
        cancelable: true,
        view: window,
        clientX: x,
        clientY: y
      }));
    }
  };

  switch (action.type) {
    case "click": {
      const element = findElement(action.target);
      if (!element) {
        return { ok: false, error: "Click target not found" };
      }
      clickElement(element);
      return { ok: true, action: "click" };
    }
    case "type": {
      const element = findElement(action.target);
      if (!element) {
        return { ok: false, error: "Type target not found" };
      }
      element.focus();
      setNativeValue(element, String(action.value ?? ""));
      return { ok: true, action: "type" };
    }
    case "select": {
      const element = findElement(action.target);
      if (!element) {
        return { ok: false, error: "Select target not found" };
      }
      element.value = String(action.value ?? "");
      element.dispatchEvent(new Event("change", { bubbles: true }));
      return { ok: true, action: "select" };
    }
    case "scroll": {
      const deltaY = Number(action.deltaY || 0);
      const deltaX = Number(action.deltaX || 0);
      if (action.target) {
        const element = findElement(action.target);
        if (element) {
          element.scrollBy({ left: deltaX, top: deltaY, behavior: "smooth" });
          return { ok: true, action: "scroll" };
        }
      }
      window.scrollBy({ left: deltaX, top: deltaY, behavior: "smooth" });
      return { ok: true, action: "scroll" };
    }
    case "wait": {
      return new Promise((resolve) => {
        setTimeout(() => resolve({ ok: true, action: "wait", waitedMs: Number(action.ms || 500) }), Number(action.ms || 500));
      });
    }
    case "fill": {
      const fields = Array.isArray(action.fields) ? action.fields : [];
      const results = [];
      for (const field of fields) {
        const element = findElement(field.target);
        if (!element) {
          results.push({ ok: false, target: field.target, error: "Field not found" });
          continue;
        }
        setNativeValue(element, String(field.value ?? ""));
        results.push({ ok: true, target: field.target });
      }
      return { ok: results.every((item) => item.ok), action: "fill", results };
    }
    case "submit": {
      const form = action.target ? findElement(action.target) : document.querySelector("form");
      const target = form?.closest?.("form") || form;
      if (!target || typeof target.requestSubmit !== "function") {
        return { ok: false, error: "Form not found or not submittable" };
      }
      target.requestSubmit();
      return { ok: true, action: "submit" };
    }
    default:
      return { ok: false, error: `Unknown action type: ${action.type}` };
  }
}

function evaluatePageCode(code) {
  return (async () => {
    try {
      const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
      const value = await new AsyncFunction(code)();
      return { ok: true, value };
    } catch (error) {
      return {
        ok: false,
        error: {
          name: error?.name || "Error",
          message: error?.message || String(error)
        }
      };
    }
  })();
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("[background] Multimodal Browser Agent installed");
});

chrome.runtime.onStartup.addListener(() => {
  connectNative();
});

connectNative();
