const PING_INTERVAL_MS = 20000;

function ping() {
  chrome.runtime.sendMessage({
    target: "background",
    type: "offscreen.ping"
  }).catch(() => {});
}

ping();
setInterval(ping, PING_INTERVAL_MS);
