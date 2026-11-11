// Shared conversational editor on both the editing and publishing pages.
(()=>{
  // publisher-navigation-start
  function publisherHref(message){
    const params=new URLSearchParams();
    if(['cricket','gaming'].includes(message.publisher_profile)){
      params.set('profile',message.publisher_profile);
      const ids=(Array.isArray(message.publish_ids)?message.publish_ids:[]).filter(id=>typeof id==='string'&&/^[a-zA-Z0-9_-]{1,80}$/.test(id));
      if(ids.length)params.set('drafts',ids.join(','));
    }
    return 'prepare-post.html'+(params.size?'?'+params.toString():'');
  }
  // publisher-navigation-end
  const token=document.documentElement.dataset.token;
  const $=s=>document.querySelector(s);
  let session=null,pending=[],busy=false,uploading=0,pollTimer=null,renderKey='',selectedJob=null,selectedTool=null,restoredResult=null;
  let recording=null,recorder=null,recordTimer=null,voiceCanceled=false;
  const active=s=>['planning','running','transcribing'].includes(s);
  async function api(path,body){const r=await window.storylensFetch(path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(body===undefined?{}:{body:JSON.stringify(body)})});const d=await window.storylensResponse(r);if(!r.ok)throw new Error(d.error||'The assistant could not complete the request');return d}
  const panel=document.createElement('aside');panel.className='assistant-panel';panel.setAttribute('aria-label','AI editing assistant');
  panel.innerHTML=`<header class="assistant-head"><span class="assistant-mark">✦</span><div><h2>Your editing assistant</h2><p>Attach. Describe. We edit.</p></div><button class="assistant-icon" id="assistantNew" aria-label="Start a new chat" title="New chat">+</button><button class="assistant-icon" id="assistantClose" aria-label="Close assistant">×</button></header>
  <div class="assistant-messages" id="assistantMessages" role="log" aria-label="Conversation" aria-live="polite"></div>
  <div class="assistant-note hidden" id="assistantWorkflowStatus" role="status" style="padding:8px 16px"></div>
  <details class="assistant-note hidden" id="assistantBackgroundTasks" style="padding:8px 16px"><summary></summary><div style="max-height:160px;overflow:auto"></div></details>
  <article class="assistant-stream hidden" id="assistantStreaming" aria-live="polite"><b>Editor · Replying</b><p id="assistantStreamingText"></p></article>
  <div class="assistant-task-progress" id="assistantTaskProgress" hidden></div>
  <div class="assistant-activity hidden" id="assistantActivity" role="status"><div class="assistant-activity-top"><span class="assistant-dot"></span><b id="assistantActivityTitle">Working</b><button id="assistantStop">Stop after this step</button></div><p id="assistantStage"></p><progress id="assistantProgress" max="100"></progress></div>
  <form class="assistant-compose" id="assistantForm"><div class="assistant-pending" id="assistantPending"></div><label class="hidden" for="assistantPrompt">Tell the assistant what to edit</label><textarea id="assistantPrompt" aria-label="Tell the assistant what to edit" rows="3" placeholder="Tell me what you want to make…"></textarea><div class="assistant-compose-row"><button type="button" id="assistantMic" class="assistant-mic" aria-label="Speak your editing request" title="Speak your editing request">${window.storylensIcon('voiceover')}</button><button type="button" id="assistantAttach">Attach</button><button class="assistant-send" id="assistantSend" type="submit">Send</button></div><p class="assistant-note" id="assistantNote" role="status"></p><p class="assistant-hint">Editing runs locally. Research can fetch internet sources. Enter to send · Shift+Enter for a new line.</p><input class="assistant-file" id="assistantFiles" type="file" multiple accept="video/*,.mkv,.mxf,.mts,.m2ts,.txt,.xml,image/png,image/jpeg,image/webp"></form>`;
  document.body.append(panel);
  const host=$('.topbar .privacy')||$('.topbar');
  const toggle=document.createElement('button');toggle.className='assistant-toggle';toggle.textContent='Ask the editor';toggle.setAttribute('aria-controls','assistantMessages');host.append(toggle);
  function open(value){document.body.classList.toggle('assistant-open',value);toggle.setAttribute('aria-expanded',String(value));try{localStorage.setItem('hinglish.assistant.open',String(value))}catch(_){}}
  toggle.onclick=()=>{open(!document.body.classList.contains('assistant-open'));if(document.body.classList.contains('assistant-open'))$('#assistantPrompt').focus()};$('#assistantClose').onclick=()=>open(false);
  try{open(localStorage.getItem('hinglish.assistant.open')!=='false')}catch(_){open(true)}
  function note(text){$('#assistantNote').textContent=text||''}
  function controls(){busy=!!session&&active(session.status);window.assistantBusy=busy;$('#assistantSend').disabled=busy||uploading>0||!!recording;$('#assistantNew').disabled=busy||uploading>0||!!recording;$('#assistantMic').disabled=uploading>0||(busy&&!recording);$('#assistantStop').disabled=!!session?.stop;
    const knowledge=session?.workflow_retrieval,sections=knowledge?.chunks||[],hint=panel.querySelector('.assistant-head p');
    hint.textContent=sections.length?(knowledge.method==='vector'?`Saved workflow recalled · ${sections.length} sections`:'Saved workflow · basic lookup'):'Attach. Describe. We edit.';
    hint.title=sections.map(s=>s.title).join('\n');
    const flow=session?.workflow_status,summary=$('#assistantWorkflowStatus');
    const currentFlow=flow?.delivery_count&&flow.current_request!==false;
    summary.classList.toggle('hidden',!currentFlow);
    summary.textContent=currentFlow?`${flow.complete?'Workflow complete':'Workflow open'} · ${flow.summary}`:'';
    const background=session?.background_instagram||[],queue=$('#assistantBackgroundTasks');
    queue.classList.toggle('hidden',!background.length);
    const posting=background.filter(j=>['running','sharing'].includes(j.status));
    queue.querySelector('summary').textContent=posting.length?`Earlier request: posting to ${[...new Set(posting.map(j=>'@'+j.account))].join(', ')}`:`Other saved Instagram tasks (${background.length})`;
    const listing=queue.querySelector('div');listing.replaceChildren();
    for(const job of background){
      const line=document.createElement('p'),label=document.createElement('span');
      const when=job.publish_at?new Date(job.publish_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'';
      const state=job.status==='published'?'posted from an earlier schedule':['running','sharing'].includes(job.status)?'posting now':when?'scheduled for '+when:'waiting to post';
      label.textContent='@'+job.account+' · '+state+'. ';line.append(label);
      if(/^[a-f0-9]{16}$/.test(job.session)){const link=document.createElement('a');link.href='/?chat='+encodeURIComponent(job.session);link.textContent='Source chat';line.append(link)}
      listing.append(line);
    }
  }
  function chips(){const box=$('#assistantPending');box.replaceChildren();pending.forEach(a=>{const chip=document.createElement('div');chip.className='assistant-attachment';const name=document.createElement('span');name.textContent=a.name;const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove '+a.name);remove.onclick=()=>{pending=pending.filter(p=>p.id!==a.id);chips()};chip.append(name,remove);box.append(chip)});controls()}
  async function ensure(){if(session)return session;session=await api('/api/assistant/session',{});try{localStorage.setItem('hinglish.assistant.session',session.id);const url=new URL(location.href);url.searchParams.set('chat',session.id);history.replaceState(null,'',url)}catch(_){};document.dispatchEvent(new CustomEvent('storylens-chat-selected',{detail:session.id}));return session}
  function upload(file,kind='file'){return new Promise(async(resolve,reject)=>{try{await ensure();const xhr=new XMLHttpRequest();xhr.open('POST',`/api/assistant/upload?session=${encodeURIComponent(session.id)}&name=${encodeURIComponent(file.name)}&kind=${kind}`);xhr.setRequestHeader('X-Hinglish-Token',token);xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.upload.onprogress=e=>{if(e.lengthComputable)note(`Adding ${file.name} · ${Math.round(e.loaded/e.total*100)}%`)};xhr.onload=()=>window.storylensXHR(xhr).then(resolve,reject);xhr.onerror=()=>reject(new Error('Attachment transfer stopped. Try again.'));xhr.send(file)}catch(e){reject(e)}})}
  async function addFiles(files){uploading++;controls();try{for(const f of [...files]){pending.push(await upload(f));chips()}note('Attachments are ready. Tell me what to do with them.')}catch(e){note(window.storylensError(e))}finally{uploading--;controls()}}
  $('#assistantAttach').onclick=()=>$('#assistantFiles').click();$('#assistantFiles').onchange=e=>{addFiles(e.target.files);e.target.value=''};
  panel.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();panel.classList.add('dragging')}});panel.addEventListener('dragleave',()=>panel.classList.remove('dragging'));panel.addEventListener('drop',e=>{e.preventDefault();panel.classList.remove('dragging');if(e.dataTransfer.files.length)addFiles(e.dataTransfer.files)});
  async function send(text,voice){await ensure();if(busy||uploading)return;note('');session=await api('/api/assistant/message',{session:session.id,message:text,profile:window.creatorProfile?.value||'general',attachments:pending.map(a=>a.id),...(document.querySelector('#motionEngine')?{motion_engine:document.querySelector('#motionEngine').value}:{}),...(voice?{voice}: {})});pending=[];chips();$('#assistantPrompt').value='';render();schedule(500)}
  $('#assistantForm').onsubmit=async e=>{e.preventDefault();const text=$('#assistantPrompt').value.trim();if(!text){note('Tell me what you want to edit.');return}try{await send(text)}catch(error){note(window.storylensError(error))}};
  $('#assistantPrompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#assistantForm').requestSubmit()}};
  $('#assistantNew').onclick=async()=>{if(busy)return;try{session=null;pending=[];selectedJob=null;selectedTool=null;restoredResult=null;window.editorAssist?.reset();renderKey='';await ensure();chips();render();note('New conversation. Completed videos stay in your output folder.')}catch(e){note(window.storylensError(e))}};
  $('#assistantStop').onclick=async()=>{try{session=await api('/api/assistant/stop',{session:session.id});render()}catch(e){note(window.storylensError(e))}};
  window.storylensChat={
    get id(){return session?.id},
    async open(id){
      if(uploading||recording){note('Finish adding files or recording before switching chats.');return}
      const saved=await api('/api/assistant/session?id='+encodeURIComponent(id));
      clearTimeout(pollTimer);session=saved;pending=[];selectedJob=null;selectedTool=null;restoredResult=null;renderKey='';
      await window.creatorProfile?.ready;window.creatorProfile?.select?.(saved.profile||'general');
      localStorage.setItem('hinglish.assistant.session',id);const url=new URL(location.href);url.searchParams.set('chat',id);history.replaceState(null,'',url);
      open(true);window.editorAssist?.reset();chips();render();schedule();note('Conversation reopened. Using only this chat’s last 5 exchanges and saved task state.');
      document.dispatchEvent(new CustomEvent('storylens-chat-selected',{detail:id}));
    },
    async new(){await $('#assistantNew').onclick();if(session){const url=new URL(location.href);url.searchParams.set('chat',session.id);history.replaceState(null,'',url);document.dispatchEvent(new CustomEvent('storylens-chat-selected',{detail:session.id}))}}
  };
  const historyScript=document.createElement('script');historyScript.src='assistant-history.js';document.body.append(historyScript);
  const scheduledScript=document.createElement('script');scheduledScript.src='scheduled-posts.js?v=20261108-voice-settings';document.body.append(scheduledScript);
  function button(label,fn){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=async()=>{try{await fn()}catch(e){note(window.storylensError(e))}};return b}
  function publishReview(review){
    const box=document.createElement('section');box.className='assistant-publish-review';
    const live=session.publishing_review?.id===review.id?session.publishing_review:null;
    const current=live||(session.publishing_review_history||[]).find(r=>r.id===review.id)||null;
    if(current)review=current;
    const resuming=current?.state==='needs_review';
    const editable=!!live&&!review.automatic&&(current.state==='review'||(resuming&&current.retryable))&&!busy,fields={},reelFields={};
    if(review.automatic||!editable){
      for(const item of review.rows||[]){const card=document.createElement('article'),title=document.createElement('b'),status=document.createElement('p');title.textContent='YouTube · '+item.metadata.title;status.textContent=item.private_verified?'Uploaded privately and verified.':item.publication_verified?'Published and verified.':item.schedule_verified?'Scheduled for '+new Date(item.publish_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':item.url?(item.private_only?'Uploaded privately; final verification is pending.':item.immediate?'Uploaded; public visibility is being verified.':'Uploaded privately; schedule not yet verified.'):'Upload not completed.';card.append(title,status);box.append(card)}
      for(const item of review.instagram_rows||[]){
        const card=document.createElement('article'),title=document.createElement('b'),status=document.createElement('p');
        title.textContent='Instagram @'+item.account+' · '+item.metadata.title;
        const states={draft:'Ready to upload.',date_change_pending:'Date change pending. The existing job is still queued for '+new Date(item.actual_publish_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST.',queued:item.immediate?'Waiting to upload.':'Scheduled locally for '+new Date(item.publish_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST. Keep Storylens and Chrome running.',running:'Uploading…',sharing:'Instagram is processing the post…',published:item.previously_published?'Posted earlier; not uploaded again in this request.':'Posted successfully in this request.',cancelled:'Cancelled.'};
        status.textContent=states[item.status]||(item.submission_started?'Publication not verified. Check Instagram before retrying.':item.user_message||'Not posted. The saved upload needs attention.');card.append(title,status);
        if(item.url&&/^https:\/\/www\.instagram\.com\/(?:[\w.]+\/)?(?:reel|p)\/[\w-]+\/$/.test(item.url)){const a=document.createElement('a');a.href=item.url;a.target='_blank';a.rel='noopener';a.textContent='View post';card.append(a)}
        if(item.message&&['needs_review','blocked'].includes(item.status)){const issue=window.storylensProblem(item.message);status.textContent=(item.submission_started?'Publication could not be verified. ':'')+issue.message;const d=window.storylensDetails({...issue,details:issue.details||item.message});if(d)card.append(d)}
        box.append(card);
      }
      return box;
    }
    if(review.youtube_check_only){const check=document.createElement('p');check.textContent='YouTube check only: '+(review.youtube_checks?.length||0)+' drafts validated. No YouTube upload or schedule will be sent.';box.append(check)}
    if(current){const summary=document.createElement('p');summary.textContent=(review.ids.length?(current.uploaded_count||0)+' of '+review.ids.length+' YouTube videos uploaded · '+(current.scheduled_count||0)+' schedules verified. ':'')+(review.instagram_rows?.length?(current.instagram_queued_count||0)+' Instagram slots queued · '+(current.instagram_published_count||0)+' published. ':'')+'Completed uploads will be reused.';box.append(summary)}
    for(const item of review.rows){
      const card=document.createElement('article'),head=document.createElement('h4'),source=document.createElement('p');
      head.textContent=item.channel+' · '+item.kind+(item.private_only?' · Private':item.immediate?' · Now':review.schedule?' · '+new Date(item.publish_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':' · Private');source.textContent=item.source+' · '+Math.round(item.duration)+' seconds';card.append(head,source);
      if(item.url){const a=document.createElement('a');if(/^https:\/\/www\.youtube\.com\/watch\?v=[\w-]{11}$/.test(item.url)){a.href=item.url;a.target='_blank';a.rel='noopener';a.textContent='Already uploaded · view video';card.append(a)}}
      const controls={};
      for(const [key,label] of [['title','Title'],['description','Description'],['tags','Search tags']]){
        const wrap=document.createElement('label'),input=document.createElement(key==='description'?'textarea':'input');
        wrap.textContent=label;input.setAttribute('aria-label',item.channel+' '+item.kind+' '+label.toLowerCase());
        input.value=key==='tags'?(item.metadata.tags||[]).join(', '):item.metadata[key]||'';
        input.maxLength=key==='title'?100:key==='description'?5000:450;input.disabled=!editable||!!item.url;
        if(key==='description')input.rows=6;wrap.append(input);card.append(wrap);controls[key]=input;
      }
      fields[item.id]=controls;box.append(card);
    }
    for(const item of review.instagram_rows||[]){
      const card=document.createElement('article'),head=document.createElement('h4'),status=document.createElement('p'),caption=document.createElement('textarea');
      head.textContent='Instagram @'+item.account+' · '+(item.immediate?'Now':new Date(item.publish_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST');
      status.textContent=item.metadata.title+' · '+item.status+(item.message?' · '+item.message:'');
      caption.value=item.caption;caption.maxLength=2200;caption.rows=5;caption.setAttribute('aria-label','Instagram @'+item.account+' caption '+item.id);caption.disabled=!editable||!!item.browser_job_id;
      card.append(head,status,caption);if(item.url&&/^https:\/\/www\.instagram\.com\/(?:[\w.]+\/)?(?:reel|p)\/[\w-]+\/$/.test(item.url)){const link=document.createElement('a');link.href=item.url;link.target='_blank';link.rel='noopener';link.textContent='View published Reel';card.append(link)}
      reelFields[item.id]=caption;box.append(card);
    }
    if(review.instagram_rows?.length){const info=document.createElement('p');info.textContent='Instagram posts through your local Chrome queue. If the laptop is asleep or offline at release time, unposted Reels post automatically when Storylens, Chrome and internet reconnect.';box.append(info)}
    if(!editable){const status=document.createElement('p');status.textContent=current?.state==='queued'?'Instagram tasks saved locally; check the individual publication receipts after their release times.':current?.state==='complete'?(review.schedule?'YouTube releases verified. Instagram status is shown separately above.':'Uploads completed.'):current?.state==='uploading'?'Uploading this batch…':current?.state==='scheduling'?'Uploads complete; verifying Studio release dates…':resuming?'An upload needs verification before resuming. Completed videos will not be uploaded again.':'This review is no longer active.';box.append(status);return box}
    const choices=(label,options)=>{const wrap=document.createElement('label'),select=document.createElement('select');wrap.textContent=label;for(const [value,text] of options){const o=document.createElement('option');o.value=value;o.textContent=text;select.append(o)}wrap.append(select);box.append(wrap);return select};
    // Saved owner choices are data, not questions. Do not create dropdowns
    // and rely on CSS to hide them: label styles can override hidden.
    const savedDeclarations=review.declaration_defaults_saved&&typeof review.made_for_kids==='boolean'&&typeof review.synthetic_media==='boolean';
    let audience,synthetic;
    if(savedDeclarations||!review.ids.length){
      audience={value:String(savedDeclarations?review.made_for_kids:false)};
      synthetic={value:String(savedDeclarations?review.synthetic_media:false)};
    }else{
      audience=choices('Audience · applies to these videos',[['','Choose the audience'],['false','Not made for kids'],['true','Made for kids']]);
      synthetic=choices('Realistic altered or synthetic media',[['','Choose the disclosure'],['false','No'],['true','Yes']]);
      if(typeof review.made_for_kids==='boolean')audience.value=String(review.made_for_kids);
      if(typeof review.synthetic_media==='boolean')synthetic.value=String(review.synthetic_media);
    }
    const upload=button(review.distribution?'Confirm these platform schedules':resuming?(review.schedule?'Resume remaining uploads and schedule':'Resume remaining private uploads'):(review.schedule?'Upload and schedule these Shorts':'Upload these privately'),async()=>{
      if(!audience.value||!synthetic.value)throw Error('Choose the audience and synthetic-media disclosure first.');
      note('');
      const metadata={};for(const [id,f] of Object.entries(fields))metadata[id]={title:f.title.value,description:f.description.value,tags:f.tags.value.split(',').map(t=>t.trim()).filter(Boolean)};
      const instagram_captions={};for(const [id,input] of Object.entries(reelFields))instagram_captions[id]=input.value;
      upload.disabled=true;
      try{session=await api('/api/assistant/publish',{session:session.id,review:review.id,made_for_kids:audience.value==='true',synthetic_media:synthetic.value==='true',metadata,instagram_captions});render();schedule(500)}catch(error){upload.disabled=false;throw error}
    });box.append(upload);return box;
  }
  function messageText(m){
    const text=String(m.text||'');
    if(m.role==='assistant'&&m.plan?.length&&!m.result&&/\b(?:complete(?:d)?|finished|done)\b/i.test(text))return 'Starting the requested steps.';
    return text;
  }
  function render(){if(!session)return;controls();const messages=$('#assistantMessages');const key=JSON.stringify([session.id,session.messages,session.publishing_review?.id,session.publishing_review?.state,session.publishing_review?.instagram_rows?.map(r=>[r.id,r.status,r.url,r.message]),session.publishing_review?.instagram_queued_count,session.publishing_review?.instagram_published_count]);if(key!==renderKey){const previousScrollTop=messages.scrollTop;const nearBottom=messages.scrollHeight-previousScrollTop-messages.clientHeight<100;messages.replaceChildren();if(!session.messages.length){const welcome=document.createElement('div');welcome.className='assistant-welcome';welcome.innerHTML='<p class="eyebrow">LESS SETUP. MORE CREATING.</p><h3>What are we<br>making today?</h3><p>Drop your clips here and describe the result. I’ll choose the tools and start the edit.</p>';const suggestions=document.createElement('div');suggestions.className='assistant-suggestions';['Clean these clips and combine them into one video','Add captions using Typography 4','Make 10 Shorts from my long video','What can you help me edit?'].forEach(t=>suggestions.append(button(t,()=>{$('#assistantPrompt').value=t;$('#assistantPrompt').focus()})));welcome.append(suggestions);messages.append(welcome)}let videoIndex=0;const lastVideoMessage=session.messages.filter(m=>m.videos?.length).at(-1)?.id;session.messages.forEach(m=>{const row=document.createElement('article');row.className='assistant-message '+m.role+(m.error?' error':'');const who=document.createElement('div');who.className='who';who.textContent=m.role==='user'?'You'+(m.voice?' · voice':''):'Editor';const text=document.createElement('p');text.textContent=messageText(m);row.append(who,text);if(m.question&&m.text==='B-roll format?'){const formats=document.createElement('div');formats.className='assistant-results';for(const label of ['Vertical','Horizontal'])formats.append(button(label,()=>send('Use '+label.toLowerCase()+' B-roll, up to six video options per keyword.').catch(error=>note(window.storylensError(error)))));row.append(formats)}if(m.error_details&&m.error_details!==m.text){const details=document.createElement('details'),label=document.createElement('summary'),raw=document.createElement('pre');label.textContent='Technical details';raw.textContent=m.error_details;details.append(label,raw);row.append(details)}(m.attachments||[]).forEach(a=>{const chip=document.createElement('div');chip.className='assistant-attachment';chip.textContent=a.name;row.append(chip)});if(m.publishing_review)row.append(publishReview(m.publishing_review));for(const result of m.publish_results||[]){const a=document.createElement('a');if(/^https:\/\/www\.youtube\.com\/watch\?v=[\w-]{11}$/.test(result.url)){a.href=result.url;a.target='_blank';a.rel='noopener';a.textContent=result.channel+' · '+result.kind+' · '+result.title;const links=document.createElement('div');links.className='assistant-results';links.append(a);row.append(links)}}if(m.plan){const list=document.createElement('div');list.className='assistant-plan';m.plan.forEach(s=>{const tag=document.createElement('span');tag.textContent=s;list.append(tag)});if(m.combine){const tag=document.createElement('span');tag.textContent='Combine in order';list.append(tag)}row.append(list)}if(m.result){for(const url of (m.result.image_urls||[]).slice(0,4)){if(!/^\/thumbnail-output\/[a-zA-Z0-9/_-]+\.png$/.test(url))continue;const image=document.createElement('img');image.src=url;image.alt='Generated image option';image.loading='lazy';image.className='assistant-image-result';row.append(image)}const actions=document.createElement('div');actions.className='assistant-results completed-result-actions';actions.setAttribute('role','group');actions.setAttribute('aria-label','Finished result actions');actions.append(button('View Result',()=>api('/api/open',{path:m.result.page})));window.storylensEditors?.render(actions,{...m.result,videos:m.videos||[]});actions.append(button('Open Folder',()=>api('/api/open',{path:m.result.folder})));row.append(actions)}if(m.browser_setup){const a=document.createElement('a');a.href='chrome.html';a.textContent='Open Chrome connection';row.append(a)}if(m.browser_url&&/^https:\/\/www\.instagram\.com\/[\w./-]+$/.test(m.browser_url)){const a=document.createElement('a');a.href=m.browser_url;a.target='_blank';a.rel='noopener';a.textContent='View published reel';row.append(a)}if(m.navigate){const actions=document.createElement('div');actions.className='assistant-results';const a=document.createElement('a');a.href=publisherHref(m);a.textContent='Open Prepare and Post';actions.append(a);row.append(actions)}(m.videos||[]).forEach((p,i)=>{const current=videoIndex++;if(i<3&&m.id===lastVideoMessage){const video=document.createElement('video');video.controls=true;video.preload='metadata';video.setAttribute('playsinline','');video.src=`/api/assistant/media?session=${encodeURIComponent(session.id)}&index=${current}&token=${encodeURIComponent(token)}`;row.append(video)}else{const actions=document.createElement('div');actions.className='assistant-results';actions.append(button('Open video '+(i+1),()=>api('/api/open',{path:p})));row.append(actions)}});messages.append(row)});renderKey=key;messages.scrollTop=nearBottom?messages.scrollHeight:previousScrollTop}
    const retry=session.pipeline?.phase==='waiting_retry'&&!session.stop,waiting=session.pipeline?.phase==='waiting_executor'&&!session.stop;const instagramBusy=session.pipeline?.phase==='waiting_instagram'&&!session.stop&&(session.publishing_review?.instagram_rows||[]).some(r=>['running','sharing'].includes(r.status)||(r.status==='queued'&&r.immediate));
    const activity=$('#assistantActivity');activity.classList.toggle('hidden',!active(session.status)&&!retry&&!waiting&&!instagramBusy);$('#assistantActivityTitle').textContent=instagramBusy?'Posting to Instagram':waiting?'Waiting for Chrome':retry?'Automatic recovery queued':session.status==='planning'?'Understanding your request':session.status==='transcribing'?'Listening locally':`Step ${session.step_index+1} of ${session.steps.length||1}`;$('#assistantStage').textContent=waiting?'Your request is saved. It will continue when Storylens Local Publisher reconnects.':retry?`Saved progress will resume in ${Math.max(0,Math.ceil((session.pipeline.next_retry||0)-Date.now()/1000))} seconds. Finished work will be reused.`:session.stop?session.stage:(session.job&&session.job.status!=='complete'?session.job.stage:session.stage);$('#assistantStop').textContent=retry||waiting?'Pause recovery':'Stop after this step';const prog=$('#assistantProgress');if(session.job&&session.job.status==='running'&&session.job.mode!=='gaming')prog.value=session.job.progress;else prog.removeAttribute('value');
    const taskView=window.StorylensAssistantProgress?.render($('#assistantTaskProgress'),session);
    if(taskView?.total){$('#assistantProgress').value=taskView.percent;$('#assistantActivityTitle').textContent=taskView.finished+'/'+taskView.total+' steps finished';}
    const liveReply=session.stream_reply,showReply=active(session.status)&&liveReply?.message_id===session.active_request_message_id;
    $('#assistantStreaming').classList.toggle('hidden',!showReply);$('#assistantStreamingText').textContent=showReply?liveReply.text:'';
    const editingPastedCaptions=typeof mode!=='undefined'&&mode==='captions'&&(!!document.querySelector('#autoCaptionPanel')||document.querySelector('#captionFromText')?.getAttribute('aria-pressed')==='true');
    if(editingPastedCaptions){selectedTool=session.selected;selectedJob=session.job_id;restoredResult=session.last_result?.page||null;}
    if(!editingPastedCaptions&&session.selected&&!['publish','instagram'].includes(session.selected)&&window.editorAssist){if(selectedTool!==session.selected){selectedTool=session.selected;window.editorAssist.select(session.payload||{mode:session.selected})}if(selectedJob!==session.job_id&&session.job_id){selectedJob=session.job_id;window.editorAssist.select(session.payload||{mode:session.selected});window.editorAssist.watch(session.job)}}
    if(!editingPastedCaptions&&!active(session.status)&&session.last_result&&window.editorAssist&&restoredResult!==session.last_result.page){restoredResult=session.last_result.page;window.editorAssist.done(session.last_result);}
    if(session.selected==='publish'&&!session.publishing_review){const nav=(session.messages||[]).filter(m=>m.navigate==='publisher').at(-1);if(nav&&sessionStorage.getItem('hinglish.assistant.navigated')!==nav.id){try{sessionStorage.setItem('hinglish.assistant.navigated',nav.id);sessionStorage.setItem('hinglish.publish.command',nav.command||'')}catch(_){}if(nav.publisher_profile||!location.pathname.endsWith('/prepare-post.html'))location.href=publisherHref(nav)}}
  }
  function schedule(ms=1200){clearTimeout(pollTimer);pollTimer=setTimeout(refresh,ms)}
  const connectionWarning='Connection interrupted. Keep the editor open; I’ll try again.';
  async function refresh(){if(!session)return;try{session=await api('/api/assistant/session?id='+encodeURIComponent(session.id));if($('#assistantNote').textContent===connectionWarning)note('');render();schedule(active(session.status)?600:5000)}catch(e){note(connectionWarning);schedule(5000)}}
  function updateMicButton(isRecording){
    const button=$('#assistantMic');
    const label=isRecording?'Finish speaking':'Speak your editing request';
    button.innerHTML=window.storylensIcon(isRecording?'stop':'voiceover');
    button.setAttribute('aria-label',label);
    button.title=label;
    button.classList.toggle('recording',isRecording);
  }
  async function mic(){if(recording){recorder.stop();return}if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){note('This browser cannot record audio. Open the editor in Chrome or Edge, or type your request.');return}try{recording=await navigator.mediaDevices.getUserMedia({audio:true});voiceCanceled=false;const chunks=[];const type=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(t=>MediaRecorder.isTypeSupported(t));recorder=new MediaRecorder(recording,type?{mimeType:type}:{});recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};recorder.onstop=async()=>{clearTimeout(recordTimer);recording.getTracks().forEach(t=>t.stop());recording=null;updateMicButton(false);controls();if(voiceCanceled)return;uploading++;controls();try{note('Sending your voice to the local speech model…');const file=new File([new Blob(chunks,{type:recorder.mimeType})],'voice-request.'+(recorder.mimeType.includes('mp4')?'m4a':'webm'),{type:recorder.mimeType});const a=await upload(file,'voice');uploading--;await send('',a.id)}catch(e){if(uploading)uploading--;note(window.storylensError(e))}finally{controls()}};recorder.start();updateMicButton(true);note('Listening. Select the stop button to run your request. Escape cancels.');recordTimer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop()},119000);controls()}catch(e){recording?.getTracks().forEach(t=>t.stop());recording=null;updateMicButton(false);controls();note('Microphone access was not available. Allow it in your browser, or type your request.')}}
  $('#assistantMic').onclick=mic;document.addEventListener('keydown',e=>{if(e.key==='Escape'&&recording){voiceCanceled=true;recorder.stop();note('Voice recording canceled.')}});
  (async()=>{try{let id;const requestedChat=new URL(location.href).searchParams.get('chat');try{id=/^[a-f0-9]{16}$/.test(requestedChat||'')?requestedChat:localStorage.getItem('hinglish.assistant.session')}catch(_){}if(id){try{session=await api('/api/assistant/session?id='+encodeURIComponent(id))}catch(e){if(!/unavailable/i.test(e.message))throw e}}await window.creatorProfile?.ready;await ensure();render();schedule()}catch(e){note(window.storylensError(e))}})();
})();
