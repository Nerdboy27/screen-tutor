// Captures the visible tab on the command hotkey and forwards it to the tutor
// API. The screenshot lives only in this service worker's memory.

const DEFAULTS = { apiBaseUrl: "http://127.0.0.1:8000", apiKey: "" };

async function settings() {
  return { ...DEFAULTS, ...(await chrome.storage.sync.get(DEFAULTS)) };
}

function headers(apiKey) {
  const base = { "content-type": "application/json" };
  if (apiKey) base["x-api-key"] = apiKey;
  return base;
}

export async function captureAndAnalyze(prompt = null) {
  const { apiBaseUrl, apiKey } = await settings();
  const dataUrl = await chrome.tabs.captureVisibleTab({ format: "png" });
  const imageBase64 = dataUrl.split(",")[1];
  const { sessionId } = await chrome.storage.session.get({ sessionId: null });

  const response = await fetch(`${apiBaseUrl}/analyze`, {
    method: "POST",
    headers: headers(apiKey),
    body: JSON.stringify({
      session_id: sessionId,
      image_base64: imageBase64,
      mime_type: "image/png",
      prompt,
      source: "browser",
    }),
  });
  if (!response.ok) throw new Error(`API ${response.status}`);
  const body = await response.json();
  await chrome.storage.session.set({
    sessionId: body.session_id,
    lastReply: body.turn.text,
  });
  return body;
}

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "capture-tab") return;
  try {
    const body = await captureAndAnalyze();
    chrome.notifications?.create({
      type: "basic",
      title: "AI Tutor",
      message: body.turn.text.slice(0, 300),
      iconUrl: "icon.png",
    });
  } catch (error) {
    console.error("Tutor capture failed", error);
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "capture") return false;
  captureAndAnalyze(message.prompt ?? null)
    .then((body) => sendResponse({ ok: true, body }))
    .catch((error) => sendResponse({ ok: false, error: String(error) }));
  return true; // keep the message channel open for the async response
});
