/** @type {import('@adobe/premierepro').premierepro} */
const ppro=require('premierepro');
const bridge='http://127.0.0.1:8766';let token=null,mode='clean',captionStyle='flash_cut',jobId=null;
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
async function connect(){const r=await fetch(bridge+'/api/bridge');const d=await r.json();token=d.token;$('#connection').textContent='Local AI connected'}
async function api(path,options={}){if(!token)await connect();const r=await fetch(bridge+path,{...options,headers:{'Content-Type':'application/json','X-Hinglish-Token':token,...options.headers}});const d=await r.json();if(!r.ok)throw new Error(d.error||'Request failed');return d}
async function selectedPaths(){const project=await ppro.Project.getActiveProject();const paths=[];const add=async item=>{try{const clip=ppro.ClipProjectItem.cast(item);const path=await clip.getMediaFilePath();if(path&&!paths.includes(path))paths.push(path)}catch(_){}};const sequence=await project.getActiveSequence();if(sequence){const selection=await sequence.getSelection();const items=await selection.getTrackItems();for(const item of items){try{await add(await item.getProjectItem())}catch(_){}}}if(!paths.length){try{const selection=await ppro.ProjectUtils.getSelection(project);for(const item of await selection.getItems())await add(item)}catch(_){}}return paths}
async function exportSequence(){
  if(!ppro.ProjectConverter||!ppro.ProjectConverter.exportAsFinalCutProXML)throw new Error('Timeline features need Premiere Pro 26.2+ in this panel. Use the Window > Extensions panel instead.');
  const project=await ppro.Project.getActiveProject();const sequence=await project.getActiveSequence();
  if(!sequence)throw new Error('Open the sequence you want B-roll for first.');
  const folder=await require('uxp').storage.localFileSystem.getDataFolder();
  const target=folder.nativePath.replace(/[\\/]$/,'')+`\\sequence-${Date.now()}.xml`;
  if(!await ppro.ProjectConverter.exportAsFinalCutProXML(sequence,target,true))throw new Error('Premiere could not export the sequence XML.');
  return target;
}
const runLabels={clean:'Clean selected clips',script:'Build timeline from selected clips',captions:'Generate captions for selected clips',broll:'Add B-roll to the open sequence',visuals:'Add smart visuals to the open sequence',zoom:'Add smart zooms to the open sequence',sound:'Design the sound of the open sequence',eyecontact:'Fix eye contact in the open sequence'};
const onSequence=m=>['broll','visuals','zoom','sound','eyecontact'].includes(m);
$$('.mode').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;$$('.mode').forEach(x=>x.classList.toggle('active',x===b));$('#script').classList.toggle('hidden',mode==='clean'||onSequence(mode));$('#captionBox').classList.toggle('hidden',mode!=='captions');$('#brollBox').classList.toggle('hidden',mode!=='broll');$('#visualsBox').classList.toggle('hidden',mode!=='visuals');$('#zoomBox').classList.toggle('hidden',mode!=='zoom');$('#soundBox').classList.toggle('hidden',mode!=='sound');$('#eyeBox').classList.toggle('hidden',mode!=='eyecontact');$('#run').textContent=runLabels[mode]});
$$('.caption-style').forEach(b=>b.onclick=()=>{captionStyle=b.dataset.style;$$('.caption-style').forEach(x=>x.classList.toggle('active',x===b))});
$('#run').onclick=async()=>{try{$('#error').textContent='';let payload;
  if(onSequence(mode)){payload={mode,timeline_xml:await exportSequence(),density:$('#density').value,device:$('#device').value,host:'premiere',
    zoom_style:$('#zoomStyle').value,zoom_strength:$('#zoomStrength').value,zoom_frequency:$('#zoomFrequency').value,
    sound_style:$('#soundStyle').value,sound_density:$('#soundDensity').value,
    visuals_density:$('#visualsDensity').value,visuals_brain:$('#visualsBrain').value,visuals_popups:$('#visualsPopups').checked,
    eye_reach:$('#eyeReach').value,eye_size:$('#eyeSize').value,eye_look_away:$('#eyeLookAway').checked}}
  else{const paths=await selectedPaths();if(!paths.length)throw new Error('Select timeline video clips first.');payload={mode,source_paths:paths,script:$('#script').value,caption_style:captionStyle,format:$('#format').value,device:$('#device').value,preview:false,host:'premiere'}}
  const job=await api('/api/jobs',{method:'POST',body:JSON.stringify(payload)});jobId=job.id;$('#run').disabled=true;$('#progress').classList.remove('hidden');poll()}catch(e){$('#error').textContent=e.message}};
async function poll(){try{const j=await api('/api/jobs/'+jobId);$('progress').value=j.progress;$('#status').textContent=j.progress+'%';$('#stage').textContent=j.stage;if(j.status==='complete'){const project=await ppro.Project.getActiveProject();const bin=await project.getInsertionBin();const ok=await project.importFiles(j.result.xml_files,true,bin,false);if(!ok)throw new Error('Premiere could not import the generated XML.');$('#progress').classList.add('hidden');$('#done').classList.remove('hidden');$('#run').disabled=false;return}if(j.status==='failed')throw new Error(j.stage);setTimeout(poll,900)}catch(e){$('#run').disabled=false;$('#error').textContent=e.message}}
connect().catch(()=>{$('#connection').textContent='Start Run Hinglish Editor.bat'});
