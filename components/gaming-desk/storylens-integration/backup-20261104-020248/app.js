const token=document.documentElement.dataset.token;
const headers={'Content-Type':'application/json','X-Hinglish-Token':token};
const TIMELINE_MODES=['clean','script','broll','visuals','zoom','sound','eyecontact','aiimage','aivideo','motion'];
let mode='clean',captionStyle='caption_1',jobId=null,timer=null,lastResult=null,lastResultMode=null,sourcePaths=[];
let nativeConnectionTimer=null;
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
$('#device').value=document.documentElement.dataset.device==='cuda'?'cuda':'cpu';
if(document.documentElement.dataset.rtxOnly==='true'){
  $('#device').value='cuda';$('#device').disabled=true;
  $('#device').title='NVIDIA RTX is required for supported AI inference on this laptop';
}
function updateCaptionReference(){
  const shorts=mode==='shorts';
  const captions=mode==='captions',lyrics=captions&&$('#captionContent').value==='lyrics';
  $('#captionContent').closest('label').classList.toggle('hidden',!captions);
  $('#captionReferenceLabel').textContent=shorts?'Script (optional)':!captions?'Reference script (optional)':lyrics?'Exact song lyrics — keep one phrase per line':'Reference script for correct spellings (optional)';
  $('#captionReferenceHelp').textContent=!captions?'':lyrics?'Your wording and line breaks will be preserved':'Main names and English terms are enough';
  $('#loadCaptionScript').textContent=shorts?'Load script .txt':'Load reference .txt';
  $('#captionReference').placeholder=!captions?'Paste your script to help the AI understand the video. You can leave this empty.':lyrics?'Paste the exact lyric lines.':'Paste spelling hints or a reference script (optional).';
}
$('#captionContent').addEventListener('change',()=>{
  updateCaptionReference();
  if($('#captionContent').value==='lyrics'){
    captionStyle='minimal';$$('.caption-card').forEach(card=>card.classList.toggle('active',card.dataset.style===captionStyle));
  }
});

async function api(path,options={}){
  const response=await window.storylensFetch(path,{...options,headers:{...headers,...(options.headers||{})}});
  const data=await window.storylensResponse(response);
  if(!response.ok)throw new Error(data.error||'Something went wrong');
  return data;
}

