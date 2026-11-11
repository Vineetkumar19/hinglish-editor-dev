// Pane limits share one viewport budget, including saved sidebar preferences.
function paneWidths(viewport, chat, history, historyOpen, assistantOpen){
  const v=Math.max(240,Number(viewport)||1024);
  const clean=(value,fallback)=>Number.isFinite(Number(value))?Number(value):fallback;
  const hMax=v>=1080&&assistantOpen?Math.min(640,v-320-520):Math.min(640,v-520);
  const h=Math.max(Math.min(240,v),Math.min(clean(history,280),Math.max(240,hMax)));
  const cMax=Math.min(900,v-(v>=1080&&historyOpen?h:0)-520);
  const c=Math.max(Math.min(320,v),Math.min(clean(chat,420),Math.max(320,cMax)));
  return {chat:Math.min(v,c),history:Math.min(v,h),chatMax:Math.max(Math.min(320,v),cMax),historyMax:Math.max(Math.min(240,v),hMax)};
}
if(typeof module!=='undefined')module.exports={paneWidths};
(()=>{
  if(typeof document==='undefined')return;
  const setupHeader=()=>{
    const bar=document.querySelector('.topbar');if(!bar)return;
    let group=bar.querySelector('.header-actions');
    if(!group){group=document.createElement('div');group.className='header-actions';group.setAttribute('role','group');group.setAttribute('aria-label','Workspace controls');bar.append(group)}
    for(const selector of ['.ai-agents-trigger','.support-call-trigger','.assistant-toggle:not(.chat-history-toggle)','.scheduled-toggle','.profile-trigger']){
      const button=bar.querySelector(selector);if(button&&button.parentElement!==group)group.append(button);
    }
  };
  setupHeader();
  const topbar=document.querySelector('.topbar');
  if(topbar)new ResizeObserver(()=>document.body.style.setProperty('--header-height',topbar.getBoundingClientRect().height+'px')).observe(topbar);
  const limits=(chat,history)=>paneWidths(innerWidth,chat,history,document.body.classList.contains('chat-history-open'),document.body.classList.contains('assistant-open'));
  const notifyResize=()=>window.dispatchEvent(new Event('storylens-pane-layout'));
  new MutationObserver(notifyResize).observe(document.body,{attributes:true,attributeFilter:['class']});
  const headerObserver=new MutationObserver(setupHeader);headerObserver.observe(document.querySelector('.topbar'),{childList:true,subtree:true});
  const setupHistory=()=>{
    const side=document.querySelector('.chat-history');if(!side||side.querySelector('.history-resizer'))return;
    const grip=document.createElement('div');grip.className='history-resizer';grip.tabIndex=0;grip.role='separator';grip.setAttribute('aria-label','Resize Chats sidebar');grip.setAttribute('aria-orientation','vertical');grip.title='Drag right to widen Chats · double-click to reset';side.append(grip);
    let width=280;
    const apply=value=>{const w=limits(parseFloat(document.body.style.getPropertyValue('--chat-width'))||420,value);const max=w.historyMax;width=Math.round(w.history);document.body.style.setProperty('--history-width',width+'px');grip.setAttribute('aria-valuenow',width);grip.setAttribute('aria-valuemin','240');grip.setAttribute('aria-valuemax',String(max))};
    try{width=Number(localStorage.getItem('storylens.history.width'))||280}catch(_){}apply(width);
    const save=()=>{try{localStorage.setItem('storylens.history.width',String(width))}catch(_){}};
    grip.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();grip.setPointerCapture(e.pointerId);document.body.classList.add('resizing-chat')};
    grip.onpointermove=e=>{if(grip.hasPointerCapture(e.pointerId)){apply(e.clientX);notifyResize()}};
    const end=e=>{if(grip.hasPointerCapture(e.pointerId))grip.releasePointerCapture(e.pointerId);document.body.classList.remove('resizing-chat');save()};grip.onpointerup=end;grip.onpointercancel=end;
    grip.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();apply(e.key==='Home'?240:e.key==='End'?640:width+(e.key==='ArrowRight'?32:-32));notifyResize();save()}};
    grip.ondblclick=()=>{apply(280);notifyResize();save()};window.addEventListener('resize',()=>apply(width));window.addEventListener('storylens-pane-layout',()=>apply(width));
  };
  setupHistory();const historyObserver=new MutationObserver(setupHistory);historyObserver.observe(document.body,{childList:true});
  const panel=document.querySelector('.assistant-panel');
  if(panel){
    const grip=document.createElement('div');grip.className='chat-resizer';grip.tabIndex=0;grip.role='separator';grip.setAttribute('aria-label','Resize chat panel');grip.setAttribute('aria-orientation','vertical');panel.prepend(grip);
    let width=420;
    const apply=value=>{const w=limits(value,parseFloat(document.body.style.getPropertyValue('--history-width'))||280);width=Math.round(w.chat);document.body.style.setProperty('--chat-width',width+'px');grip.setAttribute('aria-valuenow',width);grip.setAttribute('aria-valuemin','320');grip.setAttribute('aria-valuemax',String(w.chatMax))};
    try{const saved=Number(localStorage.getItem('storylens.chat.width'));if(saved)width=saved}catch(_){}
    apply(width);
    const save=()=>{try{localStorage.setItem('storylens.chat.width',String(width))}catch(_){}};
    grip.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();grip.setPointerCapture(e.pointerId);document.body.classList.add('resizing-chat')};
    grip.onpointermove=e=>{if(grip.hasPointerCapture(e.pointerId))apply(innerWidth-e.clientX)};
    const end=e=>{if(grip.hasPointerCapture(e.pointerId))grip.releasePointerCapture(e.pointerId);document.body.classList.remove('resizing-chat');save()};grip.onpointerup=end;grip.onpointercancel=end;
    grip.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();apply(e.key==='Home'?320:e.key==='End'?900:width+(e.key==='ArrowLeft'?32:-32));save()}};
    grip.ondblclick=()=>{apply(420);save()};window.addEventListener('resize',()=>apply(width));window.addEventListener('storylens-pane-layout',()=>apply(width));
  }
  window.addEventListener('message',e=>{
    if(e.origin!==location.origin||e.data?.type!=='storylens-tool-height')return;
    for(const frame of document.querySelectorAll('#embeddedTools iframe'))if(e.source===frame.contentWindow&&Number.isFinite(e.data.height)){frame.dataset.fitHeight='true';frame.style.height=Math.max(100,Math.min(12000,e.data.height))+'px';}
  });
  if(new URLSearchParams(location.search).get('tool')==='photos'){
    setMode('photos');document.body.classList.add('tools-visible');
  }
})();
