(() => {
  const host=document.querySelector('#autoCaptionPanel');
  if(!host)return;
  const $=s=>host.querySelector(s.replace(/^#/, '#ac-')), key='storylens-auto-caption-2-v1';
  const headers={'Content-Type':'application/json','X-Hinglish-Token':document.documentElement.dataset.token};
  const resultBar=window.storylensResults.mount($('#featureResultBar'),{onView:result=>window.open(result.page,'_blank','noopener')});
  let catalog=[],job=null,lastJob=null,timer=null,busy=false;
  let loadRequest=!!new URLSearchParams(location.search).get('job');
  function draft(){localStorage.setItem(key,JSON.stringify({text:$('#script').value,style:$('#style').value,method:$('#method').value,duration:$('#duration').value,format:$('#format').value,job,lastJob}));}
  function pending(value){busy=value;$('#generate').disabled=value;$('#generate').textContent=value?'Generating your captions…':'Generate captions';}
  function method(){const hf=$('#method').value==='hyperframes';$('#methodHelp').textContent=hf?'Hyperframes':'Qwen + Vision · Caption dataset';pending(busy);}
  function reference(){const row=catalog.find(r=>r.style===$('#style').value);$('#reference').textContent=row?'Reference: '+row.source.split(/[\\/]/).pop()+(row.base_style?'':' · automatic preparation'):'';$('#cards').querySelectorAll('button').forEach(card=>card.setAttribute('aria-pressed',String(card.dataset.reference===$('#style').value)));}
  function cards(){
    const images={"caption_1": "caption-reference-previews/caption_1.jpg", "caption_2": "caption-reference-previews/caption_2.jpg", "caption_3": "caption-reference-previews/caption_3.jpg", "caption_5": "caption-reference-previews/caption_5.jpg", "serif_circle_draft": "caption-reference-previews/serif_circle_draft.jpg", "kinetic_gold_draft": "caption-reference-previews/kinetic_gold_draft.jpg", "caption_4": "caption4-preview.png"};
    $('#cards').replaceChildren();
    for(const row of catalog){const card=document.createElement('button');card.type='button';card.className='caption-card';card.dataset.reference=row.style;card.disabled=!row.available;
      if(images[row.base_style]){const img=document.createElement('img');card.hidden=true;img.onload=()=>{card.hidden=false;};img.onerror=()=>{card.remove();for(const option of [...$('#style').options])if(option.value===row.style)option.remove();reference();};img.src=images[row.base_style];img.alt=row.name;card.append(img);}
      else{const preview=document.createElement('span');preview.className='ac-text-preview';preview.textContent=row.name;card.append(preview);}
      const label=document.createElement('span');label.textContent=row.name;card.append(label);card.onclick=()=>{$('#style').value=row.style;reference();draft();};$('#cards').append(card);
    }
  }
  async function refreshCatalog(){
    const previewStyles=new Set(['caption_1','caption_2','caption_3','caption_4','caption_5','serif_circle_draft','kinetic_gold_draft']);
    const rows=(await request('/api/captions/auto2/catalog')).styles.filter(row=>previewStyles.has(row.base_style)&&!/previous.*reference/i.test(row.name));
    if(JSON.stringify(rows)===JSON.stringify(catalog))return;
    const selected=$('#style').value;catalog=rows;$('#style').replaceChildren();
    for(const row of catalog){const option=document.createElement('option');option.value=row.style;option.textContent=row.name+(row.available?'':' · copying');option.disabled=!row.available;$('#style').append(option);}
    if(catalog.some(r=>r.style===selected))$('#style').value=selected;
    cards();reference();
  }
  async function request(url,options={}) {return window.storylensResponse(await window.storylensFetch(url,{...options,headers}));}
  function failed(error){$('#status').textContent=window.storylensError(error);}
  async function poll(){
    clearTimeout(timer);$('#reconnect').classList.add('hidden');
    try {
      const state=await request('/api/captions/auto2/job?id='+encodeURIComponent(job));
      if(loadRequest&&state.request){const r=state.request;$('#script').value=r.text;$('#style').value=r.style;$('#duration').value=r.duration;$('#format').value=r.format;reference();method();loadRequest=false;history.replaceState(null,'','/?tool=captions');}
      $('#status').textContent=state.message||'';
      if(state.status==='complete'){
        if(!/^\/caption-output\/script-previews\/[a-f0-9]+\/report\.html$/.test(state.url))throw Error('The preview link is unavailable. Check saved progress.');
        const project=await request(state.url.replace('report.html','caption-project.json'));
        if(!project.project_path)throw Error('Open editable captions to recover this saved project.');
        resultBar.setResult({folder:project.project_path.replace(/[/\\]caption-project\.json$/,''),page:state.url});
        $('#video').src=state.video_url;$('#video').classList.remove('hidden');$('#empty').classList.add('hidden');
        $('#editor').href=state.url;$('#evidence').href=state.evidence_url;$('#links').classList.remove('hidden');
        $('#models').textContent=(state.method==='hyperframes'?`Hyperframes ${state.engine_version}`:`${state.planner_model} · ${state.vision_model}`)+(state.reference_match?.approximate?' · Approximate match: '+state.reference_match.base_style.replaceAll('_',' '):'');
        $('#reviewText').replaceChildren();for(const [label,text] of Object.entries(state.review||{})){const p=document.createElement('p');p.textContent=label.replaceAll('_',' ')+': '+text;$('#reviewText').append(p);}
        $('#review').classList.toggle('hidden',state.method==='hyperframes');pending(false);lastJob=job;job=null;draft();
      }else if(state.status==='failed'||state.status==='interrupted'){
        if(state.status==='failed')failed(window.storylensJobError(state));pending(false);job=null;draft();
      }else {pending(true);timer=setTimeout(poll,2000);}
    }catch(error){
      failed(error);
      if(error.code==='not_found'){pending(false);job=null;draft();}
      else{$('#reconnect').classList.remove('hidden');pending(true);}
    }
  }
  $('#reconnect').onclick=poll;
  $('#form').addEventListener('input',draft);$('#style').addEventListener('change',reference);
  $('#method').addEventListener('change',()=>{method();draft();});
  $('#form').onsubmit=async event=>{
    event.preventDefault();if(busy)return;window.storylensClearError();
    const payload={text:$('#script').value,style:$('#style').value,method:$('#method').value,duration:$('#duration').value,format:$('#format').value};
    if(!payload.text.trim()){failed(Error('Paste captions to preview'));return;}
    job=crypto.randomUUID().replaceAll('-','');payload.request_id=job;draft();pending(true);resultBar.setPending();$('#status').textContent=payload.method==='hyperframes'?'Starting Hyperframes…':'Starting the reference-guided local model…';
    try{await request('/api/captions/auto2/start',{method:'POST',body:JSON.stringify(payload)});await poll();}
    catch(error){
      failed(error);
      if(error.code==='local_connection'||error.code==='unreadable_response'){$('#reconnect').classList.remove('hidden');pending(true);}
      else{pending(false);job=null;draft();}
    }
  };
  (async()=>{
    try{
      await refreshCatalog();
      let saved;try{saved=JSON.parse(localStorage.getItem(key)||'null')}catch{}
      $('#style').value=saved?.style||'caption_2';$('#method').value='hyperframes';$('#script').value=saved?.text||'';$('#duration').value=saved?.duration||10;$('#format').value=saved?.format||'instagram_vertical';lastJob=saved?.lastJob||null;job=new URLSearchParams(location.search).get('job')||saved?.job||lastJob;
      if(!$('#style').value&&catalog.length)$('#style').value=catalog[0].style;reference();method();if(job){pending(true);await poll();}
      setInterval(()=>refreshCatalog().catch(error=>{if(!busy)failed(error);}),5000);
      window.addEventListener('focus',()=>refreshCatalog().catch(failed));
    }catch(error){failed(error);$('#generate').disabled=true;}
  })();
  window.storylensCaptionGenerator={isRunning:()=>busy,submit:()=>$('#form').requestSubmit(),setScript:text=>{$('#script').value=text;draft();}};
  document.addEventListener('storylensmodechange',()=>{document.body.classList.toggle('captions-page',mode==='captions');document.title=mode==='captions'?'Auto Captions · Storylens':'Storylens';});
  const route=new URLSearchParams(location.search);
  if(route.get('tool')==='captions'||route.has('caption_source')){setMode('captions');document.body.classList.add('tools-visible');}
})();