function setMode(next){
  clearInterval(nativeConnectionTimer);nativeConnectionTimer=null;
  if(next==='nativeCaptions'||next==='textEffects'){next='captions';}
  mode=next==='aiimage'?'thumbnail':next;
  $('.panel').dataset.mode=mode;
  const routes={"cinematic": "cinematic-footage.html", "beats": "beats.html", "downloader": "downloader.html", "photos": "photos.html", "cricketDesk": "http://127.0.0.1:8879/", "gamingDesk": "http://127.0.0.1:8880/", "voiceover": "voiceover.html", "reelRecreate": "reel-recreate.html", "colorGrade": "color-grade.html", "templateImport": "editor-panel.html?host=aftereffects&browser=1&tool=templateImport", "templateAligner": "editor-panel.html?host=aftereffects&browser=1&tool=templateAligner", "templateText": "editor-panel.html?host=aftereffects&browser=1&tool=templateText", "copyPaste": "editor-panel.html?host=aftereffects&browser=1&tool=copyPaste", "imageDownload": "editor-panel.html?host=aftereffects&browser=1&tool=imageDownload", "nativeCaptions": "editor-panel.html?host=aftereffects&browser=1&tool=captions", "presetLibrary": "editor-panel.html?host=aftereffects&browser=1&tool=presetLibrary", "animationPresets": "editor-panel.html?host=aftereffects&browser=1&tool=animationPresets", "textEffects": "editor-panel.html?host=aftereffects&browser=1&tool=textEffects", "effectsLibrary": "editor-panel.html?host=aftereffects&browser=1&tool=effectsLibrary"};
  const embedded=Boolean(routes[mode]), embedHost=$('#embeddedTools');$('.panel').dataset.embedded=String(embedded);
  if(embedded){const engine=$('.panel .engine');if(engine){engine.replaceChildren(document.createTextNode(mode==='colorGrade'?'Uses Resolve':routes[mode].startsWith('editor-panel')?'Uses After Effects':'Local service'));}}
  if(routes[mode]?.startsWith('editor-panel')){
    const selected=mode,check=async()=>{try{const state=await api('/api/native-tools/connections');if(mode!==selected)return;const count=state.connections.filter(c=>c.host==='aftereffects').length;$('.panel .engine').textContent=count===1?'After Effects connected':count>1?'Keep one After Effects panel open':'Open Storylens in After Effects';}catch(_){if(mode===selected)$('.panel .engine').textContent='Editor connection unavailable';}};
    check();nativeConnectionTimer=setInterval(check,3000);
  }
  embedHost.hidden=!embedded;
  if(embedded){
    let frame=embedHost.querySelector(`[data-tool="${mode}"]`);
    if(!frame){frame=document.createElement('iframe');frame.dataset.tool=mode;frame.title=(document.querySelector('.mode[data-mode="'+mode+'"] b')?.textContent||mode)+' settings';frame.src=routes[mode]+(routes[mode].includes('?')?'&':'?')+'embedded=1';embedHost.append(frame)}
    embedHost.querySelectorAll('iframe').forEach(item=>{if(item!==frame)item.remove();});
  }
  syncResultBar();
  const outputSettings=$('#outputSettings');
  if(mode==='broll')$('#brollSettings form').insertBefore(outputSettings,$('#brollSettings .dialog-actions'));
  else $('.panel').insertBefore(outputSettings,$('#run'));
  $$('.mode').forEach(x=>x.classList.toggle('active',x.dataset.mode===mode));
  $$('.script-field').forEach(x=>x.classList.toggle('hidden',!(mode==='script'||(['aivideo','motion','thumbnail'].includes(mode)&&x.tagName!=='LABEL'))));
  $$('.caption-script-field').forEach(x=>x.classList.toggle('hidden',!['captions','visuals','sound','shorts'].includes(mode)));
  $$('.caption-field').forEach(x=>x.classList.toggle('hidden',mode!=='captions'));
  $$('.broll-field').forEach(x=>x.classList.toggle('hidden',mode!=='broll'));
  $$('.visuals-field').forEach(x=>x.classList.toggle('hidden',mode!=='visuals'));
  $$('.zoom-field').forEach(x=>x.classList.toggle('hidden',mode!=='zoom'));
  $$('.sound-field').forEach(x=>x.classList.toggle('hidden',mode!=='sound'));
  $$('.eye-field').forEach(x=>x.classList.toggle('hidden',mode!=='eyecontact'));
  $$('.shorts-field').forEach(x=>x.classList.toggle('hidden',mode!=='shorts'));

  $$('.aivideo-field').forEach(x=>x.classList.toggle('hidden',mode!=='aivideo'));
  $$('.motion-field').forEach(x=>x.classList.toggle('hidden',mode!=='motion'));
  $$('.gaming-field').forEach(x=>x.classList.toggle('hidden',mode!=='gaming'));
  $$('.thumbnail-field').forEach(x=>x.classList.toggle('hidden',mode!=='thumbnail'));
  if(mode==='thumbnail'||mode==='aivideo')loadAigen(mode);
  if(mode==='motion')loadMotionStyles();
  $$('.timeline-field').forEach(x=>x.classList.toggle('hidden',mode==='broll'||!TIMELINE_MODES.includes(mode)));
  if(mode==='broll')loadBrollSettings();
  if(mode==='sound')loadSoundSettings();
  if(mode==='eyecontact')loadEyeStatus();
  const data={
    cinematic:['CINEMATIC FOOTAGE','Cinematic Footage','','',''],
    beats:['BEAT STUDIO','Beat Studio','','',''],
    downloader:['DOWNLOADER','Download videos & extract audio','','',''],
    photos:['PHOTO COLLECTOR','Photos from your screenshot','','',''],
    cricketDesk:['CRICKET DESK','Cricket Desk','','',''],
    voiceover:['VOICE CLONE','Voice Clone','','',''],
    clean:['SMART CLEAN','Remove silence','Clean my videos','✂','Each selected video receives its own cleaned timeline.'],
    script:['SMART EDIT','Build by meaning','Build my timeline','≋','Selected clips are arranged by the meaning of your script.'],
    captions:['AUTO CAPTIONS','Premium Hinglish captions','Generate captions','CC','Selected videos receive timed Roman Hinglish captions.'],
    broll:['ADD B-ROLL','B-roll for what you say','Find B-roll','▶',''],
    visuals:['SMART VISUALS','Real photos, logos and footage','Add smart visuals','◈','Choose a video, or a timeline XML from Smart Clean / Smart Edit / B-roll / Premiere.'],
    zoom:['SMART ZOOM','Zooms on key moments','Add smart zooms','⤢','Choose a video, or a timeline XML from Smart Clean / Smart Edit / B-roll / Premiere.'],
    sound:['SOUND DESIGN','Music and effects by meaning','Design the sound','♪','Choose a video, or your finished timeline XML (e.g. after B-roll and Smart Zoom).'],
    eyecontact:['EYE CONTACT','Look into the camera','Fix eye contact','◉','Choose your camera videos, or a timeline XML (only your camera clips are processed).'],
    
    aivideo:['AI VIDEO','AI clips for your script','Make AI clips','▶','Paste your script below. Optional: choose your video or a timeline XML to get the clips placed on it.'],
    motion:['MOTION GRAPHICS','Motion graphics for your story','Make motion graphics','◧','Paste your script below, or choose your video / a timeline XML to get the graphics placed on it.'],
    gaming:['GAMING HIGHLIGHTS','The strongest moments from your stream','Create highlights','🎮','Choose your downloaded gaming stream. Full gameplay framing and stereo audio are preserved.'],
    thumbnail:['THUMBNAIL','Thumbnail','Create images','▧',''],
    shorts:['LONG TO SHORTS','Shorts from your long video','Make my shorts','▯','Choose your finished long video (MP4/MOV). Each video gets its own set of shorts.']
  }[mode]||['EDITOR TOOLS',document.querySelector('.mode[data-mode="'+mode+'"] b')?.textContent||mode,'','',''];
  $('#stepLabel').textContent=data[0];$('#modeTitle').textContent=data[1];
  $('#runText').textContent=data[2];$('#runIcon').innerHTML=window.storylensIcon(mode);$('#inputHelp').textContent=data[4];
  if(['clean','script'].includes(mode)&&/\.xml$/i.test($('#inputPath').value))$('#inputHelp').textContent='This saved timeline will return as an editable copy with its original source trims. Extra layers or effects need a video export first.';
  updateCaptionReference();
  document.dispatchEvent(new Event('storylensmodechange'));
}

