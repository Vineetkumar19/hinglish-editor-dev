chrome.storage.local.get(['browser','profile']).then(saved => {
  if (saved.browser) document.querySelector('#browser').value = saved.browser;
  if (saved.profile) document.querySelector('#profile').value = saved.profile;
});
document.querySelector('#connect').onclick = async () => {
  await chrome.storage.local.set({browser: document.querySelector('#browser').value,
    profile: document.querySelector('#profile').value.trim(), enabled: true});
  const result = await chrome.runtime.sendMessage({operation: 'connect'});
  document.querySelector('#status').textContent = result?.note || 'Connecting';
};
document.querySelector('#youtube').onclick = async () => {
  const granted = await chrome.permissions.request({origins: ['https://www.youtube.com/*']});
  document.querySelector('#status').textContent = granted ? 'YouTube capture allowed' : 'Permission not granted';
};
document.querySelector('#disconnect').onclick = async () => {
  await chrome.storage.local.set({enabled: false});
  await chrome.runtime.sendMessage({operation: 'disconnect'});
  document.querySelector('#status').textContent = 'Disconnected';
};
