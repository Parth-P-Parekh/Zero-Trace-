(() => {
  const PAGE_SOURCE = 'zerotrace-page';
  const EXT_SOURCE = 'zerotrace-extension';
  const originalFetch = window.fetch.bind(window);
  const pending = new Map();
  let sequence = 0;

  window.addEventListener('message', (event) => {
    if (event.source !== window || event.data?.source !== EXT_SOURCE) return;
    if (event.data.type !== 'verdict') return;
    const settle = pending.get(event.data.id);
    if (!settle) return;
    pending.delete(event.data.id);
    settle(event.data);
  });

  window.fetch = async function zeroTraceFetch(input, init = {}) {
    const method = String(init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    const url = new URL(input instanceof Request ? input.url : String(input), location.href);
    if (!['POST', 'PUT', 'PATCH'].includes(method) || !isModelRequest(url)) {
      return originalFetch(input, init);
    }

    const body = await requestBody(input, init);
    const text = extractUserText(body);
    if (!text.trim()) {
      throw new Error('ZeroTrace blocked an AI request whose user prompt could not be isolated.');
    }
    const verdict = await check(text);
    if (!verdict.allow) {
      throw new Error(verdict.reason || 'ZeroTrace blocked this prompt before submission.');
    }
    return originalFetch(input, init);
  };

  function isModelRequest(url) {
    if (!['chatgpt.com', 'claude.ai'].includes(url.hostname)) return false;
    const path = url.pathname.toLowerCase();
    return ['conversation', 'completion', '/api/chat', 'append_message',
      '/messages', '/responses'].some((part) => path.includes(part));
  }

  async function requestBody(input, init) {
    if (typeof init.body === 'string') return init.body;
    if (init.body instanceof URLSearchParams) return init.body.toString();
    if (input instanceof Request) return input.clone().text();
    return '';
  }

  function extractUserText(raw) {
    let payload;
    try { payload = JSON.parse(raw); } catch { return ''; }
    const found = [];
    if (typeof payload.prompt === 'string') found.push(payload.prompt);
    if (typeof payload.input === 'string') found.push(payload.input);
    collectMessages(payload.messages, found);
    collectMessages(Array.isArray(payload.input) ? payload.input : [], found);
    if (payload.message && typeof payload.message === 'object') {
      collectMessages([payload.message], found);
    } else if (typeof payload.message === 'string') {
      found.push(payload.message);
    }
    return found.join('\n');
  }

  function collectMessages(messages, found) {
    if (!Array.isArray(messages)) return;
    for (const message of messages) {
      if (!message || typeof message !== 'object') continue;
      const role = String(message.role || message.author?.role || '').toLowerCase();
      if (!['user', 'human'].includes(role)) continue;
      collectContent(message.content, found);
    }
  }

  function collectContent(content, found) {
    if (typeof content === 'string') { found.push(content); return; }
    if (content && !Array.isArray(content) && typeof content === 'object') {
      if (typeof content.text === 'string') found.push(content.text);
      if (Array.isArray(content.parts)) collectContent(content.parts, found);
      return;
    }
    if (!Array.isArray(content)) return;
    for (const part of content) {
      if (typeof part === 'string') found.push(part);
      else if (part && typeof part.text === 'string') found.push(part.text);
      else if (part && typeof part.content === 'string') found.push(part.content);
    }
  }

  function check(text) {
    const id = `zt-${Date.now()}-${++sequence}`;
    const harness = location.hostname === 'chatgpt.com' ? 'chatgpt-web' : 'claude-web';
    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        pending.delete(id);
        resolve({ allow: false, reason: 'ZeroTrace checker timed out; request not sent.' });
      }, 5000);
      pending.set(id, (verdict) => { clearTimeout(timeout); resolve(verdict); });
      window.postMessage({ source: PAGE_SOURCE, type: 'check', id, text, harness }, '*');
    });
  }
})();
