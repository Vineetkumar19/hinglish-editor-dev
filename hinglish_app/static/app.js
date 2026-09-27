const token=document.documentElement.dataset.token;
const headers={'Content-Type':'application/json','X-Hinglish-Token':token};
const TIMELINE_MODES=['broll','visuals','zoom','sound','eyecontact'];
let mode='clean',captionStyle='flash_cut',jobId=null,timer=null,lastResult=null,sourcePaths=[];
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);

async function api(path,options={}){
  const response=await fetch(path,{...options,headers:{...headers,...(options.headers||{})}});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Something went wrong');
  return data;
}

function setMode(next){
  mode=next;
  $$('.mode').forEach(x=>x.classList.toggle('active',x.dataset.mode===mode));
  $$('.script-field').forEach(x=>x.classList.toggle('hidden',mode!=='script'));
  $$('.caption-script-field').forEach(x=>x.classList.toggle('hidden',!['captions','visuals'].includes(mode)));
  $$('.caption-field').forEach(x=>x.classList.toggle('hidden',mode!=='captions'));
  $$('.broll-field').forEach(x=>x.classList.toggle('hidden',mode!=='broll'));
  $$('.visuals-field').forEach(x=>x.classList.toggle('hidden',mode!=='visuals'));
  $$('.zoom-field').forEach(x=>x.classList.toggle('hidden',mode!=='zoom'));
  $$('.sound-field').forEach(x=>x.classList.toggle('hidden',mode!=='sound'));
  $$('.eye-field').forEach(x=>x.classList.toggle('hidden',mode!=='eyecontact'));
  $$('.timeline-field').forEach(x=>x.classList.toggle('hidden',!TIMELINE_MODES.includes(mode)));
  if(mode==='broll'||mode==='visuals')loadBrollSettings();
  if(mode==='sound')loadSoundSettings();
  if(mode==='eyecontact')loadEyeStatus();
  const data={
    clean:['SMART CLEAN','Remove silence','Clean my videos','✂','Each selected video receives its own cleaned timeline.'],
    script:['SCRIPT EDIT','Build by meaning','Build my timeline','≋','Selected clips are arranged by the meaning of your script.'],
    captions:['AUTO CAPTIONS','Premium Hinglish captions','Generate captions','CC','Selected videos receive timed Roman Hinglish captions.'],
    broll:['ADD B-ROLL','B-roll for what you say','Add B-roll','▶','Choose a video, or a timeline XML from Smart Clean / Script Edit / Premiere.'],
    visuals:['SMART VISUALS','Real photos, logos and footage','Add smart visuals','◈','Choose a video, or a timeline XML from Smart Clean / Script Edit / B-roll / Premiere.'],
    zoom:['SMART ZOOM','Zooms on key moments','Add smart zooms','⤢','Choose a video, or a timeline XML from Smart Clean / Script Edit / B-roll / Premiere.'],
    sound:['SOUND DESIGN','Music and effects by meaning','Design the sound','♪','Choose a video, or your finished timeline XML (e.g. after B-roll and Smart Zoom).'],
    eyecontact:['EYE CONTACT','Look into the camera','Fix eye contact','◉','Choose your camera videos, or a timeline XML (only your camera clips are processed).']
  }[mode];
  $('#stepLabel').textContent=data[0];$('#modeTitle').textContent=data[1];
  $('#runText').textContent=data[2];$('#runIcon').textContent=data[3];$('#inputHelp').textContent=data[4];
}

$$('.mode').forEach(x=>x.onclick=()=>setMode(x.dataset.mode));
$$('.caption-card').forEach(x=>x.onclick=()=>{
  captionStyle=x.dataset.style;
  $$('.caption-card').forEach(card=>card.classList.toggle('active',card===x));
});

