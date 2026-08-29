const DEFAULT_GATEWAY = 'http://127.0.0.1:8080';

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== 'zerotrace.check') return false;
  checkPrompt(message).then(sendResponse).catch((error) => {
    sendResponse({ allow: false, reason: `ZeroTrace checker failed: ${error.message}` });
  });
  return true;
});

async function checkPrompt(message) {
  const settings = await chrome.storage.local.get({ gateway: DEFAULT_GATEWAY });
  const gateway = String(settings.gateway || DEFAULT_GATEWAY).replace(/\/$/, '');
  const response = await fetch(`${gateway}/v1/prompt/check`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-zerotrace-channel': 'http',
      'x-zerotrace-harness': message.harness || 'browser',
    },
    body: JSON.stringify({ text: message.text, session_id: message.sessionId || '' }),
  });
  if (!response.ok) {
    throw new Error(`gateway returned HTTP ${response.status}`);
  }
  const verdict = await response.json();
  return { allow: verdict.allow === true, reason: verdict.reason || '' };
}
