// Direct editing augments the existing template library without losing edits.
const studioOriginalDraw=draw,studioOriginalApply=applyStyle;
if(project.script_preview){
  const changeScript=document.createElement('a');changeScript.className='studio-download';changeScript.textContent=project.auto_caption_2?'Change script / generation method':'Change script';changeScript.href='/?tool=captions';
  changeScript.onclick=()=>{try{localStorage.setItem('storylens-auto-caption-2-v1',JSON.stringify({text:currentTexts().join('\n'),duration:studioDuration,format:currentFormat==='source'?(project.width<project.height?'instagram_vertical':project.width===project.height?'square':'youtube_horizontal'):currentFormat,style:project.auto_caption_2?.reference_id||currentStyle,method:'hyperframes',pasted:true}))}catch{}};
  document.querySelector('#save').before(changeScript);
}
const studioDuration=Number(project.media?.duration)||Math.max(...cues.map(c=>c.end),1);
// Keep the pattern's source independent of every subsequent wording edit.
cues.forEach((q,index)=>{q.template_source ||= project.cues?.[index]?.template_source||q.words.map(w=>w.text).join(' ');q.template_slot ??= project.cues?.[index]?.template_slot??index});
const studioKey='storylens-caption-draft:'+project.project_path;
let selectedCue=0,studioDirty=false,studioSaving=false,studioBridge=null;
let demoBackground=project.demo_background||(/(?:white|light|paper)/.test(project.source_relative||'')?'white':'black');
let previewBackground=null;
try{const saved=localStorage.getItem(studioKey+':preview-background');if(['black','white'].includes(saved))previewBackground=saved}catch{}
let cueLayouts=cues.map((_,i)=>({...{x:.5,y:project.position??.7,size:project.size??1},...(project.cue_layouts?.[i]||{})}));
let visibility=project.word_visibility||(project.caption_content==='lyrics'?'spoken':'phrase');
// Source emphasis is a saved slot, so changing wording cannot move the hero.
for(const name of ['typographyThreeAnchor','typographyFiveAnchor']){
 const previous=name==='typographyThreeAnchor'?typographyThreeAnchor:typographyFiveAnchor;
 const stable=words=>{const q=cues.find(q=>q.start<=video.currentTime&&video.currentTime<q.end),original=q?.template_source?.split(/\s+/);if(original&&original.join(' ')!==words.join(' '))return Math.min(words.length-1,Math.floor((previous(original)+.5)*words.length/original.length));return previous(words)};
 if(name==='typographyThreeAnchor')typographyThreeAnchor=stable;else typographyFiveAnchor=stable;
}
const studioOriginalPreviewMotion=previewMotion;
previewMotion=function(t,q,now){return studioOriginalPreviewMotion(t,q,now,visibility==='phrase')};
const clampStudio=(value,low,high)=>Math.min(high,Math.max(low,value));
const roundTime=value=>Math.round(value*10000)/10000;
const studioStatus=$('#status'),studioSave=$('#save');
// Upgrade saved reports as well as newly generated studios.
$('header b').textContent='English Caption Studio';
$('header>div').classList.add('studio-brand');
$('header small').textContent=(project.media?.path||project.source_relative||$('header small').textContent).split(/[\\/]/).pop();
studioStatus.parentElement.classList.add('studio-header-actions');
studioSave.textContent='Save & export MP4';
studioSave.insertAdjacentHTML('beforebegin','<a id="downloadVideo" class="studio-download disabled" download href="captioned-preview.mp4">Download MP4</a> ');
const downloadVideo=$('#downloadVideo');
const backgroundCircles=document.createElement('span');backgroundCircles.className='background-circles';
backgroundCircles.setAttribute('role','group');backgroundCircles.setAttribute('aria-label','Preview background');
backgroundCircles.innerHTML='<button type="button" data-preview-background="black" aria-label="Black background" title="Black preview background"></button><button type="button" data-preview-background="white" aria-label="White background" title="White preview background"></button>';
$('.transport').append(backgroundCircles);
function paintStudioBackground(){
  if(project.demo&&['caption_2','caption_4'].includes(currentStyle))demoBackground='black';
  const color=project.demo?demoBackground:previewBackground;
  stage.style.background=color==='white'?'#ffffff':'#000000';video.style.opacity=color?'0':'';
  backgroundCircles.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.previewBackground===color)));
}
backgroundCircles.onclick=event=>{
  const button=event.target.closest('[data-preview-background]');if(!button||studioSaving)return;
  const color=button.dataset.previewBackground;
  if(project.demo){demoBackground=color;dirtyStudio()}
  else{previewBackground=previewBackground===color?null:color;try{if(previewBackground)localStorage.setItem(studioKey+':preview-background',previewBackground);else localStorage.removeItem(studioKey+':preview-background')}catch{}}
  draw();
};
$('#size').min='8';$('#size').max='400';$('#size').step='1';
$('#position').min='0';$('#position').max='100';$('#position').step='.1';
$('#textPane .text-controls').insertAdjacentHTML('afterbegin',`<p class="studio-hint">Tap a caption to select it. Drag it on the video; pull its corner or pinch to resize. Resize applies to every caption group. Dragging position applies to the selected group.</p><span id="selectedCaptionLabel" class="studio-selected"></span><label class="visibility-control">Word display<select id="wordVisibility"><option value="styled_spoken">Spoken words · keep typography</option><option value="spoken">Single spoken word (simple text)</option><option value="phrase">Original template animation</option></select></label>`);
$('#textPane .text-controls').insertAdjacentHTML('beforeend','<div class="timing-fields"><label>Caption starts (s)<input id="cueStart" type="number" step="0.01" min="0"></label><label>Caption ends (s)<input id="cueEnd" type="number" step="0.01" min="0"></label></div><label>Size (%)<input id="sizeNumber" type="number" min="8" max="400" step="1"></label>');
$('#textPane .text-controls').insertAdjacentHTML('beforeend','<div><button id="restoreSaved" type="button">Restore saved</button> <button id="undoRestore" class="hidden" type="button">Undo restore</button></div>');
$('#wordVisibility').value=visibility;
stage.insertAdjacentHTML('beforeend','<div id="captionSelection" class="caption-selection hidden"><button id="resizeCaption" aria-label="Resize selected caption" title="Drag to resize; arrow keys also work"></button></div>');
const selectionBox=$('#captionSelection');
const captionPositionLayer=document.createElement('div');
captionPositionLayer.id='captionPositionLayer';
caption.before(captionPositionLayer);captionPositionLayer.appendChild(caption);
// Preserve each Typography 1 word's source index, including repeated words
// and decorative echoes, so timing hides glyphs without rebuilding the layout.
typeLine=function(kind,text,preserve=false,startIndex=0){return text?`<span class="t1-line ${kind}" data-word-start="${startIndex}">${esc(preserve?text:text.toUpperCase())}</span>`:''};
sandwichMarkup=function(words,kind='',echo=false){
  const [top,hero,bottom]=sandwichWords(words),a=top?top.split(/\s+/).length:0,b=hero?hero.split(/\s+/).length:0;
  return (echo?typeLine('t1-echo',hero.split(/\s+/).slice(-1)[0],false,a+b-1):'')+typeLine('t1-small',top,false,0)+typeLine(`t1-giant ${kind}`,hero,false,a)+typeLine('t1-small',bottom,false,a+b);
};
typographyOneMarkup=function(words,q){
  const variant=Math.round(q.start*30)%8;if(!words.length)return '';
  if(variant===0){const cut=Math.max(0,words.length-3),setup=words.slice(0,cut).join(' '),main=words.slice(cut),upper=main.length>=3?main.slice(0,-1).join(' '):main[0],lower=main.length>=3?main.slice(-1)[0]:main.slice(1).join(' ');return typeLine('t1-echo',lower||upper,false,lower?words.length-1:cut)+typeLine('t1-small',setup,false,0)+typeLine('t1-giant',upper,false,cut)+typeLine('t1-big',lower,false,main.length>=3?words.length-1:cut+1)}
  if(variant===1)return sandwichMarkup(words,'t1-bar');
  if(variant===2)return sandwichMarkup(words,'t1-outline');
  if(variant===3)return sandwichMarkup(words,'t1-bar');
  if(variant===4)return sandwichMarkup(words);
  if(variant===5){if(words.length===1)return typeLine('t1-giant t1-bar',words[0]);const count=Math.min(2,Math.max(1,words.length-2)),script=words.slice(0,count).join(' '),rest=words.slice(count),focus=importantIndex(rest);return typeLine('t1-script',script,true,0)+typeLine('t1-small',rest.slice(0,focus).join(' '),false,count)+typeLine('t1-giant t1-bar',rest[focus],false,count+focus)+typeLine('t1-small',rest.slice(focus+1).join(' '),false,count+focus+1)}
  if(variant===6)return sandwichMarkup(words,'',true);
  return sandwichMarkup(words);
};
applyTypographyOneColors=function(words,cueIndex){
  caption.querySelectorAll('.t1-line').forEach(line=>{
    const outline=line.classList.contains('t1-outline')||line.classList.contains('t1-echo'),start=Number(line.dataset.wordStart)||0;
    line.innerHTML=line.textContent.trim().split(/\s+/).map((token,offset)=>{
      const index=start+offset,color=wordColors[cueIndex]?.[index],style=color?(outline?`-webkit-text-stroke-color:${color};color:transparent`:`color:${color}`):'';
      return `<span data-word="${index}"${style?` style="${style}"`:''}>${esc(token)}</span>`;
    }).join(' ');
  });
};
const captionTrack=$('.track.captions');
captionTrack.insertAdjacentHTML('afterend','<div class="track words" aria-label="Word timing track"></div>');
const wordTrack=$('.track.words');
$('.timeline').insertAdjacentHTML('beforeend','<div class="timing-help">Drag a block to move it. Pull either edge to change its duration. Word handles let you correct exact sync.</div><div class="timeline-ruler" aria-label="Seek video timeline"></div>');
const ruler=$('.timeline-ruler');
for(let t=0;t<=studioDuration;t+=Math.max(1,Math.ceil(studioDuration/6))){const tick=document.createElement('span');tick.style.left=t/studioDuration*100+'%';tick.textContent=t.toFixed(0)+'s';ruler.appendChild(tick)}
$('.track.audio').insertAdjacentHTML('beforeend','<div class="timeline-playhead"></div>');
const timeline=$('.timeline'),timelineToolbar=document.createElement('div');
timelineToolbar.className='timeline-toolbar';
timeline.prepend(timelineToolbar);timelineToolbar.append($('.transport'));
const zoomControls=document.createElement('div');zoomControls.className='timeline-zoom';
zoomControls.innerHTML='<button type="button" id="timelineFit" title="Show the whole timeline">Fit</button><label>Zoom<input id="timelineZoom" aria-label="Timeline zoom" type="range" min="1" max="4" step="0.1" value="1"></label>';
timelineToolbar.append(zoomControls,$('.links'));
const optionalFiles=document.createElement('details');optionalFiles.className='timeline-files';
optionalFiles.innerHTML='<summary>Files</summary><div></div>';
for(const link of [...$('.links').querySelectorAll('a')])optionalFiles.lastElementChild.append(link);
timelineToolbar.append(optionalFiles);
const timelineScroll=document.createElement('div'),timelineRail=document.createElement('div');
timelineScroll.className='timeline-scroll';timelineRail.className='timeline-rail';
timelineScroll.append(timelineRail);timeline.append(timelineScroll);
timelineRail.append(ruler,...timeline.querySelectorAll('.track'));
const cursorArea=document.createElement('div');cursorArea.className='timeline-cursor-area';
cursorArea.append($('.timeline-playhead'));timelineRail.append(cursorArea);
$('.track.video>div').textContent=$('header small').textContent;
$('.track.audio>div').textContent='Source audio';
$('.timing-help').textContent='Drag clips to move · Drag edges to trim · Select a word to edit its color';
function zoomTimeline(fit=false){
  const available=Math.max(200,timelineScroll.clientWidth-76);
  if(fit)$('#timelineZoom').value=1;
  timelineRail.style.width=Math.round(available*Number($('#timelineZoom').value)+76)+'px';
}
$('#timelineZoom').oninput=()=>zoomTimeline();$('#timelineFit').onclick=()=>zoomTimeline(true);
requestAnimationFrame(()=>{$('#timelineZoom').value=Math.min(4,Math.max(1,studioDuration*72/Math.max(200,timelineScroll.clientWidth-76)));zoomTimeline()});
window.addEventListener('resize',()=>zoomTimeline());
function currentLayout(){return cueLayouts[selectedCue]||{x:.5,y:.7,size:1}}
function setCaptionScale(value){
  const scale=clampStudio(value,.08,4);
  cueLayouts.forEach(layout=>layout.size=scale);
  $('#size').value=scale*100;$('#sizeNumber').value=Math.round(scale*100);
}
function snapshotStudio(){return {dirty:studioDirty,style:currentStyle,format:currentFormat,font:$('#font').value,visibility,demo_background:demoBackground,cues:JSON.parse(JSON.stringify(cues)),texts:currentTexts(),wordColors,cueLayouts,selectedCue,time:video.currentTime}}
function persistStudio(){if(studioSaving||!studioDirty)return;try{localStorage.setItem(studioKey,JSON.stringify(snapshotStudio()))}catch{}}
function dirtyStudio(){studioDirty=true;downloadVideo.classList.add('disabled');studioStatus.textContent='Unsaved changes · draft kept in this browser';persistStudio()}
function restoreStudio(saved){
  if(!saved||!Array.isArray(saved.cues)||saved.cues.length!==cues.length)return;
  if(templates[saved.style])currentStyle=saved.style;
  if(['source','instagram_vertical','square','youtube_horizontal'].includes(saved.format))currentFormat=saved.format;
  if(fonts[saved.font])$('#font').value=saved.font;
  if(['spoken','phrase','styled_spoken'].includes(saved.visibility))visibility=saved.visibility;
  if(project.demo&&['black','white'].includes(saved.demo_background))demoBackground=saved.demo_background;
  saved.cues.forEach((q,i)=>{cues[i].start=q.start;cues[i].end=q.end;cues[i].words=q.words.map(w=>({...w}));cues[i].template_source=q.template_source||cues[i].template_source;cues[i].template_slot=q.template_slot??cues[i].template_slot;if(saved.texts?.[i]!==undefined)$$('.cue-row textarea')[i].value=saved.texts[i]});
  if(saved.cueLayouts?.length===cues.length)cueLayouts=saved.cueLayouts.map(q=>({...q}));
  if(saved.wordColors?.length===cues.length)wordColors=saved.wordColors.map(row=>[...row]);
  selectedCue=clampStudio(Number(saved.selectedCue)||0,0,cues.length-1);studioDirty=saved.dirty!==false;
  setCaptionScale(currentLayout().size);
  $('#wordVisibility').value=visibility;
  video.addEventListener('loadedmetadata',()=>{video.currentTime=clampStudio(Number(saved.time)||0,0,studioDuration)},{once:true});
}
let beforeRestore=null;
$('#restoreSaved').onclick=()=>{
  beforeRestore=snapshotStudio();
  restoreStudio({style:project.style,format:project.output_format||'source',font:project.font||'template',visibility:project.word_visibility||(project.caption_content==='lyrics'?'spoken':'phrase'),demo_background:project.demo_background||(/(?:white|light|paper)/.test(project.source_relative||'')?'white':'black'),cues:project.cues,texts:project.cues.map(q=>q.words.map(w=>w.text).join(' ')),wordColors:project.word_colors,cueLayouts:project.cues.map((_,i)=>project.cue_layouts?.[i]||{x:.5,y:project.position??.7,size:project.size??1}),selectedCue:0,time:0});
  try{localStorage.removeItem(studioKey)}catch{}
  studioDirty=false;downloadVideo.classList.toggle('disabled',!project.has_video);$('#undoRestore').classList.remove('hidden');renderAllWordEditors();selectCue(0,true);studioStatus.textContent='Saved version restored · Undo restore is available';
};
$('#undoRestore').onclick=()=>{if(beforeRestore){restoreStudio(beforeRestore);renderAllWordEditors();selectCue(selectedCue,true);dirtyStudio();$('#undoRestore').classList.add('hidden')}};
try{const hash=new URLSearchParams(location.hash.slice(1));const saved=hash.get('draft');restoreStudio(saved?JSON.parse(saved):JSON.parse(localStorage.getItem(studioKey)||'null'));if(saved)history.replaceState(null,'',location.pathname)}catch{}
function syncWords(index){
  const q=cues[index],tokens=wordsAt(index);
  if(tokens.length===q.words.length){q.words.forEach((w,i)=>w.text=tokens[i]);return}
  const weights=tokens.map(w=>Math.max(1,w.length)),total=weights.reduce((a,b)=>a+b,0);let cursor=q.start;
  q.words=tokens.map((text,i)=>{const end=i===tokens.length-1?q.end:cursor+(q.end-q.start)*weights[i]/total;const word={text,start:roundTime(cursor),end:roundTime(end)};cursor=end;return word});
}
function selectCue(index,seek=false){
  selectedCue=clampStudio(index,0,cues.length-1);
  const q=cues[selectedCue],layout=currentLayout();
  $('#position').value=layout.y*100;$('#size').value=layout.size*100;$('#sizeNumber').value=Math.round(layout.size*100);
  $('#cueStart').value=q.start.toFixed(2);$('#cueEnd').value=q.end.toFixed(2);
  $('#selectedCaptionLabel').textContent=`Caption ${selectedCue+1} · ${Math.round(layout.size*100)}%`;
  $$('.cue-row').forEach((row,i)=>row.classList.toggle('selected',i===selectedCue));
  if(seek){video.pause();video.currentTime=q.start+Math.min(.08,(q.end-q.start)/2)}
  renderStudioTimeline();renderWordTiming();draw();
}
function renderStudioTimeline(){
  const attribute=value=>esc(value).replaceAll('"','&quot;').replaceAll("'",'&#39;');
  captionTrack.innerHTML=cues.map((q,i)=>`<button type="button" data-cue="${i}" class="${i===selectedCue?'selected':''}" aria-label="Caption ${i+1}: ${attribute(wordsAt(i).join(' '))}" style="left:${q.start/studioDuration*100}%;width:${(q.end-q.start)/studioDuration*100}%"><i class="clip-handle left" data-edge="start"></i>${esc(wordsAt(i).join(' '))}<i class="clip-handle right" data-edge="end"></i></button>`).join('');
  const q=cues[selectedCue];
  wordTrack.innerHTML=q.words.map((w,i)=>`<button type="button" data-word="${i}" class="${i===selectedWords[selectedCue]?'selected':''}" aria-label="Word ${i+1}: ${attribute(w.text)}" style="left:${w.start/studioDuration*100}%;width:${(w.end-w.start)/studioDuration*100}%"><i class="clip-handle left" data-edge="start"></i>${esc(w.text)}<i class="clip-handle right" data-edge="end"></i></button>`).join('');
  $$('.cue-row').forEach((row,i)=>row.querySelector('small').textContent=`${cues[i].start.toFixed(2)}–${cues[i].end.toFixed(2)}`);
  for(const track of [captionTrack,wordTrack])track.querySelectorAll('button').forEach(button=>{
    const interval=track===captionTrack?cues[Number(button.dataset.cue)]:q.words[Number(button.dataset.word)];
    button.title=`${button.getAttribute('aria-label')} · ${interval.start.toFixed(3)}–${interval.end.toFixed(3)} s`;
  });
}
function renderWordTiming(){
  $$('.word-time-editor').forEach(node=>node.remove());
  const host=document.querySelector(`[data-word-tools="${selectedCue}"]`);if(!host)return;
  host.querySelector('.word-time-editor')?.remove();
  const index=selectedWords[selectedCue]||0,w=cues[selectedCue].words[index];if(!w)return;
  const box=document.createElement('div');box.className='word-time-editor';
  box.innerHTML=`<label>Word starts (s)<input aria-label="Selected word starts" type="number" step="0.01" value="${w.start.toFixed(2)}"></label><label>Word ends (s)<input aria-label="Selected word ends" type="number" step="0.01" value="${w.end.toFixed(2)}"></label>`;
  box.querySelectorAll('input').forEach((input,i)=>input.onchange=()=>{
    const q=cues[selectedCue],a=i===0?Number(input.value):w.start,b=i===1?Number(input.value):w.end;
    const low=index?q.words[index-1].end:q.start,high=index+1<q.words.length?q.words[index+1].start:q.end;
    if(!Number.isFinite(a+b)||a<low||b>high||b-a<.01){studioStatus.textContent='Keep this word inside its caption and between adjacent words';renderWordTiming();return}
    w.start=roundTime(a);w.end=roundTime(b);dirtyStudio();renderStudioTimeline();draw();
  });host.appendChild(box);
}
function updateCueInterval(index,start,end){
  const q=cues[index],oldStart=q.start,oldDuration=q.end-q.start;
  const low=index?cues[index-1].end:0,high=index+1<cues.length?cues[index+1].start:studioDuration;
  start=clampStudio(start,low,high-.06);end=clampStudio(end,start+.06,high);
  q.words.forEach(w=>{w.start=roundTime(start+(w.start-oldStart)/oldDuration*(end-start));w.end=roundTime(start+(w.end-oldStart)/oldDuration*(end-start))});
  q.start=roundTime(start);q.end=roundTime(end);
}
function bindTimingDrag(track,wordMode){
  let drag=null;
  track.addEventListener('pointerdown',e=>{
    const button=e.target.closest('button');if(!button)return;
    e.preventDefault();video.pause();
    if(!wordMode)selectCue(Number(button.dataset.cue),false);else{selectedWords[selectedCue]=Number(button.dataset.word);renderAllWordEditors();renderWordTiming()}
    const q=cues[selectedCue],index=wordMode?Number(button.dataset.word):selectedCue;
    drag={index,edge:e.target.dataset.edge||'move',x:e.clientX,original:JSON.parse(JSON.stringify(q)),wordMode};
    track.setPointerCapture(e.pointerId);
    if(wordMode)previewSelectedWord(selectedCue);else video.currentTime=q.start+Math.min(.46,(q.end-q.start)*.7);
  });
  track.addEventListener('pointermove',e=>{
    if(!drag||Math.abs(e.clientX-drag.x)<3)return;e.preventDefault();
    const q=cues[selectedCue],d=(e.clientX-drag.x)/track.getBoundingClientRect().width*studioDuration;
    if(wordMode){
      const i=drag.index,old=drag.original.words[i],w=q.words[i],low=i?q.words[i-1].end:q.start,high=i+1<q.words.length?q.words[i+1].start:q.end;
      if(drag.edge==='start')w.start=roundTime(clampStudio(old.start+d,low,w.end-.02));
      else if(drag.edge==='end')w.end=roundTime(clampStudio(old.end+d,w.start+.02,high));
      else{const delta=clampStudio(d,low-old.start,high-old.end);w.start=roundTime(old.start+delta);w.end=roundTime(old.end+delta)}
    }else{
      Object.assign(q,JSON.parse(JSON.stringify(drag.original)));
      let a=q.start,b=q.end,low=selectedCue?cues[selectedCue-1].end:0,high=selectedCue+1<cues.length?cues[selectedCue+1].start:studioDuration;
      if(drag.edge==='start')a=clampStudio(a+d,low,b-.06);else if(drag.edge==='end')b=clampStudio(b+d,a+.06,high);else{const delta=clampStudio(d,low-a,high-b);a+=delta;b+=delta}
      updateCueInterval(selectedCue,a,b);
    }
    dirtyStudio();$('#cueStart').value=q.start.toFixed(2);$('#cueEnd').value=q.end.toFixed(2);renderStudioTimeline();renderWordTiming();draw();
  });
  const finish=()=>{if(drag){drag=null;persistStudio()}};
  track.addEventListener('pointerup',finish);track.addEventListener('pointercancel',finish);
}
bindTimingDrag(captionTrack,false);bindTimingDrag(wordTrack,true);
ruler.onclick=e=>{video.pause();video.currentTime=clampStudio((e.clientX-ruler.getBoundingClientRect().left)/ruler.clientWidth*studioDuration,0,studioDuration);draw()};
$$('.cue-row').forEach((row,index)=>row.addEventListener('click',()=>{
  if(index!==selectedCue)selectCue(index,true);
}));
function previewSelectedWord(index){
  selectCue(index,false);video.pause();
  const q=cues[index],word=q.words[selectedWords[index]];
  // Pause after the entrance so a selected hero is visible, even when it is
  // the final word. Selecting never modifies timing, layout or motion.
  if(word){
    const seek=()=>{video.currentTime=Math.min(q.end-.015,word.start+Math.min(.46,(q.end-word.start)*.7));draw()};
    if(video.readyState===0)video.addEventListener('loadedmetadata',seek,{once:true});else seek();
  }
  draw();
}
const studioBaseWordEditor=renderWordEditor;
renderWordEditor=function(index){
  studioBaseWordEditor(index);
  const host=document.querySelector(`[data-word-tools="${index}"]`);
  host.querySelectorAll('.word-chip').forEach(button=>{
    button.setAttribute('aria-pressed',String(Number(button.dataset.wordIndex)===selectedWords[index]));
    button.onclick=event=>{event.stopPropagation();selectedWords[index]=Number(button.dataset.wordIndex);renderWordEditor(index);previewSelectedWord(index)};
  });
  const changeColor=color=>{
    wordColors[index][selectedWords[index]]=color;
    renderWordEditor(index);previewSelectedWord(index);dirtyStudio();
  };
  host.querySelectorAll('.palette button').forEach(button=>button.onclick=event=>{event.stopPropagation();changeColor(button.dataset.color||null)});
};
function updateSelection(){
  const q=cues[selectedCue],visible=q&&q.start<=video.currentTime&&video.currentTime<q.end&&caption.textContent.trim();
  selectionBox.classList.toggle('hidden',!visible||!video.paused);
  if(!visible)return;
  const a=caption.getBoundingClientRect(),b=stage.getBoundingClientRect();
  Object.assign(selectionBox.style,{left:(a.left-b.left-5)+'px',top:(a.top-b.top-5)+'px',width:(a.width+10)+'px',height:(a.height+10)+'px'});
}
applyStyle=function(){
  if(visibility!=='spoken')caption.style.fontWeight='';
  const style=templates[currentStyle],nativeY=style.default_position??.7;
  const sliderSize=$('#size').value,sliderPosition=$('#position').value;
  $('#size').value='100';$('#position').value=nativeY*100;
  studioOriginalApply();
  $('#size').value=sliderSize;$('#position').value=sliderPosition;
  const index=cues.findIndex(q=>q.start<=video.currentTime&&video.currentTime<q.end),layout=cueLayouts[index>=0?index:selectedCue]||currentLayout();
  const portrait=stage.clientHeight>=stage.clientWidth;
  const ratios=portrait?{typography_1:22.5,typography_2:11.5,typography_3:9.72,typography_4:6.8,typography_5:16.67}:{typography_1:13,typography_2:7.2,typography_3:5.5,typography_4:4.0,typography_5:16.67};
  if(visibility==='spoken'){
    captionPositionLayer.style.transform='none';
    caption.className='free-caption spoken-caption';caption.style.background='transparent';caption.style.color=templates[currentStyle].base;
    caption.style.left=layout.x*100+'%';caption.style.right='auto';caption.style.top=layout.y*100+'%';
    caption.style.fontSize=`${(portrait?7.8:5.6)*layout.size}cqw`;
    const file=fonts[$('#font').value]?.file||templates[currentStyle].font;
    caption.style.fontWeight=/Black/.test(file)?'900':/(bd|uib|b)\.ttf$/i.test(file)?'700':'400';
  }else{
    caption.style.left='';caption.style.right='';caption.style.width='';caption.style.maxWidth='';
    caption.style.fontSize=`${ratios[currentStyle]||(portrait?7.8:5.6)}cqw`;
    captionPositionLayer.style.transformOrigin=`50% ${nativeY*100}%`;
    captionPositionLayer.style.transform=`translate(${(layout.x-.5)*stage.clientWidth}px,${(layout.y-nativeY)*stage.clientHeight}px) scale(${layout.size})`;
  }
};
draw=function(){
  paintStudioBackground();
  const cinematic=['cinematic_reference','kinetic_gold','serif_circle'].includes(templates[currentStyle]?.layout);
  $$('.ratios button').forEach(button=>{
    const format=button.dataset.format;
    button.textContent=cinematic?(format==='youtube_horizontal'?'Horizontal · 7 words':format==='square'?'Square · 4 words':'Vertical · 4 words'):(format==='youtube_horizontal'?'16:9':format==='square'?'1:1':'9:16');
  });
  const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end),q=cues[index];
  if(visibility==='spoken'){
    applyStyle();const wi=q?q.words.findIndex(w=>w.start<=now&&now<w.end):-1;
    caption.innerHTML=wi<0?'':`<span style="color:${wordColors[index]?.[wi]||templates[currentStyle].base}">${esc(templates[currentStyle].case==='upper'?q.words[wi].text.toUpperCase():q.words[wi].text)}</span>`;
  }else{
    studioOriginalDraw();applyStyle();
    if(visibility==='styled_spoken'){
      const active=q?q.words.findIndex(w=>w.start<=now&&now<w.end):-1;
      caption.style.visibility=active<0?'hidden':'visible';
      caption.querySelectorAll('[data-word]').forEach(element=>element.style.visibility=Number(element.dataset.word)===active?'visible':'hidden');
    }else{
      // Original animation builds the entire composition, then holds every
      // revealed word until this lyric group ends. Never replace it with the
      // current-word-only presentation.
      caption.style.visibility=q?'visible':'hidden';
      caption.querySelectorAll('[data-word]').forEach(element=>{
        const word=q?.words[Number(element.dataset.word)],revealed=word&&word.start<=now;
        element.style.visibility=revealed?'visible':'hidden';
        if(['typography_1','typography_2'].includes(currentStyle)&&word){
          const duration=currentStyle==='typography_1'?.24:element.classList.contains('t2-bar-word')?.16:.20;
          const show=1-Math.pow(1-clampStudio((now-word.start)/duration,0,1),3);
          element.style.opacity=String(show);
          if(element.classList.contains('t2-bar-word'))element.style.filter=`blur(${(1-show)*.12}em)`;
        }
      });
    }
  }
  if(q && visibility!=='spoken' && ['typography_3','typography_4'].includes(currentStyle)){
    // Keep the approved row arrangement and camera keys for longer scripts.
    // Fit the complete group before applying the original camera zoom.
    const wrap=caption.querySelector(currentStyle==='typography_4'?'.t4-wrap':'.t3-wrap');
    if(wrap){
      const peak=Math.max(1,...project.kinetic_profile.echo_zoom.map(k=>k[1]));
      const span=Math.max(wrap.scrollWidth,wrap.offsetWidth),available=stage.clientWidth*.88;
      if(span*peak>available)caption.style.fontSize=(parseFloat(getComputedStyle(caption).fontSize)*available/(span*peak))+'px';
    }
    const hero=currentStyle==='typography_3'?typographyThreeAnchor(wordsFor(q)):q.words.length-1;
    const age=now-q.words[hero].start, keys=project.kinetic_profile.echo_zoom;
    let scale=keys[keys.length-1][1];
    if(age<=keys[0][0])scale=keys[0][1];
    else for(let i=1;i<keys.length;i++)if(age<=keys[i][0]){
      const a=keys[i-1],b=keys[i];scale=a[1]+(b[1]-a[1])*(age-a[0])/(b[0]-a[0]);break;
    }
    caption.style.transformOrigin='50% 50%';
    caption.style.transform=`translateY(-50%) scale(${scale})`;
  }
  if(visibility==='spoken'){caption.style.visibility='visible';caption.style.transform='translate(-50%,-50%)'}
  const playhead=$('.timeline-playhead');if(playhead)playhead.style.left=clampStudio(now/studioDuration*100,0,100)+'%';
  $('#time').textContent=`${now.toFixed(2)}s / ${studioDuration.toFixed(2)}s`;
  updateSelection();
  $('#selectedCaptionLabel').textContent=`Caption ${selectedCue+1} · ${Math.round(currentLayout().size*100)}%`;
};
// The original studio registered its renderer by reference on seeking; remove
// that listener so it cannot paint a full phrase over strict spoken-word mode.
video.removeEventListener('seeked',studioOriginalDraw);video.addEventListener('seeked',draw);
let touchPoints=new Map(),gesture=null;
function beginCaptionGesture(e,resize=false){
  const index=cues.findIndex(q=>q.start<=video.currentTime&&video.currentTime<q.end);if(index<0)return;
  e.preventDefault();video.pause();selectCue(index,false);e.currentTarget.setPointerCapture(e.pointerId);
  touchPoints.set(e.pointerId,{x:e.clientX,y:e.clientY});
  const layout=currentLayout(),rect=stage.getBoundingClientRect();
  gesture={resize,x:e.clientX,y:e.clientY,layout:{...layout},rect};
  gesture.radius=Math.hypot(e.clientX-(rect.left+layout.x*rect.width),e.clientY-(rect.top+layout.y*rect.height));
  if(touchPoints.size===2){const [a,b]=[...touchPoints.values()];gesture.distance=Math.hypot(a.x-b.x,a.y-b.y)}
}
function moveCaptionGesture(e){
  if(!gesture||!touchPoints.has(e.pointerId))return;e.preventDefault();touchPoints.set(e.pointerId,{x:e.clientX,y:e.clientY});
  const g=gesture,layout=currentLayout();
  if(touchPoints.size===2&&g.distance){const [a,b]=[...touchPoints.values()];setCaptionScale(g.layout.size*Math.hypot(a.x-b.x,a.y-b.y)/Math.max(10,g.distance))}
  else if(g.resize){const radius=Math.hypot(e.clientX-(g.rect.left+g.layout.x*g.rect.width),e.clientY-(g.rect.top+g.layout.y*g.rect.height));setCaptionScale(g.layout.size*radius/Math.max(5,g.radius))}
  else{layout.x=clampStudio(g.layout.x+(e.clientX-g.x)/g.rect.width,0,1);layout.y=clampStudio(g.layout.y+(e.clientY-g.y)/g.rect.height,0,1)}
  $('#position').value=layout.y*100;$('#size').value=layout.size*100;$('#sizeNumber').value=Math.round(layout.size*100);dirtyStudio();draw();
}
function endCaptionGesture(e){touchPoints.delete(e.pointerId);if(!touchPoints.size){gesture=null;persistStudio()}}
for(const target of [caption,$('#resizeCaption')]){
  target.addEventListener('pointerdown',e=>beginCaptionGesture(e,target.id==='resizeCaption'));
  target.addEventListener('pointermove',moveCaptionGesture);target.addEventListener('pointerup',endCaptionGesture);target.addEventListener('pointercancel',endCaptionGesture);
}
caption.addEventListener('wheel',e=>{e.preventDefault();setCaptionScale(currentLayout().size*(e.deltaY<0?1.05:.95));$('#size').value=currentLayout().size*100;$('#sizeNumber').value=Math.round(currentLayout().size*100);dirtyStudio();draw()},{passive:false});
$('#resizeCaption').addEventListener('keydown',e=>{if(['ArrowUp','ArrowRight','ArrowDown','ArrowLeft'].includes(e.key)){e.preventDefault();setCaptionScale(currentLayout().size+(['ArrowUp','ArrowRight'].includes(e.key)?.05:-.05));$('#size').value=currentLayout().size*100;$('#sizeNumber').value=Math.round(currentLayout().size*100);dirtyStudio();draw()}});
$('#cueStart').onchange=()=>{const q=cues[selectedCue];updateCueInterval(selectedCue,Number($('#cueStart').value),q.end);selectCue(selectedCue);dirtyStudio()};
$('#cueEnd').onchange=()=>{const q=cues[selectedCue];updateCueInterval(selectedCue,q.start,Number($('#cueEnd').value));selectCue(selectedCue);dirtyStudio()};
$('#sizeNumber').oninput=()=>{if(Number.isFinite(Number($('#sizeNumber').value))){setCaptionScale(Number($('#sizeNumber').value)/100);$('#size').value=currentLayout().size*100;dirtyStudio();draw()}};
$('#size').addEventListener('input',()=>{setCaptionScale(Number($('#size').value)/100);$('#sizeNumber').value=$('#size').value;dirtyStudio();draw()});
$('#position').addEventListener('input',()=>{currentLayout().y=Number($('#position').value)/100;dirtyStudio();draw()});
$('#font').addEventListener('change',()=>{dirtyStudio();draw()});
$('#wordVisibility').onchange=()=>{visibility=$('#wordVisibility').value;dirtyStudio();draw()};
// Synchronize changed word counts before the original report's input listener
// draws. Otherwise a new six-word phrase can still have four timing entries.
$$('.cue-row textarea').forEach((input,index)=>input.addEventListener('input',()=>{syncWords(index);renderAllWordEditors();renderStudioTimeline();renderWordTiming();dirtyStudio();draw()},true));
for(const target of [$('.template-list'),$('.ratios')])target.addEventListener('click',()=>{dirtyStudio();draw()});
// Selecting a tuned preset restores its composition, font and animation. The
// optional single-word presentation must never silently replace that design.
$$('.template-card').forEach(card=>card.onclick=()=>{
  currentStyle=card.dataset.style;
  if(project.script_preview)demoBackground=['caption_3','caption_5'].includes(currentStyle)?'white':'black';
  const style=templates[currentStyle];
  // Keep the chosen word display when changing the original typography.
  $('#wordVisibility').value=visibility;$('#font').value='template';
  const sharedSize=currentLayout().size;
  cueLayouts=cues.map(()=>({x:.5,y:style.default_position??.7,size:sharedSize}));
  selectCue(selectedCue,false);dirtyStudio();draw();
});
$('.cue-list').addEventListener('click',e=>{if(e.target.closest('.palette button')){dirtyStudio();draw()}});
async function connectStudio(){
  if(location.protocol==='file:'){
    studioStatus.textContent='This file needs the connected editor';
    if(project.editor_url){const link=document.createElement('a');link.className='studio-download';link.textContent='Open connected editor';link.href=project.editor_url;link.onclick=e=>{e.preventDefault();location.href=project.editor_url+'#draft='+encodeURIComponent(JSON.stringify(snapshotStudio()))};studioSave.before(link)}
    return null;
  }
  const response=await (window.storylensFetch||fetch)('/api/bridge',{cache:'no-store'});if(!response.ok)throw new Error('Open Caption Studio through the local editor');
  studioBridge=await response.json();studioStatus.textContent=studioDirty?'Draft restored · ready to export':'Connected · ready to edit';return studioBridge;
}
save=async function(){
  if(studioSaving)return;
  if(location.protocol==='file:'&&project.editor_url){persistStudio();location.href=project.editor_url+'#draft='+encodeURIComponent(JSON.stringify(snapshotStudio()));return}
  studioSaving=true;studioSave.disabled=true;studioStatus.classList.add('studio-exporting');studioStatus.textContent='Exporting your current edits…';
  try{
    const bridge=await connectStudio();if(!bridge)throw new Error('Open the connected editor to export');
    if(project.demo||currentStyle==='caption_2'||currentStyle==='caption_3'){
      const supported=await (window.storylensFetch||fetch)('/api/captions/capabilities',{cache:'no-store',headers:{'X-Hinglish-Token':bridge.token}});
      const capabilities=supported.ok?await supported.json():null;
      const matching=capabilities?.revision>=2&&(!project.demo||capabilities.demo_backgrounds?.includes(demoBackground))&&(currentStyle!=='caption_2'||JSON.stringify(capabilities.caption_two_motion)===JSON.stringify(project.caption_two_profile.motion))&&(currentStyle!=='caption_3'||capabilities.caption_three_layout_revision===(project.caption_three_profile.layout_revision??1));
      if(!matching)throw Object.assign(Error('Storylens needs one restart to use the updated caption motion and backgrounds. Finish any active task, restart Storylens, then retry Save & export. Your caption draft is kept.'),{code:'caption_restart_required',details:'Caption exporter needs a restart: the running exporter does not match this preview (capability HTTP '+supported.status+').'});
    }
    studioStatus.textContent='Exporting your current edits…';cues.forEach((_,i)=>syncWords(i));
    const layout=currentLayout(),body={project_path:project.project_path,texts:currentTexts(),word_colors:cues.map((q,i)=>q.words.map((_,j)=>wordColors[i]?.[j]??null)),style:currentStyle,font:$('#font').value,position:layout.y,size:layout.size,output_format:currentFormat,word_visibility:visibility,cue_layouts:cueLayouts,timings:cues.map(q=>({start:q.start,end:q.end,words:q.words.map(w=>({start:w.start,end:w.end}))})),export_video:true};
    if(project.demo)body.demo_background=demoBackground;
    const response=await (window.storylensFetch||fetch)('/api/captions/rebuild',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':bridge.token},body:JSON.stringify(body)});
    const result=await (window.storylensResponse?window.storylensResponse(response):response.json());if(!response.ok)throw new Error(result.error||'Could not export captions');
    Object.assign(project,{style:currentStyle,font:body.font,position:layout.y,size:layout.size,output_format:currentFormat,word_visibility:visibility,has_video:true,cues:JSON.parse(JSON.stringify(cues)),cue_layouts:cueLayouts.map(row=>({...row})),word_colors:wordColors.map(row=>[...row])});
    if(project.demo)project.demo_background=demoBackground;
    studioDirty=false;try{localStorage.removeItem(studioKey)}catch{}
    downloadVideo.href='captioned-preview.mp4?v='+Date.now();downloadVideo.classList.remove('disabled');
    studioStatus.textContent='Export ready · Download MP4';
    location.reload();
  }catch(error){studioStatus.textContent=window.storylensError?window.storylensError(error):error.message;persistStudio()}
  finally{studioSaving=false;studioSave.disabled=false;studioStatus.classList.remove('studio-exporting')}
};
window.storylensSaveForEditor=async function(){
  if(studioSaving)throw Error('Caption export is still running. Wait for it to finish, then import.');
  studioSaving=true;studioSave.disabled=true;
  try{
    const bridge=await connectStudio();if(!bridge)throw Error('Open the connected Storylens editor to import captions.');
    cues.forEach((_,i)=>syncWords(i));
    const layout=currentLayout();
    const body={project_path:project.project_path,save_project_only:true,texts:currentTexts(),
      word_colors:cues.map((q,i)=>q.words.map((_,j)=>wordColors[i]?.[j]??null)),
      style:currentStyle,font:$('#font').value,position:layout.y,size:layout.size,
      output_format:currentFormat,word_visibility:visibility,cue_layouts:cueLayouts,
      timings:cues.map(q=>({start:q.start,end:q.end,words:q.words.map(w=>({start:w.start,end:w.end}))}))};
    const response=await (window.storylensFetch||fetch)('/api/captions/rebuild',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':bridge.token},body:JSON.stringify(body)});
    const result=await window.storylensResponse(response);
    if(!response.ok)throw Error(result.error||'Your caption changes could not be saved. Retry the import; your draft is kept.');
    Object.assign(project,result.project);studioDirty=false;
    wordColors=body.word_colors;downloadVideo.classList.toggle('disabled',Boolean(project.preview_stale)||!project.has_video);
    try{localStorage.removeItem(studioKey)}catch{}
    studioStatus.textContent='Caption design saved · opening your editor';
  }finally{studioSaving=false;studioSave.disabled=false}
};
studioSave.onclick=save;
window.addEventListener('beforeunload',()=>{if(studioDirty)persistStudio()});
video.addEventListener('timeupdate',()=>{if(video.currentTime>=studioDuration){video.pause();if(video.currentTime>studioDuration)video.currentTime=studioDuration;}$('#time').textContent=`${Math.min(video.currentTime,studioDuration).toFixed(2)}s / ${studioDuration.toFixed(2)}s`;});
video.addEventListener('play',()=>selectionBox.classList.add('hidden'));video.addEventListener('pause',draw);
function studioPlayback(){if(!video.paused)draw();requestAnimationFrame(studioPlayback)}requestAnimationFrame(studioPlayback);
window.addEventListener('resize',draw);
setCaptionScale(currentLayout().size);renderAllWordEditors();selectCue(selectedCue);setFormat(currentFormat==='source'?(project.width<project.height?'instagram_vertical':project.width===project.height?'square':'youtube_horizontal'):currentFormat,true);
// Explicit review links open the chosen orientation even when an older browser
// draft was last viewed in the other format. Subsequent edits remain available.
if(project.review_orientation)setFormat(project.review_orientation==='horizontal'?'youtube_horizontal':'instagram_vertical',true);
if(!studioDirty&&!project.preview_stale&&project.has_video&&(project.word_visibility||project.caption_content!=='lyrics'))downloadVideo.classList.remove('disabled');
connectStudio().catch(()=>{studioStatus.textContent='Editor is offline · your draft is kept'});
document.fonts.ready.then(()=>draw());
