let mode='clean',captionStyle='flash_cut',bridge=window.HINGLISH_BRIDGE,token=null,jobId=null;
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
function evalHost(code){return new Promise(resolve=>window.__adobe_cep__.evalScript(code,resolve))}
function startBridge(){try{const cp=require('child_process'),path=require('path');const py=path.join(window.HINGLISH_APP_ROOT,'.venv','Scripts','python.exe');const p=cp.spawn(py,['-m','hinglish_app','--no-open'],{cwd:window.HINGLISH_APP_ROOT,detached:true,windowsHide:true,stdio:'ignore'});p.unref()}catch(_){} }
async function connect(){for(let i=0;i<10;i++){try{const r=await fetch(bridge+'/api/bridge');const d=await r.json();token=d.token;$('#connection').textContent='Local AI connected';return}catch(_){if(i===0)startBridge();await new Promise(r=>setTimeout(r,700))}}$('#connection').textContent='Start Run Hinglish Editor.bat';throw new Error('Local AI is not running')}
async function api(path,options={}){if(!token)await connect();const r=await fetch(bridge+path,{...options,headers:{'Content-Type':'application/json','X-Hinglish-Token':token,...options.headers}});const d=await r.json();if(!r.ok)throw new Error(d.error||'Request failed');return d}
const runLabels={clean:'Clean selected clips',script:'Build timeline from selected clips',captions:'Generate captions for selected clips',broll:'Add B-roll to the open sequence'};
$$('.feature').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;$$('.feature').forEach(x=>x.classList.toggle('active',x===b));$('#scriptBox').classList.toggle('hidden',mode==='clean'||mode==='broll');$('#captionBox').classList.toggle('hidden',mode!=='captions');$('#brollBox').classList.toggle('hidden',mode!=='broll');$('#run').textContent=runLabels[mode]});
$$('.caption-style').forEach(b=>b.onclick=()=>{captionStyle=b.dataset.style;$$('.caption-style').forEach(x=>x.classList.toggle('active',x===b))});
async function exportSequence(){
  const fs=require('fs'),path=require('path');
  const folder=path.join(window.HINGLISH_APP_ROOT,'cache','app','exports');fs.mkdirSync(folder,{recursive:true});
  const target=path.join(folder,`sequence-${Date.now()}.xml`);
  const result=JSON.parse(await evalHost('hinglishExportActiveSequence('+JSON.stringify(target)+')'));
  if(result.error)throw new Error(result.error);
  return result.path;
}
$('#run').onclick=async()=>{try{$('#error').textContent='';$('#done').classList.add('hidden');let payload;
  if(mode==='broll'){const timeline=await exportSequence();payload={mode,timeline_xml:timeline,density:$('#density').value,device:$('#device').value,host:'premiere'}}
  else{const raw=await evalHost('hinglishSelectedMedia()');const selected=JSON.parse(raw);if(selected.error)throw new Error(selected.error);if(!selected.paths.length)throw new Error('Select video clips in the timeline or Project panel first.');payload={mode,source_paths:selected.paths,script:$('#script').value,caption_style:captionStyle,format:$('#format').value,device:$('#device').value,preview:false,host:'premiere'}}
  const job=await api('/api/jobs',{method:'POST',body:JSON.stringify(payload)});jobId=job.id;$('#run').disabled=true;$('#progress').classList.remove('hidden');poll()}catch(e){$('#error').textContent=e.message}};
async function poll(){try{const j=await api('/api/jobs/'+jobId);$('#status').textContent=j.status==='running'?'Editing locally':'Preparing';$('#percent').textContent=j.progress+'%';$('progress').value=j.progress;$('#stage').textContent=j.stage;if(j.status==='complete'){const result=await evalHost('hinglishImportXML('+JSON.stringify(JSON.stringify(j.result.xml_files))+')');if(result!=='ok')throw new Error(result);$('#progress').classList.add('hidden');$('#done').classList.remove('hidden');$('#run').disabled=false;return}if(j.status==='failed')throw new Error(j.stage);setTimeout(poll,900)}catch(e){$('#run').disabled=false;$('#error').textContent=e.message}}
connect().catch(()=>{});
