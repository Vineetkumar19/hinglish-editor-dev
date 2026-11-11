/* Compact AE media replacement controls; host shortcuts stay active while the panel is loaded. */
(()=>{
 window.storylensCopyPaste=function(options){
  const root=options.root,native=options.native;
  root.__storylensCopyPaste?.dispose();root.replaceChildren();
  const make=(tag,text,parent=root)=>{const el=document.createElement(tag);if(text)el.textContent=text;parent.append(el);return el;};
  if(options.host!=='aftereffects'){make('p','Fill nested After Effects templates in After Effects. Premiere cannot edit pictures inside a Dynamic Link composition.');return;}
  const row=make('div');row.className='copy-paste-actions';Object.assign(row.style,{display:'grid',gridTemplateColumns:'minmax(100px,1.3fr) repeat(3,minmax(0,1fr))',gap:'6px',alignItems:'center'});
  const source=make('select',null,row);source.setAttribute('aria-label','Copy source');
  for(const [value,text]of[['project','AE Project'],['explorer','Explorer']]){const o=make('option',text,source);o.value=value;}source.value='project';
  const copy=make('button','Copy',row),paste=make('button','Paste',row),undo=make('button','Undo',row);
  for(const el of [source,copy,paste,undo])Object.assign(el.style,{minWidth:'0',height:'34px',minHeight:'34px',margin:'0',padding:'4px 8px'});
  [copy,paste,undo].forEach(b=>b.type='button');
  const status=make('p');status.hidden=true;status.setAttribute('role','status');
  const settings=make('details');make('summary','Settings',settings);const reset=make('button','Restart from first placeholder',settings);reset.type='button';
  const technical=make('details');technical.hidden=true;make('summary','Technical details',technical);const diagnostics=make('pre',null,technical);
  let busy=false,enabled=true,keyboardReady=!options.keyboard,epoch=0,disposed=false,shortcutQueue=Promise.resolve(),starting=null;
  function enabledState(){options.onEnabled?.(enabled,!options.keyboard||keyboardReady);}
  function buttons(){[source,copy,paste,undo,reset].forEach(b=>b.disabled=busy||!enabled);}
  function clear(){status.textContent='';status.hidden=true;diagnostics.textContent='';technical.hidden=true;technical.open=false;options.clearError?.();}
  function showError(e){
   const raw=e?.message||String(e),technicalText=/TypeError|ReferenceError|SyntaxError|JSON\.parse|(?:null|undefined) is not an object|has no method|is not a function/i.test(raw),known=!technicalText&&/^copy_paste_(media|target|template|stale|full|host|native)$/.test(e.code||'');
   const problem=window.storylensProblem?.(known?e:{message:raw,name:e.name,details:e.details})||{message:known?raw:'Copy Paste could not finish. Check the editor connection and try again.',details:e.details||raw};
   status.textContent=problem.message;status.hidden=false;diagnostics.textContent=problem.details||e.details||'';technical.hidden=!diagnostics.textContent;technical.open=false;
   options.onAttention?.();
  }
  function show(r){
   // Keep routine status quiet; results remain available on hover without another row.
   if(r.cleared){copy.title='';return;}
   if(r.framing_warning){diagnostics.textContent=r.framing_warning+(r.framing_details?'\n'+r.framing_details:'');technical.hidden=false;technical.open=false;}
   if(r.clipboard)copy.title=r.clipboard.name||'';
   if(r.pasted)paste.title='Placed '+r.pasted.media+' · '+r.pasted.number+' of '+r.total;
   if(r.undone)paste.title='';
   if(r.framing?.warnings?.length){diagnostics.textContent=[...new Set(r.framing.warnings)].join('\n');technical.hidden=false;technical.open=false;}
  }
  async function run(payload){
   if(!enabled||busy)return;
   if(options.isBusy?.()){showError(Object.assign(Error('Wait for the current edit to finish.'),{code:'copy_paste_native'}));return;}
   const runEpoch=epoch;busy=true;buttons();clear();
   try{if(typeof payload==='function')payload=await payload();if(!enabled||epoch!==runEpoch)return;const r=await native('copyPaste',payload);if(!enabled||epoch!==runEpoch)return;if(r.error)throw Object.assign(Error(r.error),{code:r.code,details:r.details});show(r);return r;}
   catch(e){if(enabled&&epoch===runEpoch)showError(e);}
   finally{busy=false;buttons();}
  }
  const copyPayload=(kind,windowHandle)=>async()=>{
   const copyEpoch=epoch,cleared=await native('copyPaste',{action:'clear'});if(!enabled||epoch!==copyEpoch)return;
   if(cleared.error)throw Object.assign(Error(cleared.error),{code:cleared.code,details:cleared.details});show(cleared);
   if(kind==='explorer'){const selected=await native('explorerSelection',windowHandle?{window_handle:windowHandle}:{});if(selected.error)throw Object.assign(Error(selected.error),{code:selected.code,details:selected.details});return {action:'copyFile',paths:selected.paths};}
   return {action:'copy'};
  };
  copy.onclick=()=>run(copyPayload(source.value));paste.onclick=()=>run({action:'paste',fit:'fill'});undo.onclick=()=>run({action:'undo'});reset.onclick=()=>run({action:'reset',next:0});
  const keys=e=>{if(options.shortcuts===false||!enabled||!root.contains(e.target)||!e.ctrlKey||e.altKey||e.shiftKey||e.metaKey)return;if(e.key==='1'){e.preventDefault();copy.click();}else if(e.key==='2'){e.preventDefault();paste.click();}else if(e.key==='3'){e.preventDefault();undo.click();}};
  root.addEventListener('keydown',keys);
  const controller={
   dispose(){disposed=true;epoch++;enabled=false;root.removeEventListener('keydown',keys);options.keyboard?.(false);options.keyInterest?.(false);if(root.__storylensCopyPaste===controller)delete root.__storylensCopyPaste;},
   inspect(){return run({action:'inspect'});},isEnabled:()=>enabled,isShortcutReady:()=>enabled&&(!options.keyboard||keyboardReady),
   async setEnabled(value){
    if(disposed)return false;if(value&&starting)return starting;
    const changeEpoch=++epoch;enabled=!!value;keyboardReady=false;buttons();
    const connection=(async()=>{try{
     if(options.keyInterest)await options.keyInterest(enabled);
     if(options.keyboard){const result=await options.keyboard(enabled);if(epoch!==changeEpoch)return enabled;keyboardReady=!!result?.ok&&result.enabled!==false;if(enabled&&!keyboardReady)showError(Object.assign(Error('Mouse shortcuts could not connect. Reopen Copy Paste to retry.'),{code:'copy_paste_native',details:result?.message||result?.details}));else clear();}
    }catch(e){if(epoch===changeEpoch)showError(e);}
    if(epoch===changeEpoch){buttons();enabledState();}return enabled;})();
    starting=connection;try{return await connection;}finally{if(starting===connection)starting=null;}
   },
   shortcutState(state){if(!enabled||state.enabled)return;epoch++;keyboardReady=false;showError(Object.assign(Error('Mouse shortcuts disconnected. Reopen Copy Paste to reconnect.'),{code:'copy_paste_native',details:state.details}));buttons();enabledState();},
   shortcut(event){
    const queuedEpoch=epoch;if(!enabled||(options.keyboard&&!keyboardReady)||!['copy','paste','undo'].includes(event.command))return Promise.resolve();
    shortcutQueue=shortcutQueue.catch(()=>{}).then(()=>{if(!enabled||epoch!==queuedEpoch)return;if(event.command==='copy'){source.value=event.source==='explorer'?'explorer':'project';return run(copyPayload(source.value,event.window_handle));}return run({action:event.command,fit:'fill'});});return shortcutQueue;
   },
   filePaste(event){if(!enabled||event.phase==='keyboard')return;busy=event.phase==='working';buttons();clear();if(event.result?.error)showError(Object.assign(Error(event.result.error),{code:event.result.code,details:event.result.details}));else if(event.result)show(event.result);}
  };
  buttons();root.__storylensCopyPaste=controller;
  controller.ready=options.keyboard?controller.setEnabled(true):Promise.resolve(true);
  return controller;
 };
})();