$$('button.mode').forEach(x=>x.onclick=()=>setMode(x.dataset.mode));
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
    xhr.onload=()=>window.storylensXHR(xhr).then(resolve,reject);
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
    sourcePaths=[];$('#inputPath').value='';$('#selectedFiles').classList.add('hidden');window.storylensShowError(error);
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
  $('#brollUseCommons').checked=s.use_commons!==false;$('#brollUseWeb').checked=s.use_web!==false;
  libraryFolders=[...s.library_folders];renderLibrary();
  const sources=[];if(s.use_library&&s.library_folders.length)sources.push(`My footage (${s.library_folders.length} folder${s.library_folders.length===1?'':'s'})`);
  if(s.use_pexels&&s.pexels_key)sources.push('Pexels');if(s.use_pixabay&&s.pixabay_key)sources.push('Pixabay');
  if(s.use_commons!==false)sources.push('Commons');if(s.use_web!==false)sources.push('Web + YouTube');
  $('#sourceSummary').textContent=sources.length?sources.join(' + '):'None yet — open B-roll settings';
}
async function loadBrollSettings(){try{showSettings(await api('/api/broll/settings'))}catch(e){$('#sourceSummary').textContent=window.storylensError(e)}}
$('#openBrollSettings').onclick=()=>{$('#settingsError').textContent='';$('#brollSettings').showModal()};
$('#addLibrary').onclick=async()=>{try{const r=await api('/api/pick?kind=folder');if(r.path&&!libraryFolders.includes(r.path)){libraryFolders.push(r.path);renderLibrary()}}catch(e){$('#settingsError').textContent=window.storylensError(e)}};
$('#saveBrollSettings').onclick=async()=>{
  try{const s=await api('/api/broll/settings',{method:'POST',body:JSON.stringify({pexels_key:$('#pexelsKey').value,
      pixabay_key:$('#pixabayKey').value,use_pexels:$('#usePexels').checked,use_pixabay:$('#usePixabay').checked,
      use_library:$('#useLibrary').checked,library_folders:libraryFolders,
      use_commons:$('#brollUseCommons').checked,use_web:$('#brollUseWeb').checked,image_fallback:false})});
    $('#pexelsKey').value='';$('#pixabayKey').value='';showSettings(s);$('#brollSettings').close();
  }catch(e){$('#settingsError').textContent=window.storylensError(e)}
};
// ---- Quality check ----
function syncResultBar(){
  const ready=Boolean(lastResult&&lastResultMode===mode),bar=$('#result');
  bar.classList.remove('hidden');bar.classList.toggle('is-pending',!ready);
  $('#openResult').disabled=!ready||!lastResult.page;$('#openFolder').disabled=!ready||!lastResult.folder;
  if(ready){
    const made=lastResult.xml_files?.length||0;
    $('#resultMeta').textContent=mode==='shorts'?`${made} shorts · MP4s + editable sequences`:made?`${made} editable timeline${made===1?'':'s'}`:'Open your finished result';
    showQuality(lastResult);
  }else{
    bar.classList.remove('needs-review');$('#result .check').textContent='·';
    $('#resultTitle').textContent='Your result will appear here';$('#resultMeta').textContent='View and export after processing.';
    $('#qualityMeta').textContent='';window.storylensEditors?.render($('#editorExports'),null);
  }
}
window.storylensPendingResult=()=>{lastResult=null;lastResultMode=null;syncResultBar()};
document.addEventListener('storylens-editors-ready',syncResultBar);
function showQuality(result){
  const q=result.quality_summary,box=$('#qualityMeta');
  const v=result.visuals_summary;
  if(v?.review_options){
    $('#resultTitle').textContent='Choose your Smart Visuals';
    $('#resultMeta').textContent=`${v.options} downloaded choices · ${v.complete_subjects} of ${v.subjects} subjects have five options`;
    $('#result').classList.toggle('needs-review',true);$('#result .check').textContent='↗';
    box.className='quality-meta';box.textContent='Open View Result and save your selections. Only selected visuals are sent to your editor.';
    window.storylensEditors?.render($('#editorExports'),result);
    return;
  }
  const b=result.broll_summary;
  if(b?.review_options){
    $('#resultTitle').textContent='Choose your B-roll';
    $('#resultMeta').textContent=`${b.options} playable video options · ${b.moments} keyword moments requested`;
    $('#result').classList.toggle('needs-review',true);$('#result .check').textContent='↗';
    box.className='quality-meta';box.textContent=result.broll_preview_notice||'Review the choices or send them to your editor. The timeline is a suggestion; you decide what to keep.';
    window.storylensEditors?.render($('#editorExports'),b.options?result:null);
    return;
  }
  $('#resultTitle').textContent=b?(b.filled?'Review your B-roll':'No relevant B-roll found'):'Your timeline is ready';
  $('#result').classList.toggle('needs-review',Boolean(b&&b.filled<b.moments));
  $('#result .check').textContent=b&&b.filled<b.moments?'!':'✓';
  if(b){
    $('#resultMeta').textContent=`${b.filled} approved video cutaway${b.filled===1?'':'s'} · ${b.moments-b.filled} moment${b.moments-b.filled===1?'':'s'} left empty`;
    if(!b.filled){
      window.storylensEditors?.render($('#editorExports'),null);box.className='quality-meta warn';
      box.textContent='No retrieved video passed the context check. Your original source and audio are kept. Review the missing moments or try another footage source.';
      return;
    }
  }
  if(mode==='thumbnail'){$('#resultTitle').textContent='Your images are ready';const d=result.thumbnail_design;$('#resultMeta').textContent=(result.images?.length?`${result.images.length} image${result.images.length===1?'':' options'}`:'Open your saved image result')+(d?` · ${d.width} × ${d.height}`:'');}
  window.storylensEditors?.render($('#editorExports'),result,{disabledReason:mode==='thumbnail'&&!result.xml_files?.length?'These results are image files. Use View Result or Open Folder to choose an image.':''});
  if(b&&b.filled<b.moments){
    box.className='quality-meta warn';box.textContent='This preview is incomplete. Some requested cutaways have no approved video yet. Your source and original audio are kept.';return;
  }
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
    box.textContent=s.ready?`Ready · ${s.engine||s.gpu}`:(s.checks.find(c=>!c.ok)||{text:'Not set up yet'}).text;
  }catch(e){box.classList.add('warn');box.textContent=window.storylensError(e)}
}
// ---- Sound design ----
async function loadSoundSettings(){try{const s=await api('/api/sound/settings');
  $('#musicFolder').textContent=s.music_folder;$('#sfxFolder').textContent=s.sfx_folder}catch(e){$('#musicFolder').textContent=window.storylensError(e)}}
