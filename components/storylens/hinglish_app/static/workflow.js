(()=>{
 const token=document.documentElement.dataset.token;
 async function refresh(){try{
  const r=await window.storylensFetch('/api/distribution',{headers:{'X-Hinglish-Token':token}}),data=await window.storylensResponse(r);if(!r.ok)throw Error(data.error||'Workflow unavailable');
  for(const p of ['cricket','gaming']){const yt=data.youtube_accounts[p],ig=data.instagram_accounts[p];document.getElementById(p+'Accounts').textContent='YouTube: '+(yt.connected?yt.name.trim():'Not connected')+' · Instagram: '+(ig?'@'+ig:'Not mapped yet')}
  const ready=data.batches.filter(b=>b.available_for_upload);document.getElementById('workflowSaved').textContent=ready.reduce((n,b)=>n+b.export_count,0)+' finished Shorts in '+ready.length+' saved batches. Viewing this page creates no publishing tasks.';
  const list=document.getElementById('workflowBatches');list.replaceChildren();for(const b of ready){const li=document.createElement('li');li.textContent=b.source+' · '+b.export_count+' clips · '+b.targets.map(t=>t.profile).join(', ')+' · '+b.clips.filter(c=>c.video_id).length+' YouTube upload receipts · '+b.clips.filter(c=>c.schedule_verified).length+' verified YouTube schedules';list.append(li)}
  document.getElementById('workflowChrome').textContent=data.chrome_connected?'Local Chrome extension connected.':'Local Chrome extension is offline. Open Chrome and connect Storylens before arming Instagram tasks.';
  const health=data.instagram_readiness||{};
  document.getElementById('workflowQueue').textContent=(health.queued||0)+' queued · '+(health.published||0)+' verified published · '+(health.attention_required||0)+' need attention'+(health.next_slot?' · Next slot: '+new Date(health.next_slot).toLocaleString():'.');
  const failures=document.getElementById('workflowFailures');failures.replaceChildren();
  for(const job of health.failures||[]){const li=document.createElement('li');li.textContent='@'+job.account+' · '+new Date(job.publish_at).toLocaleString()+' · '+(job.submission_started?'Outcome needs verification. ':'Share did not start. ')+job.message;failures.append(li)}
 }catch(e){document.getElementById('workflowSaved').textContent=window.storylensError(e)}}
 refresh();setInterval(refresh,15000);
})();
