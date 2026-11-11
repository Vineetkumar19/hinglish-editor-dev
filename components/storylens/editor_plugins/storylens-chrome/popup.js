const $=s=>document.querySelector(s);
async function action(type){try{const value=await chrome.runtime.sendMessage({type,port:Number($('#port').value),key:$('#key').value.trim()});$('#status').textContent=value?.message||'Connected.'}catch(e){$('#status').textContent=e.message}}
$('#connect').onclick=()=>action('connect');$('#check').onclick=()=>action('check');$('#disconnect').onclick=()=>action('disconnect');
$('#youtube').onclick=async()=>{try{const granted=await chrome.permissions.request({origins:['https://studio.youtube.com/*']});$('#status').textContent=granted?'YouTube Studio enabled. Checking the local editor…':'YouTube Studio access was not granted.';if(granted)await action('check')}catch(e){$('#status').textContent=e.message}};
chrome.storage.local.get(['port','key','message']).then(v=>{$('#port').value=v.port||8765;$('#key').value=v.key||'';$('#status').textContent=v.message||'Not connected.'});