function uploadOne(file,batch,index,total){
  return new Promise((resolve,reject)=>{
    const url=`/api/upload?batch=${encodeURIComponent(batch)}&name=${encodeURIComponent(file.name)}`;
    const xhr=new XMLHttpRequest();
    xhr.open('POST',url);
    xhr.setRequestHeader('X-Hinglish-Token',token);
    xhr.setRequestHeader('Content-Type','application/octet-stream');
    xhr.upload.onprogress=event=>{
      if(!event.lengthComputable)return;
      const filePercent=Math.round(event.loaded/event.total*100);
      $('#inputHelp').textContent=`Adding video ${index+1}/${total} · ${filePercent}%`;
    };
    xhr.onload=()=>{
      let data={};
      try{data=JSON.parse(xhr.responseText||'{}')}catch(_){data={error:'The local app returned an invalid response'}}
      if(xhr.status>=200&&xhr.status<300)resolve(data);else reject(new Error(data.error||'Could not add video'));
    };
    xhr.onerror=()=>reject(new Error('The local app lost connection while adding the video'));
    xhr.send(file);
  });
}

async function addVideos(fileList){
  const videos=[...fileList].filter(file=>/\.(mp4|mov|mxf|mkv|avi|mts|m2ts|webm)$/i.test(file.name));
  if(!videos.length){alert('Choose at least one supported video file.');return}
  const createId=typeof crypto.randomUUID==='function'?crypto.randomUUID():`${Date.now()}-${Math.random()}`;
  const batch=createId.replace(/[^a-z0-9-]/gi,'');
  sourcePaths=[];
  $('#browse').disabled=true;$('#browseFolder').disabled=true;$('#run').disabled=true;
  try{
    for(let index=0;index<videos.length;index++){
      const uploaded=await uploadOne(videos[index],batch,index,videos.length);
      sourcePaths.push(uploaded.path);
    }
    $('#inputPath').value=`${videos.length} video${videos.length===1?'':'s'} selected`;
    $('#selectedFiles').textContent=videos.map(file=>file.name).join('  •  ');
    $('#selectedFiles').classList.remove('hidden');
    $('#inputHelp').textContent=`Ready: ${videos.length} local video${videos.length===1?'':'s'}`;
  }catch(error){
    sourcePaths=[];$('#inputPath').value='';$('#selectedFiles').classList.add('hidden');alert(error.message);
  }finally{
    $('#browse').disabled=false;$('#browseFolder').disabled=false;$('#run').disabled=false;
    $('#videoFiles').value='';$('#videoFolder').value='';
  }
}

$('#browse').onclick=()=>$('#videoFiles').click();
$('#browseFolder').onclick=()=>$('#videoFolder').click();
$('#videoFiles').onchange=event=>addVideos(event.target.files);
$('#videoFolder').onchange=event=>addVideos(event.target.files);
$('#inputPath').addEventListener('input',()=>{
  sourcePaths=[];$('#selectedFiles').classList.add('hidden');
});

$('#loadScript').onclick=()=>$('#scriptFile').click();
$('#scriptFile').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;
  $('#script').value=await file.text();countWords();event.target.value='';
};
$('#loadCaptionScript').onclick=()=>$('#captionScriptFile').click();
$('#captionScriptFile').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;
  $('#captionReference').value=await file.text();event.target.value='';
};
function countWords(){
  const n=$('#script').value.trim().split(/\s+/).filter(Boolean).length;
  $('#scriptCount').textContent=`${n} words`;
}
$('#script').addEventListener('input',countWords);

