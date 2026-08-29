const PAGE_SOURCE = 'zerotrace-page';
const EXT_SOURCE = 'zerotrace-extension';

window.addEventListener('message', async (event) => {
  if (event.source !== window || event.data?.source !== PAGE_SOURCE) return;
  if (event.data.type !== 'check') return;

  let verdict;
  try {
    verdict = await chrome.runtime.sendMessage({
      type: 'zerotrace.check',
      text: event.data.text,
      harness: event.data.harness,
      sessionId: event.data.sessionId,
    });
  } catch (error) {
    verdict = { allow: false, reason: `ZeroTrace extension failed: ${error.message}` };
  }

  window.postMessage({
    source: EXT_SOURCE,
    type: 'verdict',
    id: event.data.id,
    allow: verdict?.allow === true,
    reason: verdict?.reason || 'ZeroTrace blocked this request.',
  }, '*');

  if (!verdict?.allow) showBlock(verdict?.reason);
});

function showBlock(reason) {
  const id = 'zerotrace-block-notice';
  document.getElementById(id)?.remove();
  const notice = document.createElement('div');
  notice.id = id;
  notice.textContent = reason || 'ZeroTrace blocked this prompt before it left the browser.';
  Object.assign(notice.style, {
    position: 'fixed', top: '16px', left: '50%', transform: 'translateX(-50%)',
    zIndex: '2147483647', maxWidth: '720px', padding: '12px 16px',
    borderRadius: '8px', background: '#231f20', color: '#fff',
    font: '14px/1.4 system-ui, sans-serif', boxShadow: '0 6px 28px rgba(0,0,0,.3)',
  });
  (document.body || document.documentElement).appendChild(notice);
  setTimeout(() => notice.remove(), 9000);
}
