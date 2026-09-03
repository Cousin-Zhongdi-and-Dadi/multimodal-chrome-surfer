chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.target !== "content") {
    return false;
  }

  if (message.type === "page.status") {
    sendResponse({
      ok: true,
      title: document.title,
      url: location.href,
      readyState: document.readyState
    });
    return false;
  }

  return false;
});