async function changeSoundFolder(key){try{const r=await api('/api/pick?kind=folder');if(!r.path)return;
  await api('/api/sound/settings',{method:'POST',body:JSON.stringify({[key]:r.path})});loadSoundSettings()}catch(e){window.storylensShowError(e)}}
$('#pickMusic').onclick=()=>changeSoundFolder('music_folder');
// ---- AI Images / AI Video (separate tools; the style list and GPU check are shared) ----
let aigenStyles=[],aigenVideoStudioSupported=null;
function aiPayload(tool){return {[tool+'_style']:$('#'+tool+'Style').value||'cinematic',[tool+'_custom_style']:$('#'+tool+'Custom').value,
  [tool+'_count']:$('#'+tool+'Count').value,[tool+'_options']:$('#'+tool+'Options').value,[tool+'_aspect']:$('#'+tool+'Aspect').value,
  [tool+'_brain']:$('#'+tool+'Brain').value,[tool+'_check']:$('#'+tool+'Check').checked}}
function videoStudioPayload(){return {aivideo_video_method:$('#aivideoMethod').value,aivideo_reference:$('#aivideoReference').value.trim(),aivideo_motion_style:$('#aivideoMotionStyle').value,aivideo_quality:$('#aivideoQuality').value}}
function updateVideoMethod(){
  const method=$('#aivideoMethod').value,motion=method==='motion';
  $('#aivideoReferenceField').classList.toggle('hidden',method!=='reference');
  $('#aivideoMotionField').classList.toggle('hidden',!motion);
  for(const id of ['aivideoStyle','aivideoCount','aivideoOptions','aivideoCustom','aivideoNewName','aivideoFromText'])$('#'+id).closest('label').classList.toggle('hidden',motion);
  $('.ai-save-style[data-tool="aivideo"]').closest('label').classList.toggle('hidden',motion);
  for(const option of $('#aivideoQuality').options)option.textContent=motion?(option.value==='preview'?'Quick preview · 360p':'Full quality'):(option.value==='preview'?'Quick preview · 2-second clips':'Full quality · 5-second clips');
  $('#aivideoMethodNote').textContent=method==='reference'?'Local Vision measures the reference and guides new scenes. Public YouTube links use a 10-second sample; matching is approximate.':motion?'GSAP / Hyperframes renders every script line; orbital scenes use Three.js. Exported 3D is a video layer.':'Qwen plans the scenes; Z-Image and Wan generate the clips locally.';
}
$('#aivideoMethod').addEventListener('change',()=>{updateVideoMethod();loadAigen('aivideo')});updateVideoMethod();
{const option=document.createElement('option');option.value='1';option.textContent='Exactly 1 · short test';$('#aivideoCount').append(option)}
function showStyles(list){aigenStyles=list;['thumbnail','aivideo'].forEach(tool=>{const select=$('#'+tool+'Style');
  let was=select.dataset.requestedStyle||select.value;delete select.dataset.requestedStyle;try{was=was||localStorage.getItem('hinglish.'+tool+'Style')}catch(_){}
  select.innerHTML='';list.forEach(s=>{const o=document.createElement('option');o.value=s.id;o.textContent=(s.own?'★ ':'')+s.name;select.append(o)});
  if(was&&list.some(s=>s.id===was))select.value=was})}
