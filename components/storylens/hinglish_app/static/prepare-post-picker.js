/* One visible, read-only chooser. Selecting a path never uploads file bytes. */
window.StorylensVideoPicker = (() => {
 let active=null;
 const make=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
 function open({path='',browse}){
  if(active)return active;
  active=new Promise(resolve=>{
   const dialog=make('dialog');dialog.id='videoPathDialog';dialog.setAttribute('aria-labelledby','videoPathDialogTitle');
   const head=make('div'),heading=make('h2','Choose video'),cancel=make('button','Cancel');heading.id='videoPathDialogTitle';head.className='inline';head.append(heading,cancel);
   const row=make('form'),location=make('input'),go=make('button','Open'),up=make('button','Up'),drives=make('button','Drives');
   location.setAttribute('aria-label','Video chooser folder');location.placeholder='Folder path';location.value=path;row.className='inline';go.type='submit';up.type=drives.type='button';row.append(location,go,up,drives);
   const filter=make('input');filter.setAttribute('aria-label','Video chooser filename');filter.placeholder='Find video';
   const status=make('p');status.setAttribute('role','status');status.className='muted';const list=make('div');list.className='video-path-list';
   const error=make('div');error.setAttribute('role','alert');let parent=null,version=0,chosen='';
   function finish(value){chosen=value||'';dialog.close();}
   cancel.type='button';cancel.onclick=()=>finish('');dialog.oncancel=event=>{event.preventDefault();finish('');};
   dialog.onclose=()=>{version++;dialog.remove();active=null;resolve(chosen);};
   async function load(target){
    const request=++version;status.textContent='Opening folder…';error.replaceChildren();list.replaceChildren();go.disabled=up.disabled=drives.disabled=true;
    try{
     const data=await browse(target,filter.value);if(request!==version)return;
     location.value=data.path;parent=data.parent;list.replaceChildren();
     for(const folder of data.folders){const button=make('button',folder.name);button.type='button';button.className='video-path-folder';button.setAttribute('aria-label','Open folder '+folder.name);button.onclick=()=>{filter.value='';load(folder.path);};list.append(button);}
     for(const file of data.videos){const button=make('button'),name=make('span',file.name),size=make('small',(file.bytes/1048576).toFixed(1)+' MB');button.type='button';button.className='video-path-file';button.setAttribute('aria-label','Select video '+file.name);button.append(name,size);button.onclick=()=>finish(file.path);list.append(button);}
     status.textContent=data.truncated?'More files are available. Narrow the filename search.':data.videos.length+' videos · '+data.folders.length+' folders';
    }catch(problem){if(request!==version)return;const issue=window.storylensProblem?window.storylensProblem(problem):{message:problem.message};error.append(make('p',issue.message));const details=window.storylensDetails?.(issue);if(details)error.append(details);status.textContent='Check the folder path or choose Drives.';
    }finally{if(request===version){go.disabled=drives.disabled=false;up.disabled=!parent;}}
   }
   row.onsubmit=event=>{event.preventDefault();load(location.value);};up.onclick=()=>{filter.value='';load(parent);};drives.onclick=()=>{filter.value='';load('::drives::');};filter.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();load(location.value);}};
   dialog.append(head,row,filter,status,error,list);document.body.append(dialog);dialog.showModal();load(path);
  });return active;
 }
 return {open};
})();
