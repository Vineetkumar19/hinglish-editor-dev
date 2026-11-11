(()=>{
 const $=id=>document.getElementById(id),kind=document.body.dataset.workbench,token=document.documentElement.dataset.token;
 const query=new URLSearchParams(location.search),host=query.get('panel')==='1'&&['aftereffects','premiere'].includes(query.get('host'))?query.get('host'):'standalone';
 let current=null,paths=[],group='Best Shots',pollTimer=null,gradeMode='nodes';
 const gradeButtons=document.querySelectorAll('[data-grade-mode]');
 function selectGrade(mode){
  gradeMode=mode;
  const realfilm=mode==='realfilm';
  for(const button of gradeButtons)button.setAttribute('aria-pressed',String(button.dataset.gradeMode===mode));
  for(const id of ['gradeNodeGraph','gradeNodeControls','downloadGrade'])$(id).hidden=realfilm;
  $('realfilmNodeGraph').hidden=!realfilm;
  $('gradeModeNote').textContent=realfilm
   ? 'Use your saved RealFilmV2_Rec709 PowerGrade. Fine-tune the editable nodes in Resolve for each shot.'
   : 'Build the original editable node structure and set a starting balance, contrast and saturation.';
 }
 if(new URLSearchParams(location.search).get('embedded')==='1'){document.querySelector('header').hidden=true;document.querySelector('main').style.padding='0';}
 async function api(path,body){const r=await window.storylensFetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(body?{body:JSON.stringify({...body,host})}:{})});return window.storylensResponse(r);}
 function error(e){const box=$('toolError');box.hidden=false;box.replaceChildren();const p=document.createElement('p');p.textContent=window.storylensProblem(e).message;box.append(p);const details=window.storylensDetails?.(e);if(details)box.append(details);}
 function busy(on){$('runTool').disabled=on;for(const button of gradeButtons)button.disabled=on;if($('stopTool'))$('stopTool').hidden=!on;$('toolProgress').hidden=!on;}
 function render(){
  if(kind!=='footage'||!current?.result?.assets)return;
  $('shotResults').hidden=false;const rows=current.result.assets.filter(a=>a.group===group);$('shots').replaceChildren();
  $('bestTab').setAttribute('aria-pressed',String(group==='Best Shots'));$('extrasTab').setAttribute('aria-pressed',String(group==='Extras'));
  $('bankSummary').textContent=rows.length+' '+group.toLowerCase();
  const sheets = $('contactSheets');
  sheets.replaceChildren();
  for (const sheet of current.result.review?.sheets || []) {
   const link = document.createElement('a');
   link.textContent = sheet.orientation + ' contact sheet ' + Number(sheet.file.match(/(\d+)\.jpg$/)[1]);
   link.href = '/api/workbench/media?' + new URLSearchParams({id:current.id, token, kind:'contact-sheet', sheet:sheet.file});
   link.target = '_blank';
   link.rel = 'noopener';
   sheets.append(link);
  }
  for(const asset of rows){const card=document.createElement('article');card.className='shot-card';const video=document.createElement('video');video.controls=true;video.preload='none';video.playsInline=true;video.src='/api/workbench/media?id='+current.id+'&asset='+asset.id+'&token='+encodeURIComponent(token);if(asset.poster)video.poster=video.src+'&kind=poster';const label=document.createElement('div');label.className='shot-caption';label.textContent=asset.duration.toFixed(1)+'s · '+asset.source.replace(/\\/g,'/').split('/').pop()+' · '+asset.start.toFixed(1)+'s';const link=document.createElement('a');link.textContent='Download';link.href=video.src+'&download=1';link.download='';const copy=document.createElement('button');copy.type='button';copy.textContent='Copy';copy.onclick=async()=>{copy.disabled=true;try{const result=await window.storylensBrowserNative.request('aftereffects','copyPaste',{action:'copyFile',paths:[asset.path]});if(result.error)throw Error(result.error);copy.textContent='Copied';}catch(e){error(e);}finally{copy.disabled=false;}};const exports=document.createElement('div');exports.className='editor-exports';window.storylensEditors.renderMedia(exports,asset.path);card.append(video,label,exports,link,copy);$('shots').append(card);}
  const folder=current.result.folder+'\\'+group;
  $('footageResult').replaceChildren();window.storylensResults.mount($('footageResult'),{title:group+' ready',meta:rows.length+' unique selections',onView:()=>$('shots').scrollIntoView({block:'nearest'}),onFolder:()=>api('/api/workbench/open',{id:current.id})}).setResult({folder});
  $('selectionDetails').textContent=JSON.stringify({filtered:current.result.duplicate_count,skipped:current.result.skipped,method:current.result.selection_method},null,2);
 }
 async function watch(id){
  const job=await api('/api/workbench/job?id='+id);current=job;$('toolStatus').textContent=job.stage;$('toolProgress').value=job.progress||0;
  if(['queued','running'].includes(job.status)){pollTimer=setTimeout(()=>watch(id).catch(e=>{busy(false);error(e);}),1000);return;}
  busy(false);if(job.status!=='complete'){render();throw Object.assign(Error(job.error?.message||job.stage),job.error);}
  if(kind==='footage'){$('toolStatus').textContent=job.result.best_count+' Best Shots · '+job.result.extra_count+' Extras';render();}
  else $('toolStatus').textContent=job.result.clips+' clips · '+job.result.node_count+' editable nodes · '+job.result.timeline;
 }
 $('toolForm').onsubmit=async e=>{e.preventDefault();if($('runTool').disabled)return;$('toolError').hidden=true;busy(true);try{let payload;
  if(kind==='footage'){
   const results=$('shotResults');document.querySelector('main').insertBefore(results,document.querySelector('.tool-history'));results.hidden=true;const history=document.querySelector('.tool-history');if(history)history.open=false;
   const files=[...$('videoFiles').files];if(files.length){for(let i=paths.length;i<files.length;i++){$('toolStatus').textContent='Adding video '+(i+1)+' of '+files.length;const r=await window.storylensFetch('/api/cinematic/upload?name='+encodeURIComponent(files[i].name)+'&host='+host,{method:'POST',headers:{'X-Hinglish-Token':token,'Content-Type':'application/octet-stream'},body:files[i]});const data=await window.storylensResponse(r);paths.push(data.path);}}
   payload={folder:$('sourceFolder').value.trim(),paths,best_count:$('allCandidates')?.checked?null:Number($('bestCount').value)};
  }else{
   payload={input_profile:$('inputProfile').value,grade_mode:gradeMode};
   if(gradeMode==='nodes')Object.assign(payload,{balance:Number($('gradeBalance').value),contrast:Number($('gradeContrast').value),saturation:Number($('gradeSaturation').value)});
  }
  const job=await api('/api/workbench/'+kind,payload);localStorage.setItem('storylens.workbench.'+kind,job.id);if($('open-last-extraction'))$('open-last-extraction').hidden=false;await watch(job.id);
 }catch(e){busy(false);error(e);}};
 if(kind==='footage'){
  $('browseFolder').onclick=async()=>{try{const result=await api('/api/pick?kind=folder');if(result.path){$('sourceFolder').value=result.path;paths=[];$('videoFiles').value='';$('sourceSummary').textContent='';}}catch(e){error(e);}};
  $('browseFiles').onclick=()=>$('videoFiles').click();$('videoFiles').onchange=()=>{paths=[];$('sourceFolder').value='';$('sourceSummary').textContent=$('videoFiles').files.length+' videos selected';};
  $('bestTab').onclick=()=>{group='Best Shots';render();};$('extrasTab').onclick=()=>{group='Extras';render();};$('openOutput').onclick=()=>api('/api/workbench/open',{id:current.id}).catch(error);$('stopTool').onclick=()=>current&&api('/api/workbench/cancel',{id:current.id}).catch(error);
  window.addEventListener('storylens-native-shots',e=>{if(Array.isArray(e.detail)){paths=e.detail;$('sourceFolder').value='';$('videoFiles').value='';$('sourceSummary').textContent=paths.length+' selected editor clips';}});
 }
 if(kind==='color-grade')$('downloadGrade').onclick=async e=>{e.preventDefault();try{const r=await window.storylensFetch('/api/workbench/grade-template',{headers:{'X-Hinglish-Token':token}});if(!r.ok){await window.storylensResponse(r);return;}const url=URL.createObjectURL(await r.blob()),link=document.createElement('a');link.href=url;link.download='Storylens SDR nodes.drx';link.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}catch(e){error(e);}};
 for(const button of gradeButtons)button.onclick=()=>selectGrade(button.dataset.gradeMode);
 const saved=localStorage.getItem('storylens.workbench.'+kind);
 if(kind==='footage')window.storylensOpenFootage=async(id,history)=>{if(!id||$('runTool').disabled)return;history.append($('shotResults'));busy(true);try{await watch(id)}catch(e){busy(false);error(e)}};
 else if(saved&&/^[a-f0-9]{32}$/.test(saved)){busy(true);watch(saved).catch(e=>{busy(false);error(e);});}
 window.addEventListener('beforeunload',()=>clearTimeout(pollTimer));
})();