// ---- B-roll ----
const inResolve=new URLSearchParams(location.search).get('host')==='resolve';
let libraryFolders=[];
if(inResolve)$('.broll-resolve').classList.remove('hidden');
function renderLibrary(){
  $('#libraryList').innerHTML='';
  libraryFolders.forEach((folder,i)=>{const li=document.createElement('li');li.textContent=folder;
    const remove=document.createElement('button');remove.type='button';remove.textContent='Remove';
    remove.onclick=()=>{libraryFolders.splice(i,1);renderLibrary()};li.append(remove);$('#libraryList').append(li)});
  if(!libraryFolders.length)$('#libraryList').innerHTML='<li>No folders yet — add folders with your own clips (travel, food, city shots…)</li>';
}
function showSettings(s){
  $('#pexelsSaved').textContent=s.pexels_key;$('#pixabaySaved').textContent=s.pixabay_key;
  $('#usePexels').checked=s.use_pexels;$('#usePixabay').checked=s.use_pixabay;$('#useLibrary').checked=s.use_library;
  libraryFolders=[...s.library_folders];renderLibrary();
  const sources=[];if(s.use_library&&s.library_folders.length)sources.push(`My footage (${s.library_folders.length} folder${s.library_folders.length===1?'':'s'})`);
  if(s.use_pexels&&s.pexels_key)sources.push('Pexels');if(s.use_pixabay&&s.pixabay_key)sources.push('Pixabay');
  $('#sourceSummary').textContent=sources.length?sources.join(' + '):'None yet — open B-roll settings';
  $('#visualsSources').textContent=['Whole web + YouTube','Wikipedia'].concat(sources.filter(x=>x==='Pexels'||x==='Pixabay')).join(' + ');
}
async function loadBrollSettings(){try{showSettings(await api('/api/broll/settings'))}catch(e){$('#sourceSummary').textContent=e.message}}
$('#openBrollSettings').onclick=()=>{$('#settingsError').textContent='';$('#brollSettings').showModal()};
$('#addLibrary').onclick=async()=>{try{const r=await api('/api/pick?kind=folder');if(r.path&&!libraryFolders.includes(r.path)){libraryFolders.push(r.path);renderLibrary()}}catch(e){$('#settingsError').textContent=e.message}};
$('#saveBrollSettings').onclick=async()=>{
  try{const s=await api('/api/broll/settings',{method:'POST',body:JSON.stringify({pexels_key:$('#pexelsKey').value,
      pixabay_key:$('#pixabayKey').value,use_pexels:$('#usePexels').checked,use_pixabay:$('#usePixabay').checked,
      use_library:$('#useLibrary').checked,library_folders:libraryFolders})});
    $('#pexelsKey').value='';$('#pixabayKey').value='';showSettings(s);$('#brollSettings').close();
  }catch(e){$('#settingsError').textContent=e.message}
};
// ---- Quality check ----
function showQuality(result){
  const q=result.quality_summary,box=$('#qualityMeta');
  $('#openQuality').classList.toggle('hidden',!result.quality);
  if(!q){box.textContent='';box.className='quality-meta';return}
  const redo=q.attempts>1?` · redone ${q.attempts-1}x, using attempt ${q.used}`:'';
  box.className='quality-meta '+(q.passed?'ok':'warn');
  box.textContent=q.passed?`Quality check passed · ${q.score}/100${redo}`:`Quality ${q.score}/100${redo} · still failing: ${q.failed.join('; ')}`;
}
// ---- Eye contact ----
async function loadEyeStatus(){
  const box=$('#eyeStatus');box.className='eye-status';box.textContent='Checking this PC…';
  try{const s=await api('/api/eyecontact/status');
    box.classList.add(s.ready?'ok':'warn');
    box.textContent=s.ready?`Ready on ${s.gpu}`:(s.checks.find(c=>!c.ok)||{text:'Not set up yet'}).text;
  }catch(e){box.classList.add('warn');box.textContent=e.message}
}
// ---- Sound design ----
async function loadSoundSettings(){try{const s=await api('/api/sound/settings');
  $('#musicFolder').textContent=s.music_folder;$('#sfxFolder').textContent=s.sfx_folder}catch(e){$('#musicFolder').textContent=e.message}}
async function changeSoundFolder(key){try{const r=await api('/api/pick?kind=folder');if(!r.path)return;
  await api('/api/sound/settings',{method:'POST',body:JSON.stringify({[key]:r.path})});loadSoundSettings()}catch(e){alert(e.message)}}
$('#pickMusic').onclick=()=>changeSoundFolder('music_folder');
$('#pickSfx').onclick=()=>changeSoundFolder('sfx_folder');

$('#pickXml').onclick=async()=>{try{const r=await api('/api/pick?kind=xml');if(r.path){sourcePaths=[];$('#inputPath').value=r.path;
  $('#selectedFiles').classList.add('hidden');if(inResolve)$('#useResolve').checked=false}}catch(e){alert(e.message)}};

