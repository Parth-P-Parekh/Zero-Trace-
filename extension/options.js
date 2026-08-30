const gateway = document.getElementById('gateway');
const status = document.getElementById('status');

chrome.storage.local.get({ gateway: 'http://127.0.0.1:8080' }, (value) => {
  gateway.value = value.gateway;
});

document.getElementById('save').addEventListener('click', () => {
  chrome.storage.local.set({ gateway: gateway.value.replace(/\/$/, '') }, () => {
    status.textContent = 'Saved';
    setTimeout(() => { status.textContent = ''; }, 1500);
  });
});
