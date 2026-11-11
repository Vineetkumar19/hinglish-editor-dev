// Bounded operations only. No model-supplied scripts, URLs, selectors or filesystem paths.
let busy=false;
importScripts('youtube.js');
importScripts('youtube-weekly.js');
importScripts('instagram_analytics_worker.js');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const disconnected=e=>/receiving end does not exist|message port closed|frame was removed|cannot access contents/i.test(e?.message||'');
async function instagramPage(tabId){
  for(let attempt=0;attempt<45;attempt++){
    const tab=await chrome.tabs.get(tabId),url=tab.url||'',pending=tab.pendingUrl||'';
    // Instagram can keep loading peripheral resources after its UI is ready.
    // Let the content adapter inspect that UI (including login challenges)
    // once navigation commits instead of hiding it behind a load timeout.
    if(url.startsWith('https://www.instagram.com/')&&!pending)return tab;
    if(url&&url!=='about:blank'&&!url.startsWith('https://www.instagram.com/')&&
       !pending.startsWith('https://www.instagram.com/')){
      let origin='an unavailable page';try{origin=new URL(url).origin}catch(_){}
      throw Error('Instagram working tab opened '+origin+'; no upload was started.');
    }
    await delay(700);
  }
  throw Error('Instagram has not finished loading its working tab; no upload was started.');
}
async function workTab(account='',comments=false){
  const tabKey=comments?'commentTabId':'workTabId';
  const workTabId=(await chrome.storage.local.get(tabKey))[tabKey];let tab;
  if(workTabId){try{tab=await chrome.tabs.get(workTabId)}catch(_){}}
  if(!tab?.url?.startsWith('https://www.instagram.com/')||/^\/(?:direct|accounts)\//.test(new URL(tab.url).pathname)){
    const open=comments?[]:await chrome.tabs.query({url:'https://www.instagram.com/*'});
    // An inbox or manual browsing tab is not a competing publishing worker.
    // Prefer the requested profile; otherwise create one owned working tab.
    const profiles=open.filter(t=>{
      const path=new URL(t.url).pathname;
      return path==='/'||(/^\/[A-Za-z0-9._]+\/(?:reels\/)?$/.test(path)&&!/^\/(?:direct|accounts|reels|explore|stories)\//.test(path));
    });
    const matches=account?profiles.filter(t=>new URL(t.url).pathname==='/'+account+'/'):[];
    tab=matches.length===1?matches[0]:profiles.length===1?profiles[0]:
      await chrome.tabs.create({url:'https://www.instagram.com/'+(account?account+'/':''),active:true});
  }
  await chrome.storage.local.set({[tabKey]:tab.id});
  if(Number.isInteger(tab.windowId)){
    const window=await chrome.windows.get(tab.windowId);
    await chrome.windows.update(tab.windowId,{focused:true,...(window.state==='minimized'?{state:'normal'}:{})});
  }
  await chrome.tabs.update(tab.id,{active:true});return instagramPage(tab.id);
}
async function api(action,body={}){
  const {port,key}=await chrome.storage.local.get(['port','key']);
  if(!key||!Number.isInteger(port)||port<1024||port>65535)throw Error('Connect the extension to Storylens first.');
  const response=await fetch(`http://127.0.0.1:${port}/api/local-browser/worker/${action}`,{method:'POST',headers:{'Content-Type':'application/json','X-Storylens-Browser':key},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Editor connection unavailable.');return data;
}
async function command(tabId,action,data={}){
  const result=await chrome.tabs.sendMessage(tabId,{source:'storylens',action,...data});
  if(!result?.ok)throw Error(result?.error||'Instagram did not respond.');return result;
}
async function reconnect(tabId){
  // Extension reloads invalidate the old page listener. Reattach only our
  // packaged adapter, then let the normal account and composer checks run.
  const tab=await instagramPage(tabId);
  if(!await chrome.permissions.contains({origins:['https://www.instagram.com/*']}))
    throw Error('Storylens does not have Instagram host access in Chrome. No upload was started.');
  try{await chrome.scripting.executeScript({target:{tabId},files:['dom-checks.js','analytics-dom.js','instagram.js']})}
  catch(e){throw Error('Instagram adapter could not attach to '+new URL(tab.url).origin+
    ' (tab '+tabId+', '+(tab.status||'ready')+'): '+e.message)}
}
async function readReceipt(tabId,request){
  for(let attempt=0;attempt<3;attempt++){
    try{return await command(tabId,'verifyPublished',request)}
    catch(e){
      if(!disconnected(e)||attempt===2)throw e;
      await delay(1000);await reconnect(tabId);
    }
  }
}
async function step(job,tabId,action,data={}){
  const message=action==='inspect'?'Checking the signed-in account.':
    ['switch','switchMenu','switchAccount'].includes(action)?'Switching to the requested Instagram account.':
    action==='profile'?'Loading the destination profile.':
    action==='uploaded'?'Loading the selected video in Instagram.':'Preparing the requested reel in Chrome.';
  const phase=await api('phase',{id:job.id,lease:job.lease,status:'running',message});
  if(phase.stop)throw Error('Stopped before publishing.');
  return command(tabId,action,data);
}
async function nativeFile(tabId,path,control,id){
  if(typeof path!=='string'||!path.toLowerCase().endsWith('.mp4'))throw Error('The selected MP4 is unavailable.');
  if(!control||!Number.isFinite(control.x)||!Number.isFinite(control.y)||control.x<0||control.y<0)throw Error('The reel file selection control is unavailable.');
  const tab=await chrome.tabs.get(tabId);
  if(!tab.url?.startsWith('https://www.instagram.com/'))throw Error('Native upload is limited to the dedicated Instagram tab.');
  const target={tabId};let attached=false,listener=null,timer=null;
  try{
    await chrome.debugger.attach(target,'1.3');attached=true;
    const {root}=await chrome.debugger.sendCommand(target,'DOM.getDocument',{depth:0});
    const {nodeId}=await chrome.debugger.sendCommand(target,'DOM.querySelector',{nodeId:root.nodeId,selector:'[role="dialog"] input[type="file"][accept*="video/"]'});
    if(!nodeId)throw Error('The reel upload input is unavailable.');
    const {node}=await chrome.debugger.sendCommand(target,'DOM.describeNode',{nodeId});
    await chrome.debugger.sendCommand(target,'Page.enable');
    await chrome.debugger.sendCommand(target,'Page.setInterceptFileChooserDialog',{enabled:true});
    await delay(250);
    const measured=await command(tabId,'fileControl',{id});control=measured.uploadControl;
    if(!control||!Number.isFinite(control.x)||!Number.isFinite(control.y))throw Error('The reel file selection control is unavailable.');
    const chooser=new Promise((resolve,reject)=>{
      listener=(source,method,params)=>{if(source.tabId===tabId&&method==='Page.fileChooserOpened')resolve(params);};
      chrome.debugger.onEvent.addListener(listener);
      timer=setTimeout(()=>reject(Error('Chrome did not open the reel file chooser.')),10000);
    });
    // Match the normal file chooser: a trusted click preserves the browser's media activation.
    await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mousePressed',x:control.x,y:control.y,button:'left',clickCount:1});
    await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mouseReleased',x:control.x,y:control.y,button:'left',clickCount:1});
    const selected=await chooser;
    if(selected.backendNodeId!==node.backendNodeId)throw Error('Chrome opened a different file input; no video was selected.');
    await chrome.debugger.sendCommand(target,'DOM.setFileInputFiles',{backendNodeId:selected.backendNodeId,files:[path]});
  }catch(e){
    if(/not allowed/i.test(e.message))throw Error('Chrome blocked native file selection. Check Allow access to file URLs for Storylens Local Publisher in Chrome extensions.');
    throw e;
  }finally{
    if(timer)clearTimeout(timer);
    if(listener)chrome.debugger.onEvent.removeListener(listener);
    if(attached){await chrome.debugger.sendCommand(target,'Page.setInterceptFileChooserDialog',{enabled:false}).catch(()=>{});await chrome.debugger.detach(target).catch(()=>{});}
  }
}
async function nativeSwitch(tabId,job){
  const tab=await instagramPage(tabId);
  if(!tab.url.startsWith('https://www.instagram.com/'))throw Error('Account switching is limited to Instagram.');
  const target={tabId};let attached=false;
  try{
    await chrome.debugger.attach(target,'1.3');attached=true;
    // Attaching can change the viewport through Chrome's debugger infobar.
    // Measure after attach and retain one connection for the whole menu flow.
    await delay(250);
    for(const action of ['switch','switchMenu','switchAccount']){
      const {control}=await step(job,tabId,action,{account:job.account,labels:job.switch_labels?.[job.account]||[],exactAccount:job.action.startsWith('instagram_comment')||job.action==='instagram_analytics_read'});
      if(!control||!Number.isFinite(control.x)||!Number.isFinite(control.y)||control.x<0||control.y<0)
        throw Error('The Instagram account-switch control is unavailable.');
      await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mousePressed',x:control.x,y:control.y,button:'left',clickCount:1});
      await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mouseReleased',x:control.x,y:control.y,button:'left',clickCount:1});
    }
  }finally{if(attached)await chrome.debugger.detach(target).catch(()=>{});}
}
async function nativeCaption(tabId,text){
  if(typeof text!=='string'||!text.trim()||text.length>2200)throw Error('The queued caption is invalid.');
  const tab=await chrome.tabs.get(tabId);
  if(!tab.url?.startsWith('https://www.instagram.com/'))throw Error('Caption entry is limited to the dedicated Instagram tab.');
  const target={tabId};let attached=false;
  try{
    await chrome.debugger.attach(target,'1.3');attached=true;
    const {root}=await chrome.debugger.sendCommand(target,'DOM.getDocument',{depth:0});
    const {nodeId}=await chrome.debugger.sendCommand(target,'DOM.querySelector',{nodeId:root.nodeId,selector:'[role="dialog"] [contenteditable="true"][aria-label*="caption"], [role="dialog"] textarea[aria-label*="caption"]'});
    if(!nodeId)throw Error('The Instagram caption field is unavailable.');
    await chrome.debugger.sendCommand(target,'DOM.focus',{nodeId});
    await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type:'keyDown',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2});
    await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2});
    await chrome.debugger.sendCommand(target,'Input.insertText',{text});
    await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
    await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  }finally{if(attached)await chrome.debugger.detach(target).catch(()=>{});}
}
async function submitCommentReply(tabId,job){
  const {id,account,source_url,comment_id,author,comment_text,reply_text}=job;
  const details={id,account,source_url,comment_id,author,comment_text,reply_text};
  const target={tabId};
  let attached=false;
  async function trustedClick(control){
    if(!control||!Number.isFinite(control.x)||!Number.isFinite(control.y)||control.x<0||control.y<0)
      throw Error('The exact Instagram reply control is unavailable.');
    await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mousePressed',x:control.x,y:control.y,button:'left',clickCount:1});
    await chrome.debugger.sendCommand(target,'Input.dispatchMouseEvent',{type:'mouseReleased',x:control.x,y:control.y,button:'left',clickCount:1});
  }
  try{
    const tab=await instagramPage(tabId);
    if(new URL(tab.url).origin!=='https://www.instagram.com')throw Error('The reply tab left Instagram.');
    await chrome.debugger.attach(target,'1.3');
    attached=true;
    const prepared=await step(job,tabId,'commentReplyPrepare',details);
    if(prepared.already_replied){
      await api('finish',{id:job.id,lease:job.lease,result:{status:'needs_review',message:'This comment already has a creator reply.'}});
      return;
    }
    await trustedClick(prepared.control);
    for(const type of ['keyDown','keyUp'])
      await chrome.debugger.sendCommand(target,'Input.dispatchKeyEvent',{type,key:'End',code:'End',windowsVirtualKeyCode:35,modifiers:2});
    await chrome.debugger.sendCommand(target,'Input.insertText',{text:(prepared.needs_space?' ':'')+job.reply_text});
    await step(job,tabId,'commentReplyReady',details);
    const permission=await api('phase',{id:job.id,lease:job.lease,status:'sharing',message:'Submitting the verified Instagram comment reply once.'});
    if(permission.stop)throw Error('The Instagram reply was paused before submission.');
    const ready=await command(tabId,'commentReplyReady',details);
    await trustedClick(ready.control);
    for(let attempt=0;attempt<15;attempt++){
      await delay(750);
      const receipt=await command(tabId,'commentReplyReceipt',details);
      if(receipt.confirmed){
        await api('finish',{id:job.id,lease:job.lease,result:{...receipt,status:'complete',message:'Instagram confirmed the exact reply.'}});
        return;
      }
    }
    throw Error('Instagram did not confirm the reply. The same comment will not be retried.');
  }finally{if(attached)await chrome.debugger.detach(target).catch(()=>{});}
}
async function run(){
  if(busy)return;busy=true;let job=null,uploadTab=null,composerStarted=false,shareStarted=false;
  try{
    const prior=(await chrome.storage.local.get('active')).active;
    if(prior){await api('finish',{id:prior.id,lease:prior.lease,result:{status:'needs_review',message:'Chrome restarted during this task. Check the requested platform before any new attempt.'}});await chrome.storage.local.remove('active');}
    const studioAllowed=await chrome.permissions.contains({origins:['https://studio.youtube.com/*']});
    const task=await api('claim',{version:chrome.runtime.getManifest?.().version||'0.4.0',supports:['instagram_analytics_read','instagram_comments_read','instagram_comments_reply','instagram_comments_window',...(studioAllowed?['youtube_schedule','youtube_preview','youtube_publish','youtube_metadata','youtube_private','youtube_weekly_metadata']:[])]});job=task.job;if(!job)return;
    await chrome.storage.local.set({active:job,message:'Working on '+(job.account?'@'+job.account:'Instagram account check')});
    if(['youtube_schedule','youtube_schedule_preview','youtube_metadata','youtube_private','youtube_weekly_metadata'].includes(job.action)){await storylensYouTubeTask(job,api);return;}
    if(job.action==='instagram_analytics_read'){await storylensInstagramAnalytics(job);return;}
    if(job.action==='instagram_comments_read'&&!job.source_url){
      const tabs=await chrome.tabs.query({url:'https://www.instagram.com/*'});
      const loaded=tabs.filter(tab=>tab.url&&!tab.pendingUrl&&!tab.discarded);
      const postTabs=loaded.filter(tab=>{
        const post=new URL(tab.url).pathname.match(/^\/(?:([A-Za-z0-9._]+)\/)?(?:reel|p)\/[A-Za-z0-9_-]{1,64}\/?$/);
        return post&&(!post[1]||post[1]===job.account);
      });
      const focused=postTabs.length>1?await chrome.tabs.query({active:true,lastFocusedWindow:true}):[];
      const profileTabs=loaded.filter(tab=>new URL(tab.url).pathname.replace(/\/+$/,'')==='/'+job.account);
      const tab=postTabs.find(tab=>tab.id===focused[0]?.id)||
        (postTabs.length===1?postTabs[0]:!postTabs.length&&profileTabs.length===1?profileTabs[0]:null);
      if(!tab){
        const help=postTabs.length>1?'Several Instagram post tabs are open. Select the exact post tab.':
          loaded.length?'Open an individual post or Reel from @'+job.account+' rather than the feed.':
            'No Instagram tab is available in this paired Chrome profile.';
        throw Error(help);
      }
      let result;
      try{result=await command(tab.id,'commentsRead',{account:job.account})}
      catch(e){
        if(!disconnected(e))throw e;
        await reconnect(tab.id);
        result=await command(tab.id,'commentsRead',{account:job.account});
      }
      await api('finish',{id:job.id,lease:job.lease,result:{...result,status:'complete',message:'Read visible Instagram comments with exact platform IDs.'}});
      return;
    }
    // Reuse one working tab across accounts and jobs; never create a tab per upload.
    const commentJob=['instagram_comment_posts','instagram_comments_read','instagram_comments_reply'].includes(job.action);
    const tab=await workTab(job.account,commentJob);
    uploadTab=tab.id;
    if(commentJob)await reconnect(tab.id);
    if(job.action==='verify_reel'){
      // Read the already-open post. Never enter a composer or press Share.
      const request={account:job.account,caption:job.caption,after:job.after,before:job.before};
      const receipt=await readReceipt(tab.id,request);
      await api('finish',{id:job.id,lease:job.lease,result:{...receipt,status:'complete',message:'Existing Instagram post verified; no upload repeated.'}});
      return;
    }
    let info;
    for(let i=0;i<20;i++){
      try{await command(tab.id,'idle');info=await step(job,tab.id,'inspect');if(info.account)break;}
      catch(e){
        if(disconnected(e)&&i===0){await reconnect(tab.id);continue;}
        if(i===19||/login|verification|not finished loading/i.test(e.message))throw e;
      }
      await delay(700);
    }
    if(!info.account)throw Error('Sign in to Instagram in Chrome, then request an account check again.');
    const switchTrace=[info.account];
    if(job.switch_via&&info.account===job.account){
      if(job.switch_via===job.account)throw Error('The alternate account must differ from the destination.');
      try{await nativeSwitch(tab.id,{...job,account:job.switch_via})}
      catch(e){if(!disconnected(e))throw e;}
      let stable=0;
      for(let i=0;i<60;i++){
        await delay(1000);
        try{info=await step(job,tab.id,'inspect');stable=info.account===job.switch_via?stable+1:0;if(stable>=3)break}
        catch(e){stable=0;if(!disconnected(e))throw e;}
      }
      if(stable<3)throw Error('Instagram did not confirm the alternate account; no upload was started.');
      switchTrace.push(info.account);
    }
    if(job.account&&info.account!==job.account){
      for(let attempt=0;attempt<2;attempt++){
        try{await nativeSwitch(tab.id,job);break}
        catch(e){
          if(disconnected(e))break;
          if(attempt||!/control unavailable: Switch accounts|account switcher is unavailable/i.test(e.message))throw e;
          // Instagram sometimes leaves a rendered profile with a failed app
          // bootstrap. Reuse and refresh this tab once, before any composer.
          await command(tab.id,'idle');
          await api('phase',{id:job.id,lease:job.lease,status:'running',message:'Refreshing Instagram because its account menu did not respond.'});
          await chrome.tabs.reload(tab.id);await instagramPage(tab.id);await reconnect(tab.id);
          await command(tab.id,'idle');info=await step(job,tab.id,'inspect');
          if(info.account===job.account)break;
        }
      }
      let stable=0;
      for(let i=0;i<90;i++){
        await delay(1000);
        try{info=await step(job,tab.id,'inspect');stable=info.account===job.account?stable+1:0;if(stable>=3)break;}
        catch(e){stable=0;if(!disconnected(e)||i===89)throw e;}
      }
      if(stable<3)throw Error('Instagram could not confirm the requested account after switching. No post was shared.');
      switchTrace.push(info.account);}
    if(!commentJob&&(!['reel','preview','inspect'].includes(job.action)||(job.action!=='inspect'&&!task.media)))throw Error('This browser action is not supported.');
    // A cached sidebar can show an account after its server session expires.
    // An account check must also load that account's real profile grid.
    const destination=job.account||info.account;
    if(commentJob&&job.source_url){
      // Open the discovered permalink in the existing working tab. A profile
      // tile can open a variant modal that hides the post author or timestamp.
      const source=new URL(job.source_url);
      const owned=source.pathname.match(/^\/([A-Za-z0-9._]+)\/(?:reel|p)\/([A-Za-z0-9_-]{1,64})\/$/);
      if(source.origin!=='https://www.instagram.com'||owned?.[1]!==destination||source.search||source.hash)
        throw Error('Choose an owned Instagram post.');
      await chrome.tabs.update(tab.id,{url:source.href});
      await reconnect(tab.id);
      const verify={account:destination,source_id:owned[2]};
      try{await step(job,tab.id,'verifyCommentPost',verify)}
      catch(error){
        if(!source.pathname.includes('/reel/')||!/could not verify the open post/i.test(error.message))throw error;
        // The post view can expose metadata absent from Instagram’s Reel view.
        source.pathname='/'+destination+'/p/'+owned[2]+'/';
        await chrome.tabs.update(tab.id,{url:source.href});
        await reconnect(tab.id);
        await step(job,tab.id,'verifyCommentPost',verify);
      }
      if(job.action==='instagram_comments_read'){
        const result=await step(job,tab.id,'commentsRead',{account:destination,expand:true,cutoff:job.cutoff});
        await api('finish',{id:job.id,lease:job.lease,result:{...result,status:'complete',
          message:result.expired_source?'Expired Instagram post skipped.':'Chrome checked comments on the exact post.'}});
      }else{
        await submitCommentReply(tab.id,job);
      }
      return;
    }
    try{await step(job,tab.id,'profile',{account:destination})}
    catch(e){
      if(!/has not opened the destination profile|has not loaded the existing post list/i.test(e.message))throw e;
      // A switched session may render its header while the profile query fails.
      // Refresh once before any composer/media exists; never replay Share.
      await command(tab.id,'idle');
      await api('phase',{id:job.id,lease:job.lease,status:'running',message:'Instagram could not load the profile. Refreshing it once before uploading.'});
      await chrome.tabs.reload(tab.id);await instagramPage(tab.id);await reconnect(tab.id);
      await command(tab.id,'idle');await step(job,tab.id,'profile',{account:destination});
    }
    if(job.action==='inspect'){
      await api('finish',{id:job.id,lease:job.lease,result:{status:'complete',account:destination,switch_trace:switchTrace,message:'Chrome is signed in as @'+destination+'.'}});return;
    }
    if(job.action==='instagram_comment_posts'){
      const result=await step(job,tab.id,'commentPosts',{account:job.account});
      await api('finish',{id:job.id,lease:job.lease,result:{...result,status:'complete',message:'Chrome verified the Instagram profile and its posts.'}});
      return;
    }
    const selection=await step(job,tab.id,'start',{id:job.id,name:task.media.name});
    composerStarted=true;
    await nativeFile(tab.id,task.media.path,selection.uploadControl,job.id);
    await step(job,tab.id,'uploaded',{id:job.id});
    await step(job,tab.id,'crop');
    await step(job,tab.id,'details',{caption:job.caption,account:job.account});
    if(job.caption)await nativeCaption(tab.id,job.caption);
    const ready=await step(job,tab.id,'ready',{account:job.account,caption:job.caption});
    if(!ready.ready)throw Error('Instagram did not confirm the account, caption and reel preview.');
    if(job.action==='preview'){
      await api('finish',{id:job.id,lease:job.lease,result:{status:'complete',account:job.account,message:'Portrait video and caption preview are ready in Chrome. Nothing was published.'}});
      await chrome.storage.local.set({message:'Preview ready. Nothing was published.'});return;
    }
    // Persist the ambiguity boundary BEFORE clicking Share. Never auto-retry Share.
    shareStarted=true;const submittedAt=Date.now()/1000;
    const sharing=await api('phase',{id:job.id,lease:job.lease,status:'sharing',message:'Instagram is processing the upload. Do not upload it again.'});
    if(sharing.stop)throw Error('Stopped before publishing.');
    await command(tab.id,'share',{id:job.id,account:job.account,caption:job.caption});
    for(let i=0;i<90;i++){
      let status;
      try{status=await command(tab.id,'result',{account:job.account,caption:job.caption});}
      catch(e){
        if(!disconnected(e))throw e;
        const receipt=await readReceipt(tab.id,{account:job.account,caption:job.caption,after:submittedAt-2,before:Date.now()/1000+60});
        status={published:true,url:receipt.url};
      }
      if(status.published){await api('finish',{id:job.id,lease:job.lease,result:{status:'published',account:job.account,url:status.url,switch_trace:switchTrace,message:'Instagram confirmed the reel was shared.'}});await chrome.storage.local.set({message:'Published to @'+job.account});return;}
      if(status.error)throw Error(status.error);
      await api('phase',{id:job.id,lease:job.lease,status:'sharing',message:'Waiting for Instagram publication confirmation.'});
      await delay(2000);
    }
    throw Error('Instagram has not confirmed publication. Check the open tab before trying again.');
  }catch(e){
    if(job&&composerStarted&&!shareStarted&&uploadTab!==null){
      try{await command(uploadTab,'abortOwned',{id:job.id})}catch(_){}
    }
    await chrome.storage.local.set({message:e.message});
    if(job){try{await api('finish',{id:job.id,lease:job.lease,result:{status:job.action==='youtube_weekly_metadata'&&(e.weekly_retryable||/sign-in|controls are unavailable|not visible in the selected Studio channel|could not establish connection|receiving end|message port|network|fetch|timed out|offline/i.test(e.message||''))?'queued':'needs_review',message:e.message}})}catch(_){}}
  }finally{if(job)await chrome.storage.local.remove('active');busy=false;if(job)setTimeout(run,300);}
}
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='storylens')run()});
chrome.runtime.onInstalled.addListener(()=>chrome.alarms.create('storylens',{periodInMinutes:.5}));
chrome.runtime.onStartup.addListener(()=>{chrome.alarms.create('storylens',{periodInMinutes:.5});run()});
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  // Content pages cannot invoke the control channel or select arbitrary media.
  if(sender.tab||!sender.url?.startsWith(chrome.runtime.getURL('popup.html')))return;
  (async()=>{
    if(message.type==='disconnect'){await chrome.storage.local.remove(['key','active']);return {message:'Disconnected. Revoke the connection in Storylens to invalidate the old code.'};}
    if(message.type==='connect'){
      if(!/^[A-Za-z0-9_-]{40,64}$/.test(message.key)||!Number.isInteger(message.port)||message.port<1024||message.port>65535)throw Error('Paste the connection code and editor port.');
      await chrome.storage.local.set({port:message.port,key:message.key});await chrome.alarms.create('storylens',{periodInMinutes:.5});
    }
    run();return {message:'Checking your local editor. Keep Chrome and Storylens open.'};
  })().then(reply,e=>reply({message:e.message}));return true;
});
