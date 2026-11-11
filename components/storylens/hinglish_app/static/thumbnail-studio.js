// One entry point for covers, posts, posters and ordinary local images.
(()=>{
 const key='storylens-thumbnail-studio-v1',script=$('#script'),label=document.querySelector('label[for="script"]');
 const originalLabel=label.textContent,originalPlaceholder=script.placeholder;
 const sizes={'16:9':[1280,720],'9:16':[1080,1920],'4:5':[1080,1350],'1:1':[1080,1080],'2:3':[1080,1620],profile:[1080,1080]};
 const defaults={youtube:'16:9',instagram:'9:16',post:'4:5',poster:'2:3',general:'1:1'};
 const fields={category:'Category',aspect:'Aspect',count:'Count',text_mode:'TextMode',title:'Title',subtitle:'Subtitle'};
 let draft={},previousScript='',wasThumbnail=false;
 try{draft=JSON.parse(localStorage.getItem(key)||'{}');if(!draft.idea){const old=JSON.parse(localStorage.getItem('storylens-image-idea')||'null');if(old?.idea)draft={...draft,idea:old.idea,category:old.purpose==='thumbnail'?'youtube':'general',text_mode:'none'}}}catch{}
 for(const [field,id] of Object.entries(fields))if(draft[field]!==undefined)$('#thumbnail'+id).value=draft[field];
 function keep(){
  for(const [field,id] of Object.entries(fields))draft[field]=$('#thumbnail'+id).value;
  if(mode==='thumbnail')draft.idea=script.value;
  try{localStorage.setItem(key,JSON.stringify(draft))}catch{}
 }
 function sync(){
  const imageMode=mode==='thumbnail';
  if(imageMode&&!wasThumbnail){previousScript=script.value;script.value=draft.idea||'';wasThumbnail=true}
  else if(!imageMode&&wasThumbnail){draft.idea=script.value;keep();script.value=previousScript;wasThumbnail=false;label.textContent=originalLabel;script.placeholder=originalPlaceholder;$('#inputPath').closest('.field').classList.remove('hidden');$('#outputSettings').classList.remove('hidden')}
  if(!imageMode)return;
  $('#inputPath').closest('.field').classList.add('hidden');$('#outputSettings').classList.add('hidden');
  label.textContent='What should we create?';script.placeholder='e.g. A cricket match poster with floodlights, a red ball hitting the stumps and dramatic blue lighting.';
  const aspect=$('#thumbnailAspect').value==='auto'?defaults[$('#thumbnailCategory').value]:$('#thumbnailAspect').value;
  $('#thumbnailSize').textContent=sizes[aspect].join(' × ');
  $('#thumbnailHeadlineFields').classList.toggle('hidden',$('#thumbnailTextMode').value!=='exact');
 }
 for(const id of Object.values(fields))$('#thumbnail'+id).addEventListener('input',()=>{keep();sync()});
 $('#thumbnailCategory').addEventListener('change',()=>{$('#thumbnailAspect').value='auto';$('#thumbnailTextMode').value=$('#thumbnailCategory').value==='general'?'none':'auto';keep();sync()});
 script.addEventListener('input',()=>{if(mode==='thumbnail')keep()});
 document.addEventListener('storylensmodechange',sync);
 window.storylensThumbnailRequest=()=>{
  if(!script.value.trim())throw Error('Describe the image you want to create first.');
  if($('#thumbnailTextMode').value==='exact'&&!$('#thumbnailTitle').value.trim())throw Error('Enter your exact headline, or choose automatic / no headline.');
  keep();const design={};for(const [field,id] of Object.entries(fields))design[field]=$('#thumbnail'+id).value;
  design.count=Number(design.count);design.style=$('#thumbnailStyle').value;
  return {script:script.value,source_paths:[],input_path:'',use_resolve_timeline:false,thumbnail_design:design,generate_background:true,portrait:'',background:''};
 };
 window.storylensThumbnailSelect=payload=>{
  if(mode!=='thumbnail')return;
  const design=payload.thumbnail_design||(payload.mode==='aiimage'?{category:'general',text_mode:'none',style:payload.aiimage_style||'cinematic',custom_style:payload.aiimage_custom_style||'',aspect:payload.aiimage_aspect||'auto',count:Math.max(1,Math.min(4,Number(payload.aiimage_options)||1))}:{});
  for(const [field,id] of Object.entries(fields))if(design[field]!==undefined)$('#thumbnail'+id).value=design[field];
  if(design.style){$('#thumbnailStyle').value=design.style;$('#thumbnailStyle').dataset.requestedStyle=design.style}
  if(payload.script){script.value=payload.script;if(script.value.startsWith('STORYLENS_IMAGE_IDEA_V1\n')){try{script.value=JSON.parse(script.value.split('\n').slice(1).join('\n')).idea||payload.script}catch{}}}
  keep();sync();
 };
 const destination=new URLSearchParams(location.search).get('tool');
 if(destination==='thumbnail'||destination==='aiimage'){
  setMode('thumbnail');document.body.classList.add('tools-visible');
 }else sync();
})();
