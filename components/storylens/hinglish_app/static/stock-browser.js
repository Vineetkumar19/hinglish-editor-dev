(()=>{
 'use strict';
 const $=id=>document.getElementById(id),token=document.documentElement.dataset.token;
 const extension=new URLSearchParams(location.search).get('extension_id');
 const validExtension=/^[a-p]{32}$/.test(extension||'');
 async function api(path='',body){const response=await window.storylensFetch('/api/stock-browser'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(body===undefined?{}:{body:JSON.stringify(body)})});return window.storylensResponse(response);}
 function error(e){$('status').textContent=window.storylensError(e);}
 async function refresh(){
  try{const status=await api();$('status').textContent=status.connected?'Connected · '+status.providers.map(p=>p==='pexels'?'Pexels':'Pixabay').join(' · '):'Not connected';
   const pair=await api('/pairing');$('folder').textContent=pair.extension_folder;
   $('pair').disabled=!validExtension||!window.chrome?.runtime?.sendMessage;
   if(validExtension&&$('pair').disabled)$('hint').textContent='Open this page from the Stock Search extension popup in Chrome.';
   $('disconnect').disabled=!status.connected;
  }catch(e){error(e);}
 }
 $('pair').onclick=async()=>{
  $('pair').disabled=true;
  try{const pair=await api('/pairing');
   const result=await new Promise((resolve,reject)=>{chrome.runtime.sendMessage(extension,{type:'pair',port:pair.port,key:pair.key},reply=>{if(chrome.runtime.lastError)reject(Error('Open the Stock Search popup and choose Connect again.'));else if(reply?.error)reject(Error(reply.error));else resolve(reply);});});
   if(!result?.connected)throw Error('Check the Stock Search popup and reconnect.');
   await refresh();
  }catch(e){error(e);$('pair').disabled=false;}
 };
 $('refresh').onclick=refresh;$('disconnect').onclick=async()=>{try{await api('/disconnect',{});await refresh();}catch(e){error(e);}};
 void refresh();
})();
