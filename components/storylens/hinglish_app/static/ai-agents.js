(() => {
  const $=id=>document.getElementById(id), token=document.documentElement.dataset.token;
  let suite={}, social={accounts:[],comments:[]};
  const names={community:'Community',video_client:'Editing clients',sponsorship:'Sponsorships',saas_sales:'SaaS sales',job_hunter:'Jobs',fullstack_sales:'Development clients'};
  const blurbs={community:'Find relevant discussions and draft useful replies.',video_client:'Find gigs, quote your rates and prepare proposals.',sponsorship:'Find sponsors, draft pitches and track their replies.',saas_sales:'Find people with problems Storylens can genuinely solve.',job_hunter:'Find roles and prepare truthful applications.',fullstack_sales:'Find development projects and prepare quotes.'};
  const text=(tag,value,cls)=>{const e=document.createElement(tag);e.textContent=value||'';if(cls)e.className=cls;return e};
  async function api(path,body){
    const request={method:body?'POST':'GET',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'}};
    if(body)request.body=JSON.stringify(body);
    let response;
    try{response=await fetch('/api/agents/'+path,request)}
    catch(error){
      if(body)throw Error('Storylens did not confirm the request. Refresh to see its current status.');
      await new Promise(resolve=>setTimeout(resolve,900));
      try{response=await fetch('/api/agents/'+path,request)}
      catch(error){throw Error('Storylens is temporarily disconnected. Try Refresh when it is running.')}
    }
    const result=await response.json();
    if(!response.ok)throw Error(result.error_details?.replace(/^ValueError: /,'')||result.error||'Request failed');
    return result;
  }
  function show(page){for(const id of ['home','comments','suite'])$(id).hidden=id!==page}
  function button(label,fn,cls){const b=text('button',label,cls);b.onclick=async()=>{b.disabled=true;try{await fn()}catch(e){$('status').textContent=e.message}finally{b.disabled=false}};return b}
  async function task(action,payload){let t=await api('comments/'+action,payload);$('status').textContent=action==='draft'?'Reading the conversation and drafting a reply…':'Checking the selected account…';while(t.status==='running'){await new Promise(r=>setTimeout(r,1200));t=await api('task?id='+encodeURIComponent(t.id))}if(t.status!=='complete')throw Error(t.error||'The action did not complete');return t.result}
  async function loadSocial(){social=await api('comments/status');drawSocial();return social}
  async function refresh(){suite=await api('status');drawAgents();try{await loadSocial()}catch(e){$('status').textContent=e.message}$('status').textContent=suite.connected?'Agent Suite connected. Existing work and review queues are preserved.':suite.error;}
  async function connect(){suite=await api('connect',{});drawAgents();$('status').textContent='Agent Suite connected. Existing work and review queues are preserved.';await loadSocial()}
  async function openSuite(path,title){const result=await api('open',{path});$('suite-title').textContent=title;$('suite-frame').src=result.url;$('suite-window').href=result.url;show('suite')}
  function drawAgents(){
    $('connect').hidden=!!suite.connected;
    const first=text('article','','card');first.append(text('h3','Comment replies'),text('p','Read the tone and context. Reply naturally across both YouTube channels and Instagram pages.'),text('small','Four accounts · automatic checks every 12 hours'));
    first.append(button('Open replies',async()=>{await loadSocial();show('comments')},'primary'));
    const nodes=[first], developerNodes=[];
    const items=suite.agents?.length?suite.agents:['video_client','sponsorship','saas_sales','community','job_hunter','fullstack_sales'].map(key=>({key}));
    const ordered=[...items].sort((a,b)=>['video_client','sponsorship','saas_sales','community','job_hunter','fullstack_sales'].indexOf(a.key)-['video_client','sponsorship','saas_sales','community','job_hunter','fullstack_sales'].indexOf(b.key));
    for(const a of ordered){const card=text('article','','card');card.append(text('h3',names[a.key]||a.name),text('p',blurbs[a.key]||a.blurb),text('small',a.key==='saas_sales'&&suite.saas?.hosting==='local'?'Localhost only. Research and drafts are ready; promotion waits for your public link.':a.blocker||a.status||'Connect to see current work'));const actions=text('div','','actions');const open=button('Open',()=>openSuite(a.url||'/agent/'+a.key,names[a.key]||a.name));open.dataset.voiceLabel=names[a.key]||a.name;actions.append(open);if(a.key==='saas_sales')actions.append(button('Demand research',()=>openSuite(suite.saas?.demand_research_url||'/workflows','SaaS demand research')));if(a.pending)actions.append(text('span',a.pending+' waiting','badge'));card.append(actions);(['community','job_hunter','fullstack_sales'].includes(a.key)?developerNodes:nodes).push(card)}
    $('agents').replaceChildren(...nodes);
    const extra=text('article','','card');extra.append(text('h3','All workflows'),text('p','Client delivery, inbox commitments, research and the existing suite tools.'),button('Open workflows',()=>openSuite('/workflows','Agent Suite workflows')));developerNodes.push(extra);$('developer-agents').replaceChildren(...developerNodes);
    const connections=suite.connections||{};$('suite-connections').textContent=Object.entries(connections).map(([k,v])=>{const title=k.replaceAll('_',' ');return title+': '+(typeof v==='string'?v:v.status||v.message||(v.configured?'Configured; not live-verified':'Not connected'))}).join(' · ');
  }
  function accountTitle(a){return (a.profile==='cricket'?'Cricket':'Gaming')+' · '+(a.platform==='youtube'?'YouTube':'Instagram')}
  function drawSocial(){
    $('connections').replaceChildren(...(social.accounts||[]).map(a=>{const row=text('div','','connection');row.append(text('b',accountTitle(a)),text('span',a.blocker||(a.write_ready?'Replies ready':a.read_ready?'Reading ready':'Check connection')));return row}));
    $('accounts').replaceChildren(...(social.accounts||[]).map(a=>{
      const card=text('article','','account'),payload={platform:a.platform,profile:a.profile};card.append(text('h3',accountTitle(a)),text('small',a.account_id||a.channel_id||a.handle),text('p',a.blocker||a.cycle_error||a.scan_error||'Connection verified','blocker'));
      if(a.next_cycle)card.append(text('small','Next check '+new Date(a.next_cycle).toLocaleString(undefined,{timeZone:'Asia/Kolkata'})+' IST'));
      const controls=text('div','','actions'),select=document.createElement('select');select.dataset.voiceReview='';select.setAttribute('aria-label',accountTitle(a)+' reply mode');const modes=[['paused','Paused'],['review','Draft for review']];if(a.write_ready||a.mode==='auto')modes.push(['auto','Automatic replies']);for(const [value,label] of modes)select.append(new Option(label,value));select.value=a.mode||'paused';const cap=document.createElement('input');cap.type='number';cap.dataset.voiceReview='';cap.min='0';cap.max='100';cap.value=a.daily_cap??20;cap.setAttribute('aria-label',accountTitle(a)+' daily reply limit');cap.title='Daily reply limit. Zero uses the platform limit.';cap.style.width='76px';select.onchange=async()=>{select.disabled=true;try{await task('settings',{...payload,mode:select.value,daily_cap:Number(cap.value)});await loadSocial();$('status').textContent='Reply mode saved.'}catch(e){$('status').textContent=e.message;select.value=a.mode||'paused'}finally{select.disabled=false}};cap.onchange=()=>select.onchange();controls.append(select,text('small','Max/day (0 = all)'),cap,button('Check',async()=>{await task('check',payload);await loadSocial();$('status').textContent='Connection check complete.'}));
      if(a.platform==='youtube'&&!a.write_ready)controls.append(button('Connect replies',async()=>{await task('connect',payload);await loadSocial();$('status').textContent='YouTube reply permission checked.'}));
      controls.append(button('Check comments',async()=>{const result=await task('refresh',payload);await loadSocial();$('status').textContent=result.scan_warning||result.scan_error||(!result.read_ready&&result.blocker)||'Comment check complete.'}));
      if(a.mode!=='paused')controls.append(button('Run replies now',async()=>{
        const result=await task('run',payload);
        await loadSocial();
        $('status').textContent=result.run_errors?.[0]?.error||'Reply cycle complete.';
      }));
      if(a.platform==='instagram'&&a.mode==='paused'){
        controls.append(button('Enable Chrome replies',async()=>{
          await task('connect',payload);
          await loadSocial();
          $('status').textContent='Automatic Instagram replies enabled.';
        }));
      }
      for (const action of controls.querySelectorAll('button')) {
        action.dataset.voiceLabel=action.textContent+' for '+accountTitle(a);
        if (['Run replies now','Enable Chrome replies','Connect replies'].includes(action.textContent)) action.dataset.voiceReview='';
      }
      card.append(controls);
      return card;
    }));
    const rows=social.comments||[];
    if(!rows.length){$('inbox').replaceChildren(text('p','New comments will appear here after an account is connected and checked.','muted'));return}
    $('inbox').replaceChildren(...rows.map(c=>{const card=text('article','','comment');card.append(text('small',accountTitle(c)+' · '+(c.state||c.status||'new')),text('h3',c.author||c.author_name||c.author_id||'Viewer'),text('blockquote',c.text||c.comment_text||c.body));if(c.draft)card.append(text('div',typeof c.draft==='string'?c.draft:c.draft.reply||c.draft.text||'','reply'));if(c.draft_model)card.append(text('small','Model: '+c.draft_model,'muted'));if(c.draft_fallback_reason)card.append(text('small',c.draft_fallback_reason,'muted'));if(c.state==='review'&&!c.draft&&c.reason)card.append(text('p',c.reason,'muted'));if(c.error)card.append(text('p',c.error,'muted'));const actions=text('div','','actions'),payload={platform:c.platform,profile:c.profile,comment_id:c.comment_id||c.id};if(['new','draft_error'].includes(c.state))actions.append(button('Draft reply',async()=>{const result=await task('draft',payload);await loadSocial();$('status').textContent=result.error||(result.state==='skipped'?'Comment skipped.':result.state==='review'?'Comment needs review.':'Reply drafted.')}));const account=(social.accounts||[]).find(a=>a.platform===c.platform&&a.profile===c.profile);if(c.draft)actions.append(button('Copy reply',async()=>{await navigator.clipboard.writeText(typeof c.draft==='string'?c.draft:c.draft.reply||c.draft.text||'');$('status').textContent='Reply copied.'}));if(c.draft&&account?.write_ready&&account.mode!=='paused'&&['draft','review'].includes(c.state))actions.append(button('Send reply',async()=>{await task('send',payload);await loadSocial();$('status').textContent='Delivery status updated.'},'primary'));const url=c.source_url||c.url||c.permalink;if(url&&/^https:\/\/(www\.)?(youtube\.com|instagram\.com)\//.test(url)){const link=text('a','View comment');link.href=url;link.target='_blank';link.rel='noopener noreferrer';actions.append(link)}card.append(actions);return card}));
  }
  $('developer-toggle').onclick=()=>{const panel=$('developer-agents');panel.hidden=!panel.hidden;$('developer-toggle').setAttribute('aria-expanded',String(!panel.hidden))};
  $('connect').onclick=()=>connect().catch(e=>$('status').textContent=e.message);
  $('refresh').onclick=()=>refresh().catch(e=>$('status').textContent=e.message);
  $('refresh-comments').onclick=()=>loadSocial().catch(e=>$('status').textContent=e.message);
  $('check-all').onclick=async()=>{const b=$('check-all');b.disabled=true;try{for(const a of social.accounts||[])await task('check',{platform:a.platform,profile:a.profile});await loadSocial();$('status').textContent='Account checks complete.'}catch(e){$('status').textContent=e.message}finally{b.disabled=false}};
  document.querySelectorAll('.back').forEach(b=>b.onclick=()=>show('home'));
  if(location.hash==='#comments')show('comments');
  refresh().then(()=>suite.connected?null:connect()).catch(e=>$('status').textContent=e.message);
})();