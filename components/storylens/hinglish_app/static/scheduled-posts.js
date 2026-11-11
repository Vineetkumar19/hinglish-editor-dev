// One list of real saved deliveries. Opening it never changes a schedule.
// Read-only compatibility for a running service that predates Prepare/Post.
// Correct platform ownership without touching queues or restarting its worker.
function storylensScheduledRows(posts,jobs){
  const byId=new Map(jobs.map(job=>[job.id,job]));
  const rows=posts.filter(post=>post.status!=='cancelled'&&!byId.get(post.id.split(':')[1])?.scheduled_panel_deleted_at&&!(post.platform==='youtube'&&byId.get(post.id.split(':')[1])?.platform==='instagram'));
  const represented=new Set(rows.map(post=>post.id));
  for(const job of byId.values()){
    if(job.scheduled_panel_deleted_at)continue;
    if(job.platform!=='instagram'||!job.prepare_post_id||!job.authorized_at)continue;
    if(!['ready','uploading','processing','needs_review','blocked','failed'].includes(job.status))continue;
    const remote=job.remote||{},id='instagram:'+job.id;
    if(represented.has(id)||represented.has('instagram:'+remote.browser_job_id))continue;
    // Once handed to Chrome, its task is the single source of delivery state.
    if(remote.browser_job_id)continue;
    const caption=job.metadata?.instagram_caption||'',failed=['needs_review','blocked','failed'].includes(job.status);
    rows.push({id,platform:'instagram',profile:job.profile,account:job.account_id,status:job.status,
      bucket:failed?'failed':'scheduled',publish_at:new Date(job.due*1000).toISOString(),
      title:caption.replace(/(?<!\w)#[A-Za-z][A-Za-z0-9_]*/g,'').trim(),description:'',
      hashtags:(caption.match(/#[A-Za-z][A-Za-z0-9_]*/g)||[]).join(' '),session:'',can_edit:false,
      message:failed?job.error||'Needs review.':'Queued locally; uploads automatically at release time while Storylens and Chrome are running.',
      revision:JSON.stringify([job.status,job.due,caption]),operation:{},url:remote.url||'',prepare_post_id:job.prepare_post_id});
  }
  return rows.sort((a,b)=>(a.profile||'').localeCompare(b.profile||'')||a.platform.localeCompare(b.platform)||Date.parse(a.publish_at)-Date.parse(b.publish_at));
}
function scheduledActionEnabled(post,action,pending=false){return !pending&&(action==='delete'?post.bucket==='failed'&&post.can_delete===true:action==='cancel'?post.can_cancel===true:post.can_edit===true);}
if(typeof module!=='undefined')module.exports={storylensScheduledRows,scheduledActionEnabled};
if(typeof document!=='undefined')(()=>{
  const token=document.documentElement.dataset.token;
  const style=document.createElement('link');style.rel='stylesheet';style.href='scheduled-posts.css?v=20261029-cancel-layout';document.head.append(style);
  const host=document.querySelector('[data-scheduled-host]')||document.querySelector('.topbar .privacy')||document.querySelector('.topbar');if(!host)return;
  const button=document.createElement('button');button.className='scheduled-toggle';button.textContent='Scheduled posts';host.append(button);
  const dialog=document.createElement('dialog');dialog.className='scheduled-dialog';
  dialog.innerHTML='<header><div><p class="eyebrow">YOUR PUBLISHING QUEUE</p><h2>Scheduled posts</h2></div><button type="button" aria-label="Close scheduled posts">×</button></header><p class="scheduled-note" role="status"></p><nav class="scheduled-channels" aria-label="Creator channels"></nav><nav class="scheduled-platforms" aria-label="Platforms"></nav><div class="scheduled-layout"><section class="scheduled-list" aria-label="Scheduled videos"></section><section class="scheduled-detail" aria-label="Post details"><p>Select a post to review its text and release time.</p></section></div>';
  document.body.append(dialog);dialog.querySelector('header button').onclick=()=>dialog.close();
  dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});
  const list=dialog.querySelector('.scheduled-list'),detail=dialog.querySelector('.scheduled-detail'),notice=dialog.querySelector('.scheduled-note');
  const channels=dialog.querySelector('.scheduled-channels'),channelName=profile=>({cricket:'Cricket',gaming:'Gaming'})[profile]||'Other channels';
  const platforms=dialog.querySelector('.scheduled-platforms');
  let posts=[],selected='',renderedRevision='',dirty=false,pending=false,timer,profileFilter=new URLSearchParams(location.search).get('profile')==='gaming'?'gaming':'cricket',platformFilter='instagram';
  let channelSignature='',platformSignature='',listSignature='';
  let publisherJobs=[],publisherJobsReadAt=0;
  let pendingCancellation='';
  let pendingDeletion='';
  const channelPosts=()=>posts.filter(p=>(['cricket','gaming'].includes(p.profile)?p.profile:'other')===profileFilter);
  const filtered=()=>channelPosts().filter(p=>platformFilter==='failed'?p.bucket==='failed':p.bucket!=='failed'&&p.platform===platformFilter);
  const preferred=items=>items.find(p=>p.can_edit&&p.publish_at&&new Date(p.publish_at)>new Date())||items[0];
  const time=value=>value?new Date(value).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'})+' IST':'Now';
  const stateLabel=post=>post.operation?.status==='working'?'Applying your change…':post.bucket==='failed'&&['scheduled','ready'].includes(post.status)?'Release not verified':({queued:'Queued locally',scheduled:'Saved YouTube schedule',needs_review:'Needs attention',blocked:'Blocked',running:'Posting in progress',sharing:'Waiting for publication verification',ready:'Waiting to upload',uploading:'Uploading',processing:'Processing'})[post.status]||post.status;
  async function api(path,body){
    const response=await window.storylensFetch(path,{method:body?'POST':'GET',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
    const data=await window.storylensResponse(response);if(!response.ok)throw Error(data.error||'Could not read the scheduled posts.');return data;
  }
  function image(post){const wrap=document.createElement('span'),img=document.createElement('img');wrap.className='scheduled-preview';img.alt='Video preview';img.loading='lazy';img.src='/api/scheduled/thumbnail?id='+encodeURIComponent(post.id)+'&token='+encodeURIComponent(token);img.onerror=()=>{wrap.textContent='Preview unavailable'};wrap.append(img);return wrap}
  function renderChannels(){
    const signature=profileFilter+'|'+posts.map(p=>p.profile).join(',');if(signature===channelSignature)return;channelSignature=signature;
    channels.replaceChildren();
    for(const profile of ['cricket','gaming',...(posts.some(p=>!['cricket','gaming'].includes(p.profile))?['other']:[])]){
      const control=document.createElement('button');control.type='button';control.textContent=channelName(profile)+' · '+posts.filter(p=>(['cricket','gaming'].includes(p.profile)?p.profile:'other')===profile).length;control.setAttribute('aria-pressed',String(profile===profileFilter));
      control.onclick=()=>{if(dirty){notice.textContent='Save your changes before changing channels, or close and reopen to discard them.';return}profileFilter=profile;selected='';renderChannels();renderPlatforms();selectDefault();renderList()};channels.append(control);
    }
  }
  function selectDefault(){const post=preferred(filtered());if(post){selected=post.id;renderDetail(post)}else{selected='';detail.textContent=platformFilter==='failed'?'No failed attempts for '+channelName(profileFilter)+'.':'No pending '+(platformFilter==='instagram'?'Instagram':'YouTube')+' posts for '+channelName(profileFilter)+'.'}}
  function renderPlatforms(){
    const signature=profileFilter+'|'+platformFilter+'|'+channelPosts().map(p=>p.platform+':'+p.bucket).join(',');if(signature===platformSignature)return;platformSignature=signature;
    platforms.replaceChildren();
    for(const platform of ['instagram','youtube','failed']){
      const control=document.createElement('button');control.type='button';control.dataset.platform=platform;control.textContent=({instagram:'Instagram',youtube:'YouTube',failed:'Failed attempts'})[platform]+' · '+channelPosts().filter(p=>platform==='failed'?p.bucket==='failed':p.bucket!=='failed'&&p.platform===platform).length;control.setAttribute('aria-pressed',String(platform===platformFilter));
      control.onclick=()=>{if(dirty){notice.textContent='Save your changes before changing platforms, or close and reopen to discard them.';return}platformFilter=platform;selected='';renderPlatforms();selectDefault();renderList()};platforms.append(control);
    }
  }
  function renderList(){
    const visible=filtered();
    const signature=profileFilter+'|'+platformFilter+'|'+selected+'|'+visible.map(p=>p.id+':'+p.revision).join(',');if(signature===listSignature)return;listSignature=signature;
    list.replaceChildren();
    if(!visible.length){const empty=document.createElement('p');empty.textContent=(platformFilter==='failed'?'No failed attempts':'No scheduled posts')+' for '+channelName(profileFilter)+'.';list.append(empty);return}
    let previousPlatform='';
    for(const post of visible){
      if(post.platform!==previousPlatform){const heading=document.createElement('h3');heading.className='scheduled-platform';heading.textContent=post.platform==='instagram'?'Instagram':'YouTube';list.append(heading);previousPlatform=post.platform}
      const card=document.createElement('button');card.type='button';card.className='scheduled-card'+(post.id===selected?' selected':'');
      const info=document.createElement('span'),platform=document.createElement('small'),title=document.createElement('b'),date=document.createElement('span'),account=document.createElement('span');
      platform.textContent=post.platform==='youtube'?'YouTube':'Instagram';title.textContent=post.title;date.textContent=time(post.publish_at)+' · '+stateLabel(post);account.textContent=(post.platform==='instagram'?'@':'')+post.account;
      info.append(platform,title,account,date);card.append(image(post),info);
      card.onclick=()=>{if(dirty){notice.textContent='Save your changes before selecting another post, or close and reopen this panel to discard them.';return}selected=post.id;renderList();renderDetail(post)};
      list.append(card);
    }
  }
  function renderDetail(post){
    detail.replaceChildren();dirty=false;renderedRevision=post.revision;
    const title=document.createElement('h3');title.textContent=post.platform==='youtube'?'YouTube post':'Instagram Reel';
    const identity=document.createElement('p');identity.textContent=(post.platform==='instagram'?'@':'')+post.account+' · '+time(post.publish_at);
    const status=document.createElement('p');status.className='scheduled-state';
    status.textContent=post.operation?.status==='working'?'Applying your change…':post.bucket==='failed'?stateLabel(post)+(post.message?' · '+post.message:''):post.status==='scheduled'?'Saved YouTube schedule. Its current platform state is checked before any change.':post.status==='queued'?'Queued locally. If the laptop is offline at release time, posting resumes after Storylens and Chrome reconnect.':stateLabel(post)+(post.message?' · '+post.message:'');
    if(post.bucket==='failed'&&post.message){const issue=window.storylensProblem({message:post.message,code:post.operation?.error_code,details:post.operation?.error_details});status.textContent=stateLabel(post)+' · '+issue.message;detail.append(title,identity,status);const technical=window.storylensDetails(issue);if(technical)detail.append(technical)}else detail.append(title,identity,status);
    const fields={};
    for(const [key,label,multiline] of [['title','Title',false],['description','Description',true],['hashtags','Hashtags',true]]){
      if(post.platform==='instagram'&&key==='description')continue;
      const wrap=document.createElement('label'),input=document.createElement(multiline?'textarea':'input');wrap.textContent=label;input.setAttribute('aria-label',label);
      input.value=post[key]||'';input.disabled=!post.can_edit||pending;
      if(key==='description'){input.value=input.value.replace(/(?<!\w)#[A-Za-z][A-Za-z0-9_]*/g,'').trim();input.rows=7;input.maxLength=4800}
      else if(key==='title')input.maxLength=100;else{input.rows=2;input.maxLength=400}
      input.oninput=()=>{dirty=true;notice.textContent='Unsaved changes.'};fields[key]=input;wrap.append(input);detail.append(wrap);
    }
    if(post.platform==='instagram'){const note=document.createElement('p');note.className='muted';note.textContent='The title and hashtags are the text shown with this Reel.';detail.append(note)}
    const actions=document.createElement('div');actions.className='scheduled-actions';
    for(const [action,label] of post.bucket==='failed'?[['delete','Delete']]:[['save','Save changes'],['publish_now','Publish now'],['cancel','Cancel schedule']]){
      const control=document.createElement('button');control.type='button';control.dataset.action=action;control.textContent=label;control.disabled=!scheduledActionEnabled(post,action,pending);if(action==='publish_now')control.className='publish-now';
      if(action==='delete')control.title='Remove this failed attempt from the list. The platform video and saved media are kept.';
      control.onclick=async()=>{
        if(pending)return;pending=true;actions.querySelectorAll('button').forEach(b=>b.disabled=true);notice.textContent=action==='delete'?'Removing this failed attempt…':action==='cancel'?'0/1 complete · Cancelling this schedule…':action==='publish_now'?'Requesting publication of this post only…':'Saving this post’s text…';
        try{
          const data=await api('/api/scheduled/action',{id:post.id,revision:post.revision,action,...(['cancel','delete'].includes(action)?{}:{fields:Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.value]))})});
          if(action==='cancel')pendingCancellation=post.id;
          if(action==='delete')pendingDeletion=post.id;
          dirty=false;notice.textContent=data.message;await load(true);
        }catch(error){notice.textContent=window.storylensError(error)}finally{pending=false;actions.querySelectorAll('button').forEach(b=>b.disabled=!scheduledActionEnabled(post,b.dataset.action));if(!dirty)await load(true)}
      };
      actions.append(control);
    }
    detail.append(actions);
    if(post.platform==='youtube'&&post.url){const match=post.url.match(/[?&]v=([\w-]{11})(?:&|$)/);if(match){const manage=document.createElement('a');manage.href='https://studio.youtube.com/video/'+match[1]+'/edit';manage.target='_blank';manage.rel='noopener';manage.textContent='Manage schedule in YouTube Studio';detail.append(manage)}}
    if(post.prepare_post_id){const link=document.createElement('a');link.href='prepare-post.html?profile='+encodeURIComponent(post.profile);link.textContent='Open Prepare & post';detail.append(link)}
    if(post.operation?.message){const message=document.createElement('p');message.textContent=post.operation.message;detail.append(message)}
    if(/^[a-f0-9]{16}$/.test(post.session)){const link=document.createElement('a');link.href='/?chat='+encodeURIComponent(post.session);link.textContent='Open source chat';detail.append(link)}
    if(post.url&&/^https:\/\/(?:www\.youtube\.com\/watch\?v=[\w-]+|www\.instagram\.com\/)/.test(post.url)){const link=document.createElement('a');link.href=post.url;link.target='_blank';link.rel='noopener';link.textContent='View on '+(post.platform==='youtube'?'YouTube':'Instagram');detail.append(document.createElement('br'),link)}
  }
  async function load(force=false){
    clearTimeout(timer);
    try{
      const data=await api('/api/scheduled');
      if(pendingCancellation&&(data.cancelled_ids||[]).includes(pendingCancellation)){notice.textContent='1/1 complete · Schedule cancelled. The saved video is kept.';pendingCancellation='';}
      if(pendingCancellation){const attempt=data.posts.find(p=>p.id===pendingCancellation);if(['failed','needs_review'].includes(attempt?.operation?.status)){notice.textContent=attempt.operation.message||'Cancellation could not be verified. Check Failed attempts.';pendingCancellation='';}}
      if(pendingDeletion&&(data.deleted_ids||[]).includes(pendingDeletion)){notice.textContent='Deleted from Failed attempts.';pendingDeletion='';}
      if(!data.prepare_post_queue_included){
        if(Date.now()-publisherJobsReadAt>30000){
          const queue=await api('/api/publisher?profile='+profileFilter);
          publisherJobs=queue.jobs;publisherJobsReadAt=Date.now();
        }
        data.posts=storylensScheduledRows(data.posts,publisherJobs);
      }
      // Also classify the older backend's response while an owner task prevents
      // a safe server restart. This only changes the view, never queue state.
      posts=data.posts.filter(post=>post.status!=='cancelled'&&!(data.deleted_ids||[]).includes(post.id)).map(post=>{
        const expired=post.platform==='youtube'&&['scheduled','ready'].includes(post.status)&&post.publish_at&&new Date(post.publish_at)<=new Date()&&post.operation?.status!=='working';
        const bucket=post.bucket||(['needs_review','blocked','failed'].includes(post.status)||post.operation?.action==='cancel'&&['failed','needs_review'].includes(post.operation?.status)||expired?'failed':'scheduled');
        return {...post,bucket,can_edit:post.can_edit&&bucket!=='failed',message:expired?'The release time has passed, but publication is not confirmed. Check YouTube before retrying.':post.message};
      });
      const pendingCount=posts.filter(p=>p.bucket!=='failed').length;button.textContent='Scheduled posts'+(pendingCount?' · '+pendingCount:'');
      if(dialog.open){
        if(selected&&!filtered().some(p=>p.id===selected)){selected='';dirty=false;renderedRevision=''}
        renderChannels();renderPlatforms();
        const post=filtered().find(p=>p.id===selected)||preferred(filtered());
        if(post&&(force||(!dirty&&!detail.contains(document.activeElement)&&(post.id!==selected||post.revision!==renderedRevision)))){selected=post.id;renderDetail(post)}
        else if(!post){selected='';detail.textContent='No scheduled posts for this channel.'}
        renderList();
        if(data.refresh_warning&&!dirty&&!pending)notice.textContent=data.refresh_warning;
      }
    }catch(error){if(dialog.open)notice.textContent=window.storylensError(error)}
    timer=setTimeout(()=>load(),dialog.open?5000:30000);
  }
  button.onclick=()=>{dirty=false;notice.textContent='All times are India time (IST). Publishing now affects only the selected post.';dialog.showModal();load(true)};
  document.addEventListener('storylens-publishing-profile',event=>{if(!['cricket','gaming'].includes(event.detail)||dirty)return;profileFilter=event.detail;selected='';if(dialog.open){renderChannels();renderPlatforms();selectDefault();renderList()}});
  load();
})();
