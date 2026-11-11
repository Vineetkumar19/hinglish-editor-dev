// Executes fixed reviewed IDs only. No model-generated selectors or page scripts.
async function storylensYouTubeTask(job,api){
  if(!/^UC[\w-]{22}$/.test(job.channel_id)||! /^[\w-]{11}$/.test(job.video_id))throw Error('Invalid reviewed YouTube IDs.');
  if(!await chrome.permissions.contains({origins:['https://studio.youtube.com/*']}))throw Error('Enable YouTube Studio access in the extension popup.');
  const contentTab=job.video_kind==='long'?'upload':'short';
  const state=await chrome.storage.local.get('youtubeWorkTabId');let tab;
  if(state.youtubeWorkTabId){try{tab=await chrome.tabs.get(state.youtubeWorkTabId)}catch(_){}}
  if(!tab?.url?.startsWith('https://studio.youtube.com/')){
    const open=await chrome.tabs.query({url:'https://studio.youtube.com/*'});
    tab=open.length===1?open[0]:await chrome.tabs.create({url:'https://studio.youtube.com/',active:true});
  }
  await chrome.storage.local.set({youtubeWorkTabId:tab.id});
  if(Number.isInteger(tab.windowId)){
    const window=await chrome.windows.get(tab.windowId);
    await chrome.windows.update(tab.windowId,{focused:true,...(window.state==='minimized'?{state:'normal'}:{})});
  }
  await chrome.tabs.update(tab.id,{active:true});
  const url=`https://studio.youtube.com/channel/${job.channel_id}/videos/${contentTab}`;
  // A channel-specific URL cannot select a Google/brand identity. Studio can
  // reject it before the switcher exists. Load the current session first;
  // navigate to the reviewed content list only after exact identity readback.
  await chrome.tabs.update(tab.id,{url:'https://studio.youtube.com/',active:true});
  const pause=ms=>new Promise(r=>setTimeout(r,ms));
  const phase=async(status,message)=>{const p=await api('phase',{id:job.id,lease:job.lease,status,message});if(p.stop)throw Error('Stopped before the next Studio action.');};
  const send=async(action,selection=job)=>{
    await phase('running','YouTube Studio: '+action);
    const result=await chrome.tabs.sendMessage(tab.id,{source:'storylens-youtube',action,job:selection});
    if(!result?.ok)throw Error('Studio '+action+': '+(result?.error||'Controls are unavailable.'));return result;
  };
  let loaded=false,switchStarted=0,reset=false,targets=null,pendingSwitch='',choice=0,choices=1;const switchTrace=[];
  for(let i=0;i<180;i++){
    try{
      const current=await chrome.tabs.get(tab.id);
      // Chrome may still expose about:blank, a hidden URL, or the previous
      // document while pendingUrl points to Studio. None proves sign-out.
      const pending=current.pendingUrl||'',visible=current.url||'';
      const loading=current.status==='loading'||pending.startsWith('https://studio.youtube.com/')||!visible||visible==='about:blank';
      if(!loading&&!visible.startsWith('https://studio.youtube.com/')){
        let origin;try{origin=new URL(visible)}catch(_){}
        if(origin?.hostname==='accounts.google.com'||origin?.hostname==='www.youtube.com'&&origin.pathname.startsWith('/signin'))
          throw Error('Studio sign-in is required. Open the existing Studio tab in this Chrome profile and complete sign-in yourself. No schedule was submitted.');
        throw Error('Studio opened an unexpected page. Return the existing tab to YouTube Studio; no schedule was submitted.');
      }
      if(current.status==='complete'&&!loading){
        await chrome.scripting.executeScript({target:{tabId:tab.id},files:['youtube-dom.js']});
        const identity=await send('channel');
        if(switchTrace.at(-1)!==identity.channel_id)switchTrace.push(identity.channel_id);
        if(targets===null)targets=job.switch_via&&identity.channel_id===job.channel_id?[{...job,...job.switch_via},job]:[job];
        while(targets.length&&identity.channel_id===targets[0].channel_id){targets.shift();pendingSwitch='';switchStarted=0;choice=0;choices=1;}
        if(targets.length){
          const selection=targets[0];
          if(pendingSwitch===selection.channel_id&&Date.now()-switchStarted>15000){
            if(choice+1>=choices)throw Error('Studio did not switch to the reviewed channel. No schedule was sent.');
            choice++;pendingSwitch='';
          }
          if(pendingSwitch!==selection.channel_id){
            pendingSwitch=selection.channel_id;
            switchStarted=Date.now();
            await phase('running','Switching YouTube Studio to the reviewed channel.');
            for(const action of ['accountMenu','switchMenu','switchChannel']){
              const result=await send(action,{...selection,channel_choice:choice});
              if(action==='switchChannel')choices=result.candidate_count||1;
              await studioClick(tab.id,result.control);
            }
          }
          await pause(700);continue;
        }
        if(!reset){await send('reset');reset=true;}
        if(!current.url.startsWith(url)){await chrome.tabs.update(tab.id,{url,active:true});await pause(700);continue;}
        const response=await send('inspect');if(response.ready){loaded=true;break;}
        // Uploads can be absent from an already-open Studio list. Re-reading
        // that same DOM forever cannot discover them: refresh this ONE tab,
        // strictly before opening a visibility control or submitting anything.
        if([0,20,50].includes(i)){
          await phase('running','Refreshing Studio’s upload list for this saved video.');
          await chrome.tabs.reload(tab.id);
        }
      }
    }catch(e){if(/Stopped|sign-in|verification|unexpected page|ambiguous|no channel was selected|did not switch/i.test(e.message)||i>15&&/different channel/i.test(e.message))throw e;}
    await pause(700);
  }
  if(!loaded)throw Error('The newly uploaded video is not visible in the selected Studio channel. No schedule was sent.');
  if(job.action==='youtube_weekly_metadata')return storylensWeeklyYouTubeTask(job,api,tab,switchTrace);
  if(job.action==='youtube_private'){
    const state=await send('privateInspect');
    if(!state.already_private){
      const visibility=await send('open');await studioClick(tab.id,visibility.control);await send('opened');
      const selection=await send('private');await studioClick(tab.id,selection.control);await send('privateReady');
    }
    await phase('sharing','Keeping this reviewed test upload private.');
    if(!state.already_private){
      const result=await chrome.tabs.sendMessage(tab.id,{source:'storylens-youtube',action:'commitPrivate',job});
      if(!result?.ok)throw Error(result?.error||'Private-only save needs independent verification.');
    }
    await api('finish',{id:job.id,lease:job.lease,result:{status:'submitted',video_id:job.video_id,
      channel_id:job.channel_id,publish_at:'',private_only:true,switch_trace:switchTrace,
      message:'Private-only save submitted; waiting for independent YouTube verification.'}});
    return;
  }
  if(job.action==='youtube_metadata'){
    const entry=await send('editLink');await studioClick(tab.id,entry.control);
    let fields;
    for(let i=0;i<30;i++){
      try{fields=await send('copyInspect');break}catch(e){if(/changed since|different channel/.test(e.message))throw e;await pause(700)}
    }
    if(!fields)throw Error('The saved video details did not open; no copy was changed.');
    if(!fields.already_matches){
      for(const key of ['title','description']){
        const input=await send('copyField',{...job,copy_field:key});
        await studioType(tab.id,input.control,job.metadata[key],'Tab');
      }
      await send('copyReady');await phase('sharing','Saving the reviewed title and description on this existing video.');
      const result=await chrome.tabs.sendMessage(tab.id,{source:'storylens-youtube',action:'copyCommit',job});
      if(!result?.ok)throw Error(result?.error||'Copy save outcome needs verification.');
    }else await phase('sharing','The requested copy is already present; verifying the existing save.');
    await api('finish',{id:job.id,lease:job.lease,result:{status:'submitted',video_id:job.video_id,
      channel_id:job.channel_id,publish_at:'',switch_trace:switchTrace,message:'Copy save submitted; awaiting independent YouTube readback.'}});
    return;
  }
  let opened=false,submitted=false;
  try{
  const visibility=await send('open');
  await studioClick(tab.id,visibility.control);
  await send('opened');opened=true;
  if(job.publish_now){
    const selection=await send('public');await studioClick(tab.id,selection.control);
    await send('publicReady');
    await phase('sharing','Publishing this reviewed video once.');submitted=true;
    const result=await chrome.tabs.sendMessage(tab.id,{source:'storylens-youtube',action:'commitPublic',job});
    if(!result?.ok)throw Error(result?.error||'Publication outcome needs verification.');
    await api('finish',{id:job.id,lease:job.lease,result:{status:'submitted',video_id:job.video_id,
      channel_id:job.channel_id,publish_at:'',switch_trace:switchTrace,message:'Studio publication submitted; waiting for independent YouTube verification.'}});
    return;
  }
  await send('expand');
  const date=await send('date');
  const instant=new Date(job.publish_at);
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(instant).map(p=>[p.type,p.value]));
  const month=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(parts.month)-1];
  const dateText=date.date_order==='day_first'?`${Number(parts.day)} ${month} ${parts.year}`:`${month} ${Number(parts.day)}, ${parts.year}`;
  await studioType(tab.id,date.control,dateText,'Enter');
  const clock=await send('time');await studioType(tab.id,clock.control,`${parts.hour}:${parts.minute}`,'Tab');
  const ready=await send('ready');if(!ready.ready)throw Error('Studio did not confirm the requested date, time and channel.');
  if(job.action==='youtube_schedule_preview'){
    await send('cancel');
    await api('finish',{id:job.id,lease:job.lease,result:{status:'complete',video_id:job.video_id,
      channel_id:job.channel_id,publish_at:job.publish_at,controls_verified:true,driver_version:ready.driver_version,
      switch_trace:switchTrace,
      message:'Studio date, time, timezone and exact video verified in preview. Changes cancelled; nothing scheduled.'}});
    return;
  }
  await phase('sharing','Submitting the reviewed schedule once.');
  submitted=true;
  const result=await chrome.tabs.sendMessage(tab.id,{source:'storylens-youtube',action:'commit',job});
  if(!result?.ok)throw Error(result?.error||'Schedule outcome needs verification.');
  await api('finish',{id:job.id,lease:job.lease,result:{status:'submitted',video_id:job.video_id,
    channel_id:job.channel_id,publish_at:job.publish_at,switch_trace:switchTrace,message:'Studio schedule submitted; waiting for independent YouTube verification.'}});
  }catch(error){if(opened&&!submitted){try{await send('cancel')}catch(_){}}throw error;}
}
async function studioClick(tabId,control){
  const tab=await chrome.tabs.get(tabId);
  if(!tab.url?.startsWith('https://studio.youtube.com/')||!/^\[data-storylens-click="[A-Za-z0-9_-]+"\]$/.test(control?.selector||''))throw Error('Studio click target is unavailable.');
  const target={tabId};let attached=false;
  try{
    await chrome.debugger.attach(target,'1.3');attached=true;
    // Resolve geometry AFTER the debugging banner changes the viewport.
    const {root}=await chrome.debugger.sendCommand(target,'DOM.getDocument',{depth:0});
    const {nodeId}=await chrome.debugger.sendCommand(target,'DOM.querySelector',{nodeId:root.nodeId,selector:control.selector});
    if(!nodeId)throw Error('The reviewed Studio visibility control disappeared.');
    await chrome.debugger.sendCommand(target,'DOM.scrollIntoViewIfNeeded',{nodeId});
    const {model}=await chrome.debugger.sendCommand(target,'DOM.getBoxModel',{nodeId});
    const q=model?.content;
    if(!q||q.length!==8||!q.every(Number.isFinite)||model.width<=0||model.height<=0)throw Error('Studio visibility control has no visible click target.');
    const x=(q[0]+q[2]+q[4]+q[6])/4,y=(q[1]+q[3]+q[5]+q[7])/4;
    await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mouseMoved',x,y});
    for(const type of ['mousePressed','mouseReleased'])await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type,x,y,button:'left',clickCount:1});
  }finally{if(attached)await chrome.debugger.detach(target).catch(()=>{});}
}
async function studioType(tabId,control,text,lastKey){
  const tab=await chrome.tabs.get(tabId);
  if(!tab.url?.startsWith('https://studio.youtube.com/')||!/^(?:input|\[contenteditable="true"\])\[data-storylens-input="[A-Za-z0-9_-]+"\]$/.test(control?.selector||''))throw Error('Studio input is unavailable.');
  const target={tabId};let attached=false;
  try{
    await chrome.debugger.attach(target,'1.3');attached=true;
    // Attaching can resize Chrome through its debugging banner. Resolve and
    // focus the exact marked input after attachment instead of stale pixels.
    const {root}=await chrome.debugger.sendCommand(target,'DOM.getDocument',{depth:0});
    const {nodeId}=await chrome.debugger.sendCommand(target,'DOM.querySelector',{nodeId:root.nodeId,selector:control.selector});
    if(!nodeId)throw Error('The reviewed Studio input disappeared before typing.');
    await chrome.debugger.sendCommand(target,'DOM.focus',{nodeId});
    for(const type of ['keyDown','keyUp'])await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type,key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2});
    await chrome.debugger.sendCommand(target,'Input.insertText',{text});
    const keyText=lastKey==='Enter'?'\r':'';
    await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type:keyText?'keyDown':'rawKeyDown',key:lastKey,code:lastKey,
      windowsVirtualKeyCode:lastKey==='Enter'?13:9,text:keyText,unmodifiedText:keyText});
    await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type:'keyUp',key:lastKey,code:lastKey,windowsVirtualKeyCode:lastKey==='Enter'?13:9});
  }finally{if(attached)await chrome.debugger.detach(target).catch(()=>{});}
}
