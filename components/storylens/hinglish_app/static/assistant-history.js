// Local history navigation; opening a chat never sends or replays its old requests.
(()=>{
 const sheet=document.createElement('link');sheet.rel='stylesheet';sheet.href='assistant-history.css';document.head.append(sheet);
 const token=document.documentElement.dataset.token,$=s=>document.querySelector(s);
 async function api(path){const r=await window.storylensFetch(path,{headers:{'X-Hinglish-Token':token}});const d=await window.storylensResponse(r);if(!r.ok)throw Error(d.error||'History unavailable');return d}
 const side=document.createElement('nav');side.className='chat-history';side.setAttribute('aria-label','Chat history');
 side.innerHTML='<div class="chat-history-heading"><h2>Chats</h2><button type="button" id="chatHistoryClose" aria-label="Close chat history">×</button></div><button type="button" id="chatHistoryNew">＋ New chat</button><input id="chatHistorySearch" type="search" aria-label="Search all chats" placeholder="Search chats…"><p class="chat-memory-note">Each chat has its own context · last 5 exchanges</p><div id="chatHistoryList"></div><button type="button" id="chatHistoryTranscript">Read full conversation</button><p id="chatHistoryStatus" role="status"></p>';
 document.body.append(side);
 const toggle=document.createElement('button');toggle.type='button';toggle.className='assistant-toggle chat-history-toggle';toggle.textContent='☰ Chats';toggle.setAttribute('aria-label','Open chat history');$('.topbar').prepend(toggle);
 function show(value){document.body.classList.toggle('chat-history-open',value);toggle.setAttribute('aria-expanded',String(value));localStorage.setItem('storylens.history.open',String(value))}
 show(localStorage.getItem('storylens.history.open')!=='false'&&innerWidth>=1180);
 toggle.onclick=()=>show(!document.body.classList.contains('chat-history-open'));$('#chatHistoryClose').onclick=()=>show(false);
 $('#chatHistoryNew').onclick=()=>window.storylensChat.new().then(refresh).catch(error=>$('#chatHistoryStatus').textContent=window.storylensError(error));
 let serial=0;
 async function refresh(){const request=++serial;try{
   const data=await api('/api/assistant/history?q='+encodeURIComponent($('#chatHistorySearch').value));if(request!==serial)return;
   const box=$('#chatHistoryList');box.replaceChildren();
   for(const chat of data.chats){
     const button=document.createElement('button');button.type='button';button.className='chat-history-item';button.dataset.chat=chat.id;
     button.setAttribute('aria-current',String(chat.id===window.storylensChat.id));
     const title=document.createElement('strong');title.textContent=chat.title;
     const detail=document.createElement('small');detail.textContent=new Date(chat.updated*1000).toLocaleDateString('en-IN')+' · '+chat.message_count+' messages'+(['running','planning'].includes(chat.status)?' · working':'');
     button.append(title,detail);button.onclick=()=>window.storylensChat.open(chat.id).then(refresh).catch(error=>$('#chatHistoryStatus').textContent=window.storylensError(error));box.append(button);
   }
   $('#chatHistoryStatus').textContent=data.chats.length?'':'No matching conversations.';
 }catch(error){$('#chatHistoryStatus').textContent=window.storylensError(error)}}
 let searchTimer;$('#chatHistorySearch').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(refresh,180)};
 document.addEventListener('storylens-chat-selected',refresh);setInterval(refresh,10000);refresh();
 const dialog=document.createElement('dialog');dialog.className='chat-transcript';
 dialog.innerHTML='<header><h2>Full conversation</h2><button type="button" aria-label="Close transcript">Close</button></header><button type="button" id="chatEarlier">Load earlier messages</button><div id="chatTranscriptTurns"></div>';
 document.body.append(dialog);dialog.querySelector('header button').onclick=()=>dialog.close();let before=null,reading=null;
 function transcriptTurn(message){
   const article=document.createElement('article'),label=document.createElement('strong'),p=document.createElement('p');
   label.textContent=(message.role==='user'?'You':'Storylens')+' · '+new Date(message.created*1000).toLocaleString('en-IN');p.textContent=message.text;
   article.append(label,p);return article;
 }
 async function page(){
   const id=reading;if(!id)return;const data=await api('/api/assistant/messages?id='+encodeURIComponent(id)+(before?'&before='+encodeURIComponent(before):''));
   if(id!==reading)return;
   const fragment=document.createDocumentFragment();for(const message of data.messages)fragment.append(transcriptTurn(message));$('#chatTranscriptTurns').prepend(fragment);
   if(data.messages.length)before=data.messages[0].id;$('#chatEarlier').hidden=!data.has_more;
 }
 $('#chatHistoryTranscript').onclick=async()=>{reading=window.storylensChat.id;before=null;$('#chatTranscriptTurns').replaceChildren();try{await page();dialog.showModal()}catch(error){$('#chatHistoryStatus').textContent=window.storylensError(error)}};
 $('#chatEarlier').onclick=()=>page().catch(error=>$('#chatHistoryStatus').textContent=window.storylensError(error));
})();