async function loadAigen(tool){const box=$('.'+tool+'-field .ai-status');box.className='eye-status ai-status';box.textContent='Checking the GPU and models…';
  try{const s=await api('/api/aigen/status');showStyles(s.styles);
    if(tool==='aivideo')aigenVideoStudioSupported=Array.isArray(s.video_studio?.methods)&&['generative','reference','motion'].every(id=>s.video_studio.methods.some(method=>method.id===id));
    if(tool==='aivideo'&&$('#aivideoMethod').value==='motion'){const ready=s.video_studio?.motion_runtime_installed;box.classList.add(ready?'ok':'warn');box.textContent=ready?'Motion runtime ready · Qwen · GSAP · Hyperframes · Three.js':'Restore the local motion runtime to use Motion / 3D.';return}
    const need=tool==='thumbnail'?s.image_model:s.video_model;const setup=tool==='thumbnail'?'Setup AI Images (RTX).bat':'Setup AI Video (RTX).bat';
    const ok=s.cuda&&need;box.classList.add(ok?'ok':'warn');
    box.textContent=!s.cuda?(s.problem||'Not set up yet: run "'+setup+'" once.'):!need?'The model is not downloaded yet: run "'+setup+'" once.':
      `Ready on ${s.gpu} (${s.vram_gb} GB, ${s.mode} mode)`+(tool==='aivideo'&&!s.image_model?' · first frames need the image model set up too':'');
  }catch(e){box.classList.add('warn');box.textContent=window.storylensError(e)}}
['thumbnail','aivideo'].forEach(tool=>$('#'+tool+'Style').addEventListener('change',()=>{try{localStorage.setItem('hinglish.'+tool+'Style',$('#'+tool+'Style').value)}catch(_){}}));
$$('.ai-save-style').forEach(b=>b.onclick=async()=>{const tool=b.dataset.tool;const name=$('#'+tool+'NewName').value.trim(),prompt=$('#'+tool+'Custom').value.trim();
  if(!name||!prompt){alert('Type the style words in "One-off style prompt" and a name, then save.');return}
  try{const own=aigenStyles.filter(s=>s.own).map(s=>({name:s.name,prompt:s.prompt})).filter(s=>s.name.toLowerCase()!==name.toLowerCase());
    const r=await api('/api/aigen/styles',{method:'POST',body:JSON.stringify({styles:[...own,{name,prompt}]})});
    showStyles(r.styles);$('#'+tool+'Style').value='my:'+name;$('#'+tool+'Custom').value='';$('#'+tool+'NewName').value='';
  }catch(e){window.storylensShowError(e)}});
// ---- Motion Graphics: themes + your style cards (style memory) ----
function showMotion(r){const select=$('#motionStyle');let was=select.dataset.requestedStyle||select.value;delete select.dataset.requestedStyle;try{was=was||localStorage.getItem('hinglish.motionStyle')}catch(_){}
  select.innerHTML='';const groups={};r.choices.forEach(c=>{const o=document.createElement('option');o.value=c.value;o.textContent=c.name;
    if(c.group){if(!groups[c.group]){const g=document.createElement('optgroup');g.label=c.group;select.append(g);groups[c.group]=g}groups[c.group].append(o)}else select.append(o)});
  if(was&&r.choices.some(c=>c.value===was))select.value=was;
  else if(r.choices.some(c=>c.value==='theme:studio'))select.value='theme:studio';
  updateMotionEngine();
  const box=$('#motionCards');box.innerHTML='';
  if(!r.cards.length){box.innerHTML='<small>No style cards yet. The four built-in themes are ready to use.</small>';return}
  r.cards.filter(c=>!c.animation).forEach(c=>{const row=document.createElement('div');row.className='motion-card';
    const sw=document.createElement('span');sw.className='sw';Object.values(c.colors).forEach(v=>{const i=document.createElement('i');i.style.background=v||'#000';sw.append(i)});
    const name=document.createElement('b');name.textContent=c.name;name.title=c.summary||'';
    const badge=document.createElement('span');badge.className='badge'+(c.status==='approved'?' ok':'');badge.textContent=c.status==='approved'?'approved':'waiting for approval';
    row.append(sw,name,badge);
    if(c.animations?.length){const settings=document.createElement('span');settings.className='muted';settings.textContent=c.animations.map(a=>a.name).join(' · ');row.append(settings)}
    [[c.status==='approved'?'Unapprove':'Approve',c.status==='approved'?'unapprove':'approve'],['Rename','rename'],['Delete','delete']].forEach(([label,action])=>{
      const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=async()=>{const body={action,id:c.id};
        if(action==='rename'){const n=prompt('New name',c.name);if(!n)return;body.name=n}
        if(action==='delete'&&!confirm('Delete the style "'+c.name+'"?'))return;
        try{showMotion(await api('/api/motion/styles',{method:'POST',body:JSON.stringify(body)}))}catch(e){window.storylensShowError(e)}};row.append(b)});
    box.append(row)})}
