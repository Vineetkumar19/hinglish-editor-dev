(()=>{
  const token=document.documentElement.dataset.token;
  let data=null,selected='general',working=false;
  const panel=document.createElement('section');panel.className='channel-profiles';panel.setAttribute('aria-label','Optional creator profiles');
  panel.innerHTML=`<div class="channel-title"><div><p class="eyebrow">OPTIONAL CREATOR PROFILES</p><h2>Your channel, your context.</h2></div><span id="channelBadge">General</span></div>
  <div class="channel-cards" role="group" aria-label="Choose a creator profile"><button type="button" data-profile="general" aria-pressed="true"><b>General</b></button><button type="button" data-profile="cricket" aria-pressed="false"><b>Cricket</b><small>Stories, match reactions & news</small></button><button type="button" data-profile="gaming" aria-pressed="false"><b>Gaming</b><small>Streams, highlights & Shorts</small></button></div>
  <div id="channelExtras" hidden><div class="channel-actions" id="channelActions"></div>
  <details id="channelPreferences"><summary>My channel preferences & references</summary><label for="channelFeedback">What should this channel prefer or avoid?</label><textarea id="channelFeedback" maxlength="6000" placeholder="My preferred pacing, sound, humour, visuals and examples"></textarea><div id="channelReferences"></div>
  <div id="cricketResearch" hidden><label for="channelTopic">Match, player or research topic</label><input id="channelTopic" maxlength="500" placeholder="Teams, tournament, match date, or player name"><label for="channelSources">Scorecard / article links (up to five)</label><textarea id="channelSources" maxlength="2000" placeholder="Public HTTPS links from ICC, BCCI, IPL, ESPNcricinfo, Cricbuzz or a national cricket board"></textarea><label for="channelMatch">Exact CricketData match ID (optional)</label><input id="channelMatch" maxlength="100"><button type="button" id="channelResearch">Save & refresh sources</button><div id="channelEvidence" aria-live="polite"></div><p class="channel-note">Current facts need internet sources. Configure BRAVE_SEARCH_API_KEY for discovery and CRICKETDATA_API_KEY for the score feed. Without keys, supplied source links still work. Match identity and source conflicts need review.</p></div>
  <button type="button" id="channelSave">Save this channel's preferences</button></details></div><p id="channelStatus" role="status" class="channel-note"></p>`;
  const dialog=document.createElement('dialog');dialog.className='profile-dialog';dialog.setAttribute('aria-label','Creator profile settings');
  const close=document.createElement('button');close.type='button';close.className='profile-close';close.setAttribute('aria-label','Close creator profile settings');close.innerHTML=window.storylensIcon('close');
  dialog.append(close,panel);document.body.append(dialog);
  const trigger=document.createElement('button');trigger.type='button';trigger.className='profile-trigger';trigger.setAttribute('aria-haspopup','dialog');trigger.setAttribute('aria-label','Creator profile settings');
  trigger.innerHTML=window.storylensIcon('profile')+'<span>Profile: <b>General</b></span>';document.querySelector('.topbar').append(trigger);
  trigger.onclick=()=>dialog.showModal();close.onclick=()=>dialog.close();dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close()}});
  const q=s=>panel.querySelector(s);
  async function api(path,body){const r=await window.storylensFetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(body?{body:JSON.stringify(body)}:{})});const d=await window.storylensResponse(r);if(!r.ok)throw Error(d.error||'Channel preferences unavailable');return d}
  function status(t){q('#channelStatus').textContent=t}
  function actionsFor(profile){
    const thumbnail={id:'channelThumbnail',label:'Create thumbnail',prompt:'Create three '+profile+' thumbnail options. Story: '};
    if(profile==='gaming')return [
      {id:'channelPublish',label:'Prepare and Post',href:'prepare-post.html?profile=gaming'},
      {id:'gamingOnly',label:'15-minute highlights',prompt:'Create a 15-minute gaming highlights compilation from my stream.'},
      thumbnail,
      {id:'gamingBundle',label:'Highlights + 5 Shorts',prompt:'Create one 15-minute gaming highlights video from my stream, then extract exactly 5 Shorts from that finished highlights video.'}
    ];
    if(profile==='cricket')return [
      thumbnail,
      {id:'channelPublish',label:'Prepare and Post',href:'prepare-post.html?profile=cricket'},
      {id:'cricketBundle',label:'Video + 5 Shorts',prompt:'Prepare my finished Cricket video for YouTube and extract exactly 5 Shorts from that video for my Cricket YouTube and Instagram accounts. Prepare editable drafts.'}
    ];
    return [];
  }
  function draw(){
    if(!data)return;const card=data.profiles[selected];
    q('#channelBadge').textContent=card.name;trigger.querySelector('b').textContent=card.name;
    panel.querySelectorAll('[data-profile]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.profile===selected)));
    q('#channelExtras').hidden=selected==='general';q('#cricketResearch').hidden=selected!=='cricket';
    q('#channelActions').replaceChildren(...actionsFor(selected).map(action=>{
      const button=document.createElement('button');button.type='button';button.id=action.id;button.textContent=action.label;
      button.onclick=()=>{dialog.close();if(action.href)location.href=action.href;else prompt(action.prompt)};return button;
    }));
    q('#channelFeedback').value=card.feedback||'';q('#channelTopic').value=card.topic||'';
    q('#channelSources').value=card.source_urls||'';q('#channelMatch').value=card.match_id||'';
    q('#channelEvidence').replaceChildren();status('');
    const refs=q('#channelReferences');refs.replaceChildren();
    (card.references||[]).forEach(url=>{const a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener';a.textContent=url.replace('https://www.youtube.com/','');refs.append(a)});
    document.body.dataset.creatorProfile=selected;document.dispatchEvent(new CustomEvent('creator-profile',{detail:selected}));
  }
  async function choose(profile){if(working||window.editorAssist?.busy?.()||window.assistantBusy){status('Finish the current edit before changing profiles.');return}try{selected=profile;draw();localStorage.setItem('hinglish.creator.profile',profile);status('')}catch(e){status(window.storylensError(e))}}
  panel.querySelectorAll('[data-profile]').forEach(b=>b.onclick=()=>choose(b.dataset.profile));
  async function save(){working=true;try{const changes={feedback:q('#channelFeedback').value,topic:q('#channelTopic').value,source_urls:q('#channelSources').value,match_id:q('#channelMatch').value};data=await api('/api/niche',{profile:selected,changes});status('Preferences saved for '+data.profiles[selected].name+'.');}finally{working=false}}
  q('#channelSave').onclick=()=>save().catch(e=>status(window.storylensError(e)));
  q('#channelResearch').onclick=async()=>{try{await save();working=true;q('#channelResearch').disabled=true;status('Fetching current sources…');const receipt=await api('/api/niche/research',{profile:selected});const evidence=q('#channelEvidence');evidence.replaceChildren();const time=document.createElement('p');time.textContent='Retrieved '+new Date(receipt.retrieved_at*1000).toLocaleString();evidence.append(time);for(const source of receipt.sources){const a=document.createElement('a');a.href=source.url;a.target='_blank';a.rel='noopener';a.textContent=(source.title||source.url)+' · '+source.kind;evidence.append(a)}for(const match of receipt.matches){const p=document.createElement('p');p.textContent=match.name+' · '+match.date+' · ID: '+match.id+(receipt.selected_match_id?' · '+JSON.stringify(match.score||[]):'');evidence.append(p)}for(const warning of receipt.warnings){const p=document.createElement('p');p.textContent=warning;evidence.append(p)}status('Research receipt saved. Check the sources before using factual claims.');}catch(e){status(window.storylensError(e))}finally{working=false;q('#channelResearch').disabled=false}};
  function prompt(text){const box=document.querySelector('#assistantPrompt');if(box){if(!document.body.classList.contains('assistant-open'))document.querySelector('.assistant-toggle:not(.chat-history-toggle)')?.click();box.value=text;box.focus();status('Attach the footage or picture in the chat, then send this request.')}else{location.href='/'}}
  window.creatorProfile={get value(){return selected},select(profile){if(data&&Object.hasOwn(data.profiles,profile)){selected=profile;localStorage.setItem('hinglish.creator.profile',profile);draw()}},save,ready:(async()=>{try{data=await api('/api/niche');const remembered=localStorage.getItem('hinglish.creator.profile');selected=Object.hasOwn(data.profiles,remembered)?remembered:'general';draw();}catch(e){status(window.storylensError(e))}})()};
})();
