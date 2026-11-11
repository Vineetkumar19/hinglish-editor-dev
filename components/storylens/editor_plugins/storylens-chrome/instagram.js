// Read visible controls only. No cookies, credentials, private messages or hidden Instagram APIs.
(()=>{
  // Reconnecting must not install another responder with separate ownership
  // state. Keep the active adapter for this document and extension version.
  const adapterVersion='0.4.44-analytics-page-ready';
  if(globalThis.__storylensInstagramAdapter?.version===adapterVersion)return;
  if(globalThis.__storylensInstagramAdapter?.listener)
    chrome.runtime.onMessage.removeListener(globalThis.__storylensInstagramAdapter.listener);
  const parts=new Map(),sent=new Set(),priorReels=new Set();let confirmed=false,publishedHref='',ownedComposer=null,commentReply=null;
  const visible=e=>!!(e&&e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden');
  const norm=s=>(s||'').replace(/\s+/g,' ').trim();
  const name=e=>norm(e.getAttribute('aria-label')||e.innerText||e.querySelector('[aria-label]')?.getAttribute('aria-label')||e.querySelector('title')?.textContent||e.querySelector('img')?.alt);
  const controls=(label,root=document)=>[...root.querySelectorAll('button,a,[role="button"]')].filter(e=>visible(e)&&StorylensDOM.sameControl(name(e),label));
  const find=(label,root=document)=>controls(label,root).at(-1);
  const dialog=()=>[...document.querySelectorAll('[role="dialog"]')].filter(visible).at(-1);
  const pause=ms=>new Promise(r=>setTimeout(r,ms));
  async function wait(check,message,timeout=18000){const end=Date.now()+timeout;do{const value=check();if(value)return value;await pause(250)}while(Date.now()<end);throw Error(message);}
  function current(){
    return StorylensDOM.signedInAccount(document);
  }
  function guard(){
    const loginDialog=dialog()&&[...dialog().querySelectorAll('button,[role="button"]')].some(e=>
      visible(e)&&/^Continue as [A-Za-z0-9._]+$/i.test(name(e)));
    if(/\/challenge\/|\/accounts\/login\//.test(location.pathname)||document.querySelector('input[type="password"]')||loginDialog||find('Log in'))
      throw Error('Instagram needs your login or verification. Complete it yourself in Chrome.');
  }
  async function click(label,root=document){const e=await wait(()=>find(label,root),'Instagram control unavailable: '+label);e.click();}
  function point(element){const b=element.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2}}
  function assertAccount(account){guard();if(current()!==account)throw Error('Account changed. No upload was started on a different account.');}
  async function waitAccount(account){
    let consecutive=0;
    await wait(()=>{guard();consecutive=current()===account?consecutive+1:0;return consecutive>=4},
      'Instagram could not confirm the requested account after switching. No post was shared.',30000);
  }
  function captionBox(){const d=dialog();return d&&[...d.querySelectorAll('[contenteditable="true"],textarea')].find(e=>visible(e)&&/caption/i.test(e.getAttribute('aria-label')||e.getAttribute('placeholder')||''));}
  async function closeOwnedEmpty(){
    const d=dialog();
    // DOM identity is deliberate: never close a manual composer or one restored
    // after navigation, and never discard media/captions the user may be editing.
    if(!ownedComposer||d!==ownedComposer.dialog||!StorylensDOM.emptyComposer(d))return false;
    const inside=controls('Close',d),all=controls('Close');
    const close=inside.length===1?inside[0]:all.length===1?all[0]:null;
    if(!close)return false;
    close.click();
    try{await wait(()=>!dialog(),'The empty composer did not close.',3000)}catch(_){return false}
    parts.delete(ownedComposer.id);ownedComposer=null;return true;
  }
  function profilePostLinks(account){
    const pattern=new RegExp('^/(?:'+account.replace(/[.]/g,'[.]')+'/)?(reel|p)/([A-Za-z0-9_-]{1,64})/?$');
    return [...document.querySelectorAll('a[href]')].flatMap(link=>{
      const href=link.getAttribute('href');
      const match=href.match(pattern);
      const inProfile=href.startsWith('/'+account+'/')||link.closest('main,[role="main"]');
      return match&&inProfile&&visible(link)?[{link,id:match[2],url:location.origin+'/'+account+'/'+match[1]+'/'+match[2]+'/'}]:[];
    });
  }
  async function scrollProfile(account){
    if(!StorylensDOM.profileReady(document,location.pathname,account)||dialog())
      throw Error('The exact Instagram profile grid is not open.');
    const posts=new Map();
    let still=0;
    for(let page=0;page<45;page++){
      const before=posts.size;
      for(const post of profilePostLinks(account)){
        posts.set(post.id,post.url);
      }
      const surface=document.scrollingElement;
      const bottom=surface.scrollTop+innerHeight>=surface.scrollHeight-12;
      still=bottom&&posts.size===before?still+1:0;
      if(still>=3){
        if(!posts.size&&!/\b0\s+posts\b/i.test(document.querySelector('main,[role="main"]')?.innerText||''))
          throw Error('Instagram did not load the account’s post list.');
        return [...posts.values()];
      }
      window.scrollTo(0,surface.scrollHeight);
      await pause(700);
    }
    throw Error('Instagram did not finish loading the full profile grid.');
  }
  function thread(m){
    const source=new URL(m.source_url);
    const context=StorylensDOM.commentContext(document,location,m.account);
    if(!source.pathname.endsWith('/'+context.sourceId+'/'))throw Error('A different Instagram post is open.');
    const data=StorylensDOM.visibleComments(document,location,m.account).rows.find(row=>row.comment_id===m.comment_id);
    if(!data||data.author_id!==m.author||data.text!==m.comment_text)
      throw Error('The exact Instagram comment changed or is no longer visible.');
    const links=[...context.article.querySelectorAll('a[href*="comment_id="]')].filter(link=>
      new URL(link.href).searchParams.get('comment_id')===m.comment_id&&visible(link));
    const row=links.length===1?links[0].closest('li,[role="listitem"]'):null;
    if(!row)throw Error('The exact Instagram comment thread is unavailable.');
    return {...context,row};
  }
  function childReplies(row, account){
    const replies=[];
    for(const link of row.querySelectorAll('a[href*="comment_id="]')){
      const child=link.closest('li,[role="listitem"]');
      if(!child||child===row||!visible(link))continue;
      const author=[...child.querySelectorAll('a[href]')].find(a=>visible(a)&&norm(a.innerText)===account&&a.getAttribute('href')==='/'+account+'/');
      if(!author)continue;
      const id=new URL(link.href).searchParams.get('reply_comment_id')||new URL(link.href).searchParams.get('comment_id');
      
      const text=[...child.querySelectorAll('span[dir="auto"]')].filter(span=>visible(span)&&!span.closest('a,button,time,[role="button"]')&&span.closest('li,[role="listitem"]')===child).map(span=>norm(span.innerText));
      replies.push({id,text});
    }
    return replies;
  }
  function replyExpand(row){
    return [...row.querySelectorAll('button,[role="button"]')].filter(control=>visible(control)&&
      /^(?:View (?:all |more )?\d+ repl(?:y|ies)|View (?:all |more )?replies|See (?:all |more )?replies)(?:[\s(].*)?$/i.test(name(control)));
  }
  async function expandThread(m){
    for(let i=0;i<16;i++){
      const context=thread(m),expand=replyExpand(context.article);
      if(!expand.length)return context;
      expand[0].click();
      await pause(500);
    }
    throw Error('Instagram did not expose the full reply thread for duplicate protection.');
  }
  function replyField(article){
    const fields=[...article.querySelectorAll('textarea,[contenteditable="true"]')].filter(box=>
      visible(box)&&/^(?:add a comment|write a comment|reply)/i.test(box.getAttribute('aria-label')||box.getAttribute('placeholder')||''));
    return fields.length===1?fields[0]:null;
  }
  function replyPrefix(box,m){
    const value=box.value??box.innerText??'';
    const prefix='@'+m.author;
    return value.trim()===prefix?prefix+' ':null;
  }
  function replyReady(m){
    const context=thread(m),box=replyField(context.article);
    if(!commentReply||commentReply.id!==m.id||!box||commentReply.box!==box||
      norm(box.value??box.innerText)!==norm(commentReply.prefix+m.reply_text)||
      childReplies(context.row,m.account).length)
      throw Error('The Instagram reply composer or thread changed before sending.');
    const area=box.closest('form')||box.parentElement?.parentElement;
    const submit=controls('Post',area).filter(control=>!control.disabled&&control.getAttribute('aria-disabled')!=='true');
    if(submit.length!==1)throw Error('The exact Instagram reply submit control is unavailable.');
    submit[0].scrollIntoView({block:'nearest'});
    return {control:point(submit[0])};
  }
  async function execute(m){
    guard();
    if(m.action==='analyticsIdentity')return {account:current()};
    if(m.action==='analyticsProfile'){
      const data=await wait(()=>StorylensInstagramAnalytics.profile(document,location,m.account),
        'Instagram did not show the exact profile counters.',8000);
      return {...data,signed_in:current()};
    }
    if(m.action==='analyticsReels')return {content:await wait(()=>StorylensInstagramAnalytics.reels(document,location,m.account),
      'Instagram did not show recent Reels for this profile.',8000)};
    if(m.action==='analyticsAccount'||m.action==='analyticsReadReel'){
      const read=m.action==='analyticsAccount'?StorylensInstagramAnalytics.accountInsights:StorylensInstagramAnalytics.reelInsights;
      return {metrics:await wait(()=>{guard();return current()===m.account&&read(document,location)},
        'Instagram did not show the requested Insights.',9000)};
    }
    if(m.action==='analyticsOpenReel'){
      assertAccount(m.account);
      if(!/^[A-Za-z0-9_-]{1,64}$/.test(m.id)||location.pathname!==`/${m.account}/reel/${m.id}/`)
        throw Error('The selected Reel did not match the requested post.');
      const button=await wait(()=>{const visibleLinks=controls('View Insights');return visibleLinks.length===1&&visibleLinks[0]},
        'Instagram did not show one Insights button for this Reel.',6000);
      button.click();
      return {};
    }
    if(m.action==='commentPosts')return {account:m.account,posts:await scrollProfile(m.account)};
    if(m.action==='verifyCommentPost'){
      let reason='';
      try{
        await wait(()=>{
          guard();
          try{return StorylensDOM.commentContext(document,location,m.account).sourceId===m.source_id}
          catch(error){reason=error.message;return false}
        },'Instagram did not open the exact owned post.',m.timeout??8000);
      }catch(error){
        if(reason&&error.message==='Instagram did not open the exact owned post.')throw Error(reason);
        throw error;
      }
      return {};
    }
    if(m.action==='commentsRead'){
      if(!m.expand)return StorylensDOM.visibleComments(document,location,m.account);
      const context=StorylensDOM.commentContext(document,location,m.account);
      const {article}=context;
      const date=StorylensDOM.commentPostDate(context,location,m.account);
      const cutoff=Date.parse(m.cutoff);
      if(!Number.isFinite(cutoff))throw Error('The Instagram post scan requires a publication cutoff.');
      if(Date.parse(date.source_published_at)<=cutoff)
        return {account:m.account,rows:[],expired_source:true,...date};
      try{StorylensDOM.visibleComments(document,location,m.account)}
      catch(error){
        if(!/Open the comments panel/.test(error.message))throw error;
        const open=[...article.querySelectorAll('button,a,[role="button"]')].filter(control=>
          visible(control)&&/^(?:comment|comments|view (?:all )?(?:\d[\d,]* )?comments)$/i.test(name(control)));
        if(open.length!==1)throw Error('The verified Instagram post did not expose one comments control.');
        open[0].click();
        await wait(()=>{
          try{return StorylensDOM.visibleComments(document,location,m.account)}
          catch(error){if(!/Open the comments panel/.test(error.message))throw error;return null}
        },'Instagram did not expose verifiable comments after opening the panel.',8000);
      }
      for(let attempt=0;attempt<20;attempt++){
        const {article}=StorylensDOM.commentContext(document,location,m.account);
        const more=[...article.querySelectorAll('button,[role="button"]')].filter(control=>
          visible(control)&&/^(?:load more comments|view all \d+ comments|show more comments)$/i.test(name(control)));
        if(!more.length)break;
        if(more.length!==1||attempt===19)throw Error('Instagram did not expose the full comment list.');
        more[0].click();
        await pause(600);
      }
      return {...StorylensDOM.visibleComments(document,location,m.account),...date};
    }
    if(m.action==='commentReplyPrepare'){
      const context=await expandThread(m);
      if(childReplies(context.row,m.account).length)return {already_replied:true};
      const existing=replyField(context.article);
      if(existing&&norm(existing.value??existing.innerText))throw Error('An Instagram comment draft is already open.');
      const reply=controls('Reply',context.row).filter(control=>control.closest('li,[role="listitem"]')===context.row);
      if(reply.length!==1)throw Error('The exact Instagram Reply control is unavailable.');
      reply[0].click();
      const box=await wait(()=>replyField(thread(m).article),'Instagram did not open the reply composer.');
      const prefix=await wait(()=>replyPrefix(box,m),'Instagram did not identify the selected reply recipient.',4000);
      commentReply={id:m.id,box,prefix};
      box.scrollIntoView({block:'nearest'});
      return {control:point(box),needs_space:!(box.value??box.innerText).endsWith(' ')};
    }
    if(m.action==='commentReplyReady')return replyReady(m);
    if(m.action==='commentReplyReceipt'){
      const context=await expandThread(m);
      const expected=[norm(m.reply_text),norm('@'+m.author+' '+m.reply_text)];
      const matching=childReplies(context.row,m.account).filter(reply=>/^\d{1,30}$/.test(reply.id||'')&&reply.text.some(value=>expected.includes(value)));
      if(matching.length!==1)return {confirmed:false};
      return {confirmed:true,account:m.account,parent_id:m.comment_id,source_url:m.source_url,text:m.reply_text,reply_id:matching[0].id};
    }
    if(m.action==='idle'){
      await closeOwnedEmpty();const d=dialog();
      if(d){
        if(captionBox()||/^(?:Create new post|Crop|Edit|New reel)$/.test(norm(d.querySelector('h1,[role="heading"]')?.innerText)))throw Error('An unfinished Instagram composer is open. Finish or close it before starting the next task; no extra tab was opened.');
        if(d.querySelector('article')||/Switch accounts/.test(d.innerText)){await click('Close');await wait(()=>!dialog(),'Close the current Instagram dialog first.');}
        else throw Error('Finish the open Instagram dialog first; no extra tab was opened.');
      }
      return {};
    }
    if(m.action==='inspect')return {account:await wait(()=>{guard();return current();},'Instagram has not finished loading the signed-in profile. Check the open tab.')};
    if(m.action==='switch'){
      if(dialog())throw Error('Close the open Instagram dialog before switching accounts.');
      // The profile bio also has a "more" button. Only the navigation's
      // settings control may open account switching.
      const settings=[...document.querySelectorAll('button,a,[role="button"]')].find(e=>visible(e)&&
        !e.closest('main,header,article,[role="main"],[role="dialog"]')&&
        (StorylensDOM.sameControl(name(e),'Settings')||StorylensDOM.sameControl(name(e),'More'))&&
        (StorylensDOM.sameControl(e.getAttribute('aria-label'),'Settings')||e.querySelector('[aria-label="Settings"],svg title')));
      if(!settings)throw Error('Instagram account switcher is unavailable.');return {control:point(settings)};
    }
    if(m.action==='switchMenu'){
      const control=await wait(()=>find('Switch accounts'),'Instagram control unavailable: Switch accounts');
      return {control:point(control)};
    }
    if(m.action==='switchAccount'){
      const row=await wait(()=>StorylensDOM.accountSwitchRow(dialog(),m.account,m.labels,m.exactAccount),'Sign in to @'+m.account+' in Chrome first.');
      return {control:point(row)};
    }
    if(m.action==='profile'){
      await waitAccount(m.account);
      if(location.pathname!=='/'+m.account+'/'){
        const profile=[...document.querySelectorAll('a[href]')].find(a=>visible(a)&&!a.closest('main,header,article,[role="main"],[role="dialog"]')&&a.getAttribute('href')==='/'+m.account+'/'&&/profile picture/i.test(a.querySelector('img')?.alt||''));
        if(!profile)throw Error('The signed-in profile link is unavailable.');profile.click();
      }
      await wait(()=>current()===m.account&&StorylensDOM.profileReady(document,location.pathname,m.account),'Instagram has not opened the destination profile.');
      await wait(()=>[...document.querySelectorAll('a[href]')].some(a=>a.getAttribute('href').startsWith('/'+m.account+'/reel/')||a.getAttribute('href').startsWith('/'+m.account+'/p/'))||/\b0\s+posts\b/.test(document.querySelector('main')?.innerText||''),'Instagram has not loaded the existing post list for duplicate protection.');return {};
    }
    if(m.action==='start'){
      if(dialog())throw Error('An Instagram composer is already open. Keep it for review; no new upload started.');
      priorReels.clear();confirmed=false;publishedHref='';
      for(const a of document.querySelectorAll('a[href]'))if(/\/(reel|p)\//.test(a.getAttribute('href')))priorReels.add(a.getAttribute('href'));
      await click('New post');const post=await wait(()=>find('Post'),'The Instagram Post menu is unavailable.');post.click();
      const created=await wait(()=>dialog(),'Instagram did not open the upload composer.');
      ownedComposer={id:m.id,dialog:created};
      try{
        await wait(()=>StorylensDOM.videoInput(dialog()),'Instagram reel file input unavailable; use the open composer manually.');
        const select=await wait(()=>find('Select from computer',dialog()),'The reel file selection control is unavailable.');
        // Instagram may replace the initial modal shell while mounting the
        // file chooser. Bind ownership to the ready input, not that shell.
        const ready=dialog(),input=StorylensDOM.videoInput(ready);
        if(!input||!ready.contains(select)||!StorylensDOM.emptyComposer(ready))
          throw Error('The new Instagram upload window is not ready for file selection.');
        ownedComposer={id:m.id,dialog:ready,input};
        const box=select.getBoundingClientRect();
        parts.set(m.id,{name:m.name,chunks:[]});return {uploadControl:{x:box.x+box.width/2,y:box.y+box.height/2}};
      }catch(error){
        if(await closeOwnedEmpty())throw Error('Upload controls were unavailable; the empty Storylens composer was closed. [storylens-safe-retry:empty-composer]');
        throw error;
      }
    }
    if(m.action==='chunk'){
      const media=parts.get(m.id);if(!media)throw Error('Video transfer interrupted.');
      media.chunks.push(Uint8Array.from(atob(m.data),c=>c.charCodeAt(0)));return {};
    }
    if(m.action==='fileControl'){
      const d=dialog();
      if(!ownedComposer||ownedComposer.id!==m.id||
         (ownedComposer.dialog!==d&&ownedComposer.input!==StorylensDOM.videoInput(d)))
        throw Error('The Storylens upload composer changed before file selection.');
      ownedComposer.dialog=d;
      const select=find('Select from computer',d);
      if(!select||!StorylensDOM.videoInput(d))throw Error('The reel file selection control is unavailable.');
      return {uploadControl:point(select)};
    }
    if(m.action==='file'){
      const media=parts.get(m.id);if(!media)throw Error('Video transfer interrupted.');
      const input=StorylensDOM.videoInput(dialog());if(!input)throw Error('Reel upload input closed.');
      const transfer=new DataTransfer();transfer.items.add(new File(media.chunks,media.name,{type:'video/mp4'}));
      input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));parts.delete(m.id);
      await wait(()=>find('Select Crop',dialog()),'Instagram did not load the video crop.');return {};
    }
    if(m.action==='uploaded'){
      parts.delete(m.id);
      await wait(()=>find('Select Crop',dialog()),'Instagram did not load the selected video.',120000);
      await wait(()=>{const video=dialog()?.querySelector('video');return video&&video.readyState>=3&&Number.isFinite(video.duration)&&video.duration>0;},'Instagram has not finished decoding the selected video.',120000);
      await pause(1500);return {};
    }
    if(m.action==='abortOwned'){
      // Called only before the worker crosses Share. A manual draft, a replaced
      // dialog, or a submitted job must remain untouched.
      const d=dialog();
      if(sent.has(m.id)||!ownedComposer||ownedComposer.id!==m.id||d!==ownedComposer.dialog)return {closed:false};
      const close=controls('Close',d).at(-1)||controls('Close').at(-1);
      if(!close)return {closed:false};
      close.click();
      await pause(250);
      const discard=find('Discard',dialog());
      if(discard)discard.click();
      await wait(()=>!dialog(),'Storylens could not close its failed upload composer.',5000);
      parts.delete(m.id);ownedComposer=null;return {closed:true};
    }
    if(m.action==='crop'){
      await click('Select Crop',dialog());
      const portrait=await wait(()=>{const d=dialog();return d&&[...d.querySelectorAll('[role="button"],button')].filter(visible).find(e=>/^9:16/.test(name(e)));},'Portrait crop control unavailable.');portrait.click();
      await click('Next',dialog());await wait(()=>/Cover photo/.test(dialog()?.innerText||''),'Instagram did not open video editing.');
      let enabled=false;const audioStart=Date.now();
      await wait(()=>{const d=dialog(),sound=d?.querySelector('[role="switch"]');
        if(/Video has no audio/.test(d?.innerText||''))return false;
        if(StorylensDOM.checked(sound)===true)return true;
        if(sound&&!sound.disabled&&StorylensDOM.checked(sound)===false&&!enabled&&Date.now()-audioStart>1500){sound.click();enabled=true;}
        return false;
      },'Instagram has not confirmed the original audio track. Review the reel before posting.');
      await click('Next',dialog());await wait(captionBox,'Instagram caption field unavailable.');return {};
    }
    if(m.action==='details'){
      await waitAccount(m.account);const box=captionBox();if(!box)throw Error('Caption field unavailable.');box.focus();
      return {};
    }
    if(m.action==='ready'){
      await waitAccount(m.account);
      await pause(750); // Allow Instagram to commit the native input before Share is enabled.
      await wait(()=>{const d=dialog(),box=captionBox(),switches=d&&[...d.querySelectorAll('[role="switch"]')];
        return box&&norm(box.value||box.innerText)===norm(m.caption)&&StorylensDOM.composerAccount(d,m.account)&&find('Share',d)&&switches.length>=2&&switches.every(e=>StorylensDOM.checked(e)===false);
      },'The caption, account or reel settings changed. Review the open composer before publishing.');return {ready:true};
    }
    if(m.action==='share'){
      await waitAccount(m.account);assertAccount(m.account);if(sent.has(m.id))throw Error('Share was already requested. Check Instagram; do not repeat the upload.');
      const box=captionBox();if(!box||norm(box.value||box.innerText)!==norm(m.caption))throw Error('Caption changed before sharing.');
      sent.add(m.id);await click('Share',dialog());return {};
    }
    if(m.action==='result'){
      const d=dialog();
      if(/\blogin_required\b/i.test(d?.innerText||''))
        throw Error('Instagram rejected this post because @'+m.account+' needs to sign in again. Completed posts were kept; this upload will not be retried automatically.');
      if(/post (?:couldn.t|could not) be shared|your post could not be shared/i.test(d?.innerText||''))
        throw Error('Instagram rejected this post. Check its message in Chrome before retrying; completed posts were kept.');
      if(/Your reel has been shared\./i.test(d?.innerText||'')){confirmed=true;const done=find('Done',d);if(done)done.click();}
      // The transient success dialog can disappear before the next poll. A new top
      // entry followed by its exact posted caption remains the required evidence.
      if(confirmed||!d||publishedHref){
        if(!publishedHref){
          // Only a new top grid entry qualifies. Lazy-loaded older posts are not new uploads.
          const link=StorylensDOM.newTopReel(document,m.account,priorReels);
          if(link){publishedHref=link.getAttribute('href');link.click();}
        }
        if(publishedHref){
          const article=dialog()?.querySelector('article')||document.querySelector('main article');
          if(StorylensDOM.publishedCaption(article,publishedHref,m.caption))return {published:true,url:new URL(publishedHref,location.origin).href};
        }
      }
      if(/couldn.t share|something went wrong|try again later/i.test(d?.innerText||''))throw Error('Instagram could not confirm this upload. Check the tab before trying again.');
      return {published:false};
    }
    if(m.action==='verifyPublished'){
      let opened=false;
      return await wait(()=>{
        const article=dialog()?.querySelector('article')||document.querySelector('main article');
        const receipt=StorylensDOM.existingPublication(article,m.account,m.caption,m.after,m.before);
        if(receipt)return receipt;
        // Follow one exact-caption link already visible on the requested
        // profile; this recovery can never open a composer or press Share.
        if(!opened&&!dialog()){
          const link=StorylensDOM.matchingReel(document,m.account,m.caption);
          if(link){opened=true;link.click();}
        }
        return null;
      },'No matching Instagram account, caption and publication-time receipt was found. No upload was attempted.',60000);
    }
    throw Error('Unsupported Instagram operation.');
  }
  const listener=(m,sender,reply)=>{
    if(sender.id!==chrome.runtime.id||m.source!=='storylens')return;
    execute(m).then(v=>reply({ok:true,...v}),e=>reply({ok:false,error:e.message}));return true;
  };
  globalThis.__storylensInstagramAdapter={version:adapterVersion,listener};
  chrome.runtime.onMessage.addListener(listener);
})();
