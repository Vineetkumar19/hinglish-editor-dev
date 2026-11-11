document.getElementById('connect').onclick=async()=>{
 const status=document.getElementById('status'),port=Number(document.getElementById('port').value);
 if(!Number.isInteger(port)||port<1024||port>65535){status.textContent='Enter the port shown in Storylens.';return;}
 try{
  const accepted=await chrome.permissions.request({origins:['https://www.pexels.com/*','https://pixabay.com/*']});
  if(!accepted){status.textContent='Site access was not enabled. Existing Storylens sources still work.';return;}
  await chrome.tabs.create({url:'http://127.0.0.1:'+port+'/stock-browser.html?extension_id='+chrome.runtime.id});
 }catch(e){status.textContent='Keep Storylens running, then reconnect.';const d=document.createElement('details'),s=document.createElement('summary'),t=document.createElement('pre');s.textContent='Technical details';t.textContent=String(e.message);d.append(s,t);status.after(d);}
};