async function loadMotionStyles(){try{showMotion(await api('/api/motion/styles'))}catch(e){$('#motionCards').textContent=window.storylensError(e)}}
$('#motionStyle').addEventListener('change',()=>{try{localStorage.setItem('hinglish.motionStyle',$('#motionStyle').value)}catch(_){}});
const nativeMotionStyles=new Set(['theme:studio','theme:elements','theme:gsap','theme:product','theme:explainer']);
function updateMotionEngine(){const engine=$('#motionEngine').value;$('#motionEngineNote').textContent='Qwen · '+({'remotion':'Remotion · MP4','motion-canvas':'Motion Canvas · MP4','hyperframes':'Hyperframes · GSAP'}[engine]);for(const o of $('#motionStyle').options)o.disabled=engine!=='hyperframes'&&!nativeMotionStyles.has(o.value);if($('#motionStyle').selectedOptions[0]?.disabled)$('#motionStyle').value='theme:studio';const overlay=$('#motionMode').querySelector('option[value="overlay"]');overlay.disabled=engine!=='hyperframes';if(overlay.disabled&&$('#motionMode').value==='overlay')$('#motionMode').value='full';}
try{$('#motionEngine').value=localStorage.getItem('storylens.motionEngine')||'remotion'}catch(_){}
$('#motionEngine').addEventListener('change',()=>{try{localStorage.setItem('storylens.motionEngine',$('#motionEngine').value)}catch(_){}updateMotionEngine()});
updateMotionEngine();
async function learnMotion(kind){try{const r=await api('/api/pick?kind='+kind);if(!r.path)return;
  const paths=r.path.split(/\r?\n/).filter(Boolean);$('#motionCards').innerHTML='<small>Looking at your references (the vision model reads the look; about a minute)…</small>';
  const out=await api('/api/motion/styles',{method:'POST',body:JSON.stringify({action:'learn',paths,name:$('#motionLearnName').value})});
  $('#motionLearnName').value='';showMotion(out);
  alert('Style card made. Check its colours and press Approve to use it.')}catch(e){window.storylensShowError(e);loadMotionStyles()}}
$('#motionLearnFiles').onclick=()=>learnMotion('references');
$('#motionLearnFolder').onclick=()=>learnMotion('folder');
// Keep the saved look. Previously saved channel/title guidance remains on disk.
['shortsLook'].forEach(id=>{
  try{const saved=localStorage.getItem('hinglish.'+id);if(saved!==null)$('#'+id).value=saved}catch(_){}
  $('#'+id).addEventListener('change',()=>{try{localStorage.setItem('hinglish.'+id,$('#'+id).value)}catch(_){}})});
$('#pickSfx').onclick=()=>changeSoundFolder('sfx_folder');

$('#pickXml').onclick=async()=>{try{const r=await api('/api/pick?kind=xml');if(r.path){sourcePaths=[];$('#inputPath').value=r.path;
  $('#selectedFiles').classList.add('hidden');if(inResolve)$('#useResolve').checked=false}}catch(e){window.storylensShowError(e)}};