$('#run').onclick=async()=>{
  try{
    const payload={mode,source_paths:sourcePaths,input_path:sourcePaths.length?'':$('#inputPath').value,
      script:['captions','visuals'].includes(mode)?$('#captionReference').value:$('#script').value,
      caption_style:captionStyle,format:$('#format').value,density:$('#density').value,
      use_resolve_timeline:TIMELINE_MODES.includes(mode)&&inResolve&&$('#useResolve').checked,
      eye_reach:$('#eyeReach').value,eye_size:$('#eyeSize').value,eye_look_away:$('#eyeLookAway').checked,
      sound_style:$('#soundStyle').value,sound_density:$('#soundDensity').value,sound_music:$('#soundMusic').checked,
      sound_effects:$('#soundEffects').checked,sound_transitions:$('#soundTransitions').checked,
      visuals_density:$('#visualsDensity').value,visuals_brain:$('#visualsBrain').value,visuals_popups:$('#visualsPopups').checked,visuals_web:$('#visualsWeb').checked,visuals_check:$('#visualsCheck').checked,
      zoom_style:$('#zoomStyle').value,zoom_strength:$('#zoomStrength').value,zoom_frequency:$('#zoomFrequency').value,
      zoom_face:$('#zoomFace').checked,zoom_jump_cuts:$('#zoomJumpCuts').checked,
      device:$('#device').value,pacing:$('#pacing').value,preview:true};
    const job=await api('/api/jobs',{method:'POST',body:JSON.stringify(payload)});
    jobId=job.id;lastResult=null;$('#run').disabled=true;$('#result').classList.add('hidden');
    $('#progress').classList.remove('hidden');lostPolls=0;poll();
  }catch(e){alert(e instanceof TypeError?'The local engine is not running. Double-click Run Hinglish Editor.bat in the DEV folder, then try again.':e.message)}
};

let lostPolls=0;
function engineProblem(e){
  // Network error: the local engine window closed or is restarting. Keep trying for about a minute.
  if(e instanceof TypeError){
    lostPolls++;
    if(lostPolls<=60){
      $('#statusText').textContent='Reconnecting to the local engine…';
      $('#stage').textContent=`The engine is not answering (${lostPolls}s). Keep the Hinglish Editor window open.`;
      timer=setTimeout(poll,1000);return true;
    }
    return 'The local engine stopped. Double-click Run Hinglish Editor.bat in the DEV folder, then click the orange button again.';
  }
  // A different/restarted engine does not know this page or this job.
  if(/Not connected|Job not found/.test(e.message))
    return 'The local engine restarted, so this run stopped. Press F5 to reload this page, then click the orange button again.';
  return null;
}

async function poll(){
  try{
    const job=await api(`/api/jobs/${jobId}`);lostPolls=0;$('#percent').textContent=`${job.progress}%`;
    $('#bar').style.width=`${job.progress}%`;$('#stage').textContent=job.stage;
    $('#statusText').textContent=job.status==='running'?'Editing locally':job.status==='failed'?'Could not finish':'Preparing';
    $('#logs').textContent=job.logs.join('\n');$('#logs').scrollTop=$('#logs').scrollHeight;
    if(job.status==='complete'){
      lastResult=job.result;$('#run').disabled=false;$('#progress').classList.add('hidden');
      $('#result').classList.remove('hidden');$('#resultMeta').textContent=`${job.result.xml_files.length} editable XML timeline${job.result.xml_files.length===1?'':'s'} created`;
      showQuality(job.result);return;
    }
    if(job.status==='failed')throw new Error(job.stage);
    timer=setTimeout(poll,900);
  }catch(e){
    const problem=engineProblem(e);
    if(problem===true)return;
    $('#run').disabled=false;$('#statusText').textContent='Needs attention';$('#stage').textContent=problem||e.message;
  }
}

async function open(path){if(path)await api('/api/open',{method:'POST',body:JSON.stringify({path})})}
$('#openResult').onclick=()=>open(lastResult?.page);$('#openQuality').onclick=()=>open(lastResult?.quality);$('#openFolder').onclick=()=>open(lastResult?.folder);
$('#importResolve').onclick=async()=>{
  try{
    const button=$('#importResolve');button.disabled=true;button.textContent='Importing…';
    const result=await api('/api/import-resolve',{method:'POST',body:JSON.stringify({xml_files:lastResult?.xml_files||[]})});
    button.textContent=`Imported ${result.timelines.length} timeline${result.timelines.length===1?'':'s'} ✓`;
  }catch(e){$('#importResolve').disabled=false;$('#importResolve').textContent='Import to Resolve';alert(e.message)}
};
