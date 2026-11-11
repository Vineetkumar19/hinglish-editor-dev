(()=>{
 const token=document.documentElement.dataset.token;
 const names={premiere:'Premiere Pro',aftereffects:'After Effects',capcut:'CapCut',resolve:'DaVinci Resolve'};
 const editorName=editor=>editor==='aftereffects'?'After Effects':names[editor];
 function brollReview(folder,editor,page){
  const match=String(folder||'').replace(/\\/g,'/').match(/\/output\/broll\/(.+)$/i);
  const parts=match?match[1].split('/'):[];
  if(!parts.length||parts.some(p=>!p||p==='.'||p==='..'||p.includes('\0')))throw Error('Open the saved B-roll review before choosing an editor.');
  const file=/[/\\]index\.html$/i.test(page||'')?'index.html':'report.html';
  return '/broll-output/'+parts.map(encodeURIComponent).join('/')+'/'+file+'?editor='+editor;
 }
 async function api(path,body){const r=await window.storylensFetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(body?{body:JSON.stringify(body)}:{})});return window.storylensResponse(r).then(d=>{if(!r.ok)throw Error(d.error||'The editor connection stopped');return d})}
 function modal(title){const box=document.createElement('dialog');box.className='editor-dialog';const close=document.createElement('button');close.className='editor-close';close.setAttribute('aria-label','Close editor handoff');close.innerHTML=window.storylensIcon('close');close.onclick=()=>box.close();const h=document.createElement('h2');h.textContent=title;box.append(close,h);document.body.append(box);box.addEventListener('close',()=>box.remove());box.showModal();return box}
 function error(box,e){const message=document.createElement('p');message.textContent=window.storylensError(e);message.style.color='#ffbba6';box.append(message)}
 function action(label,callback){const b=document.createElement('button');b.className='editor-action';b.textContent=label;b.onclick=async()=>{b.disabled=true;try{await callback()}finally{b.disabled=false}};return b}
 async function prepare(editor,result,caption_mode='rendered',autoOpen=false){
  const box=modal('Continue in '+editorName(editor));const status=document.createElement('p');status.className='editor-status';status.setAttribute('role','status');status.textContent='Preparing the exact finished result…';box.append(status);
  try{
   const settings=await window.storylensBeforeHandoff?.({editor,caption_mode})||{};
   const broll=/[/\\](broll|visuals)[/\\]/i.test(result.folder);if(broll&&typeof settings.open_editor==='boolean')autoOpen=settings.open_editor;
   let task=await api('/api/editors/prepare',{editor,folder:result.folder,caption_mode,broll_include_options:Boolean(settings.broll_include_options)});
   while(task.status==='running'&&box.isConnected){status.textContent=task.stage;await new Promise(r=>setTimeout(r,1000));task=await api('/api/editors/task?id='+encodeURIComponent(task.id))}
   if(!box.isConnected)return;
   if(task.status==='failed'){const e=Error(task.error.message);e.code=task.error.code;e.details=task.error.details;throw e}
   status.textContent=task.notice;
   for(const p of task.projects||[]){const row=document.createElement('div');row.className='file-row';row.textContent=p.project+' · '+p.duration.toFixed(1)+' seconds';box.append(row)}
   const controls=document.createElement('div');for(const [label,code] of [[editor==='resolve'?'Import timelines':'Open '+editorName(editor),'open-editor'],['Open output folder','open-folder']])controls.append(action(label,async()=>{try{const answer=await api('/api/editors/action',{id:task.id,action:code});status.textContent=answer.message}catch(e){error(box,e)}}));box.append(controls);
   const downloads=document.createElement('details');const downloadHeading=document.createElement('summary');downloadHeading.textContent='Optional downloads';downloads.append(downloadHeading);box.append(downloads);
   task.files.forEach((f,i)=>{const row=document.createElement('div');row.className='file-row';const a=document.createElement('a');a.textContent='Download '+f.name;a.href='/api/editors/download?id='+encodeURIComponent(task.id)+'&index='+i+'&token='+encodeURIComponent(token);a.download=f.name;row.append(a);downloads.append(row)});
   if(autoOpen&&task.notice){const note=document.createElement('p');note.textContent=task.notice;box.append(note)}
   if(autoOpen){const answer=await api('/api/editors/action',{id:task.id,action:'open-editor'});status.textContent=answer.message}
  }catch(e){status.textContent='Your finished edit is kept.';error(box,e)}
 }
 function exportRow(container, onExport, disabledReason=''){
  if(!container)return;
  const label=document.createElement('span');
  label.className='editor-export-label';label.textContent='Export';
  container.replaceChildren(label);
  container.setAttribute('role','group');container.setAttribute('aria-label','Export to editor');
  for(const editor of ['capcut','resolve','premiere','aftereffects']){
   const button=document.createElement('button');
   button.type='button';button.className='editor-logo-button';
   button.disabled=Boolean(disabledReason);
   button.setAttribute('aria-label','Export to '+names[editor]);
   button.title=disabledReason||'Export to '+names[editor];
   button.innerHTML=window.storylensEditorLogo(editor);
   button.onclick=()=>onExport(editor,button);
   container.append(button);
  }
 }
 function render(container,result,options={}){
  const folder=result?.folder||'';
  const broll=/[/\\]broll[/\\]/i.test(folder), captions=/[/\\]captions[/\\]/i.test(folder);
  exportRow(container,editor=>{
   if(broll&&editor!=='resolve')return window.location.assign(brollReview(folder,editor,result.page));
   if(editor==='premiere'&&captions)return prepare(editor,result,'words',true);
   if(editor==='capcut'&&captions){
    const box=modal('Caption layers in '+names[editor]),note=document.createElement('p');
    note.textContent='Editable words use basic CapCut text styling. Choose the finished video to keep the exact animated appearance.';
    box.append(note,action('Editable words',()=>{box.close();return prepare(editor,result,'words',true)}),
      action('Finished video',()=>{box.close();return prepare(editor,result,'rendered',true)}));
    return;
   }
   return prepare(editor,result,'rendered',true);
  },options.disabledReason||(!folder?'Create a result to enable export':''));
 }
 function renderMedia(container, path) {
  const transfers=new Map();
  exportRow(container,async(editor,button)=>{
   button.disabled=true;
   const box=modal('Export to '+names[editor]), status=document.createElement('p');
   status.setAttribute('role','status');status.textContent='Preparing this clip…';box.append(status);
   const send=async()=>{
    let job=transfers.get(editor);
    if(!job){job=await api('/api/editor-link/prepare',{source:'storylens',target:editor,kind:'media',path});transfers.set(editor,job);}
    await confirmTransfer(()=>api('/api/editor-link/apply',{id:job.id}),message=>status.textContent=message,()=>box.isConnected);
   };
   try{await send()}
   catch(e){status.textContent=window.storylensError(e)}
   finally{button.disabled=false}
   box.append(action('Check transfer',async()=>{try{await send()}catch(e){status.textContent=window.storylensError(e)}}));
  },!path?'Create a clip to enable export':'');
 }
 async function confirmTransfer(check, update, active = () => true) {
  const deadline=Date.now()+45000;
  while(active()){
   const result=await check();
   update(result.message);
   if(!result.pending)return;
   if(Date.now()>=deadline){update(result.message+' Select the same export icon to check again.');return;}
   await new Promise(resolve=>setTimeout(resolve,1500));
  }
 }
 window.storylensEditors={render,exportRow,renderMedia,confirmTransfer};
 // The standalone tools use the same status and action row as the main editor.
 window.storylensResults={mount(container,options={}){
  container.className='result storylens-result is-pending';
  container.innerHTML='<div class="check" aria-hidden="true">·</div><div class="result-summary"><b></b><p></p></div><div class="result-actions completed-result-actions" role="group" aria-label="Result actions"><button type="button">View Result</button><span class="editor-exports"></span><button type="button" class="secondary">Open Folder</button></div>';
  const title=container.querySelector('b'),meta=container.querySelector('p'),check=container.querySelector('.check'),buttons=container.querySelectorAll('.result-actions>button'),exports=container.querySelector('.editor-exports');
  let result=null;
  async function activate(callback,path){try{if(callback)await callback(result);else if(path)await api('/api/open',{path})}catch(e){window.storylensShowError(e)}}
  buttons[0].onclick=()=>activate(options.onView,result?.page);buttons[1].onclick=()=>activate(options.onFolder,result?.folder);
  function setPending(){result=null;container.classList.add('is-pending');title.textContent='Your result will appear here';meta.textContent='View and export after processing.';check.textContent='·';buttons.forEach(b=>b.disabled=true);render(exports,null)}
  function setResult(value){result=value;container.classList.remove('is-pending');title.textContent=options.title||'Your timeline is ready';meta.textContent=options.meta||'';check.innerHTML=window.storylensIcon('check');buttons[0].disabled=!value?.page&&!options.onView;buttons[1].disabled=!value?.folder;render(exports,value,{disabledReason:options.disabledReason})}
  setPending();return {setPending,setResult};
 }};
 document.dispatchEvent(new Event('storylens-editors-ready'));
})();