$('#run').onclick=async()=>{
  try{
    if(mode==='captions'){window.storylensCaptionGenerator?.submit();return;}
    let brollOrientation=null;
    if(mode==='broll'){brollOrientation=await window.storylensBrollFormat.ask();if(!brollOrientation)return;}
    window.storylensClearError?.();
    if(mode==='aivideo'&&$('#aivideoMethod').value==='reference'&&!$('#aivideoReference').value.trim())throw Error('AI Video reference missing: choose an existing local video or a public YouTube link.');
    if(mode==='aivideo'){
      if(aigenVideoStudioSupported===null)await loadAigen('aivideo');
      if(aigenVideoStudioSupported===false)throw Error('AI Video service outdated: keep your script, let current jobs finish, then restart Storylens to enable these generation methods.');
      if(aigenVideoStudioSupported!==true)throw Error('The local AI Video service could not be checked. Your script is kept. Reopen Storylens and try again.');
    }
    if(mode==='shorts'){
      if(!$('#shortsNumber').checkValidity())throw Object.assign(Error('Enter a whole number of shorts from 1 to 40.'),{code:'invalid_shorts_count'});
      if(!$('#shortsDuration').checkValidity())throw Object.assign(Error('Enter a duration from 10 to 120 seconds per short.'),{code:'invalid_shorts_duration'});
    }
    if(mode==='visuals'){
      const health=await api('/api/health');
      if(!health.capabilities?.includes('visuals_website_options_v1'))throw Object.assign(new Error('Your video and settings are kept. Let current jobs finish, then restart Storylens to enable web image options.'),{code:'visuals_web_service_outdated'});
    }
    if(mode==='broll'&&$('#brollScript').value.trim()){
      const health=await api('/api/health');
      if(!health.capabilities?.includes('broll_reference_script_v1'))throw Object.assign(new Error('Your script is kept. Let the current edit finish, then restart Storylens once to enable B-roll script context.'),{code:'broll_script_service_outdated'});
    }
    const payload={mode,profile:window.creatorProfile?.value||'general',target_minutes:$('#gamingMinutes').value,memes:$('#gamingMemes').checked,generate_background:$('#thumbnailGenerate').checked,source_paths:sourcePaths,input_path:sourcePaths.length?'':$('#inputPath').value,
      script:mode==='broll'?$('#brollScript').value:['captions','visuals','sound','shorts'].includes(mode)?$('#captionReference').value:$('#script').value,
      caption_style:captionStyle,caption_content:mode==='captions'?$('#captionContent').value:'speech',format:mode==='broll'?(brollOrientation==='vertical'?'instagram_vertical':'youtube_horizontal'):$('#format').value,density:'medium',
      broll_black_background:false,broll_count:0,broll_brief:'',
      broll_review_options:true,broll_orientation:brollOrientation,broll_search_method:$('#brollSearchMethod').value,broll_options_per_moment:window.storylensBrollFormat.limit(brollOrientation,$('#brollOptionsPerMoment').value),
      use_resolve_timeline:TIMELINE_MODES.includes(mode)&&inResolve&&$('#useResolve').checked,
      eye_reach:$('#eyeReach').value,eye_size:$('#eyeSize').value,eye_look_away:$('#eyeLookAway').checked,
      sound_style:$('#soundStyle').value,sound_density:$('#soundDensity').value,sound_music:$('#soundMusic').checked,
      sound_effects:$('#soundEffects').checked,sound_transitions:$('#soundTransitions').checked,sound_layered:$('#soundLayered').checked,
      sound_remove_music:$('#soundRemoveMusic').checked,sound_content_form:$('#soundContentForm').value,
      visuals_density:$('#visualsDensity').value,visuals_brain:$('#visualsBrain').value,visuals_popups:$('#visualsPopups').checked,visuals_web:true,visuals_check:false,visuals_search_method:'website',visuals_review_options:true,visuals_options_per_moment:$('#format').value==='youtube_horizontal'?2:5,
      visuals_presentation:$('#visualsPresentation').value,visuals_black_background:false,
      zoom_style:$('#zoomStyle').value,zoom_strength:$('#zoomStrength').value,zoom_frequency:$('#zoomFrequency').value,
      zoom_face:$('#zoomFace').checked,zoom_jump_cuts:$('#zoomJumpCuts').checked,
      zoom_sounds:$('#zoomSounds').checked,zoom_overlays:$('#zoomOverlays').checked,
      shorts_count:$('#shortsNumber').value,
      shorts_look:$('#shortsLook').value,shorts_pieces:$('#shortsPieces').value,shorts_brain:$('#shortsBrain').value,
      shorts_min:Number($('#shortsDuration').value)-5,shorts_max:Number($('#shortsDuration').value),
      shorts_captions:$('#shortsCaptions').checked,
      ...aiPayload('aivideo'),...videoStudioPayload(),aivideo_from_text:$('#aivideoFromText').checked,
      motion_engine:$('#motionEngine').value||'remotion',motion_style:$('#motionStyle').value||'theme:studio',motion_count:$('#motionCount').value,motion_mode:$('#motionMode').value,
      motion_coverage:$('#motionCoverage').value,motion_assets:$('#motionAssets').value,motion_aspect:$('#motionAspect').value,motion_brain:$('#motionBrain').value,motion_quality:$('#motionQuality').value,
      device:$('#device').value,pacing:$('#pacing').value,preview:true};
    if(mode==='thumbnail'){Object.assign(payload,window.storylensThumbnailRequest());const health=await api('/api/health');if(!health.capabilities?.includes('thumbnail_studio_v1'))throw Object.assign(Error('Your image settings are saved. Restart Storylens after the current job finishes to enable the merged Thumbnail tool.'),{code:'thumbnail_engine_outdated'});}
    const job=await api('/api/jobs',{method:'POST',body:JSON.stringify(payload)});
    jobId=job.id;lastResult=null;$('#run').disabled=true;syncResultBar();
    $('#progress').classList.remove('hidden');lostPolls=0;poll();
  }catch(e){window.storylensShowError(e)}
};

let lostPolls=0;
function engineProblem(e){
  // Network error: the local engine window closed or is restarting. Keep trying for about a minute.
  if(e.code==='local_connection'){
    lostPolls++;
    if(lostPolls<=60){
      $('#statusText').textContent='Reconnecting to the local engine…';
      $('#stage').textContent=`The engine is not answering (${lostPolls}s). Keep the Storylens window open.`;
      timer=setTimeout(poll,1000);return true;
    }
    return 'The local engine stopped. Double-click Run Storylens.bat in the DEV folder, then click the orange button again.';
  }
  // A different/restarted engine does not know this page or this job.
  if(['not_found','connection_required'].includes(e.code)||/Not connected|Job not found/.test(e.message))
    return 'The local engine restarted, so this run stopped. Press F5 to reload this page, then click the orange button again.';
  return null;
}

async function poll(){
  try{
    const job=await api(`/api/jobs/${jobId}`);lostPolls=0;
    const analysingStream=job.mode==='gaming'&&job.status==='running';
    $('#progress').classList.toggle('has-error',job.status==='failed');
    $('#percent').textContent=job.status==='failed'?'Stopped':analysingStream?'Processing':`${job.progress}%`;
    $('#bar').style.width=analysingStream?'100%':`${job.progress}%`;
    $('#bar').style.opacity=analysingStream?'.35':'1';$('#stage').textContent=job.stage;
    $('#statusText').textContent=job.status==='running'?'Editing locally':job.status==='failed'?'Could not finish':'Preparing';
    $('#logs').textContent=job.logs.join('\n');$('#logs').scrollTop=$('#logs').scrollHeight;
    if(job.status==='complete'){
      lastResult=job.result;lastResultMode=job.mode;$('#run').disabled=false;$('#progress').classList.add('hidden');
      const made=job.result.xml_files.length;
      syncResultBar();return;
    }
    if(job.status==='failed')throw window.storylensJobError(job);
    timer=setTimeout(poll,900);
  }catch(e){
    const problem=engineProblem(e);
    if(problem===true)return;
    $('#run').disabled=false;$('#progress').classList.add('has-error');$('#percent').textContent='Stopped';$('#statusText').textContent='Needs attention';$('#stage').textContent=problem||window.storylensError(e);
  }
}

async function open(path){if(path)await api('/api/open',{method:'POST',body:JSON.stringify({path})})}
$('#openResult').onclick=()=>open(lastResult?.page);$('#openFolder').onclick=()=>open(lastResult?.folder);
// The chat dispatches jobs on the server. This adapter only reveals their existing tool UI.
window.editorAssist={
  useSources(paths){if(this.busy()||window.assistantBusy)throw Error('Finish the current edit before choosing another source.');sourcePaths=paths;$('#inputPath').value=paths.join(' | ');$('#inputHelp').textContent='Local video selected. Choose a tool to continue.';},
  useTimeline(path){if(this.busy()||window.assistantBusy)throw Error('Finish the current edit before choosing another timeline.');sourcePaths=[];$('#inputPath').value=path;$('#inputHelp').textContent='Local timeline selected. Smart Clean and Smart Edit will return an editable copy.';},
  reset(){clearTimeout(timer);jobId=null;lastResult=null;lastResultMode=null;sourcePaths=[];setMode('clean');$('#progress').classList.add('hidden');syncResultBar();$('#inputPath').value='';$('#run').disabled=false},
  busy(){return !!jobId&&$('#run').disabled},
  select(payload){
    setMode(payload.mode);
    if(payload.target_minutes)$('#gamingMinutes').value=payload.target_minutes;
    if(payload.generate_background!==undefined)$('#thumbnailGenerate').checked=payload.generate_background;
    if(payload.memes!==undefined)$('#gamingMemes').checked=payload.memes;
    if(payload.caption_style&&Array.from($$('.caption-card')).some(c=>c.dataset.style===payload.caption_style)){captionStyle=payload.caption_style;$$('.caption-card').forEach(c=>c.classList.toggle('active',c.dataset.style===captionStyle))}
    const fields={format:'format',device:'device',caption_content:'captionContent',pacing:'pacing',density:'density',zoom_style:'zoomStyle',zoom_strength:'zoomStrength',sound_style:'soundStyle',shorts_look:'shortsLook',motion_mode:'motionMode',motion_assets:'motionAssets',motion_engine:'motionEngine'};
    Object.entries(fields).forEach(([k,id])=>{if(payload[k]!==undefined&&$('#'+id))$('#'+id).value=payload[k]});
    if(payload.mode==='motion')updateMotionEngine();
    updateCaptionReference();
    if(document.documentElement.dataset.rtxOnly==='true')$('#device').value='cuda';
    if(payload.shorts_count&&/^\d+$/.test(payload.shorts_count))$('#shortsNumber').value=payload.shorts_count;
    if(payload.shorts_max)$('#shortsDuration').value=payload.shorts_max;
    if(payload.shorts_captions!==undefined)$('#shortsCaptions').checked=payload.shorts_captions;
    for(const [key,id] of [['zoom_sounds','zoomSounds'],['zoom_overlays','zoomOverlays']])if(payload[key]!==undefined)$('#'+id).checked=payload[key];
    sourcePaths=[...(payload.source_paths||[])];$('#inputPath').value=payload.source_paths?.length?`${payload.source_paths.length} chat attachment(s)`:payload.input_path||'';
    $('#inputHelp').textContent=payload.mode==='broll'?'':'The assistant is running this tool using your chat attachments.';
    if(payload.script){if(payload.mode==='captions')window.storylensCaptionGenerator?.setScript(payload.script);else if(payload.mode==='broll')$('#brollScript').value=payload.script;else if(['visuals','sound','shorts'].includes(payload.mode))$('#captionReference').value=payload.script;else $('#script').value=payload.script;}
  },
  done(result){if(!result)return;lastResult=result;lastResultMode=mode;$('#run').disabled=false;$('#progress').classList.add('hidden');syncResultBar()},
  watch(job){if(!job)return;clearTimeout(timer);jobId=job.id;lastResult=null;lostPolls=0;$('#run').disabled=true;syncResultBar();$('#progress').classList.remove('hidden');poll()}
};

$('#toolSearch').oninput=()=>{const q=$('#toolSearch').value.trim().toLowerCase();$$('.mode').forEach(b=>b.hidden=!b.textContent.toLowerCase().includes(q));};
const initialTool=new URLSearchParams(location.search).get('tool');
if(initialTool&&document.querySelector('.mode[data-mode="'+CSS.escape(initialTool)+'"]')){
 setMode(initialTool);document.body.classList.add('tools-visible');
}
window.addEventListener('beforeunload',()=>clearInterval(nativeConnectionTimer));
