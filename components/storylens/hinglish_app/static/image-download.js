(()=>{
 window.storylensImageDownload=function(options){
  const $=id=>document.getElementById(id),status=$('imageDownloadStatus'),retry=$('imageDownloadRetry');
  let current=null,busy=false,lastPaste=0;
  function controls(){for(const id of ['imageDownloadPaste','imageDownloadSubmit','imageDownloadRetry'])$(id).disabled=busy;}
  function show(row){current=row;localStorage.setItem('storylens.directImage',row.id);$('imageDownloadPreview').hidden=false;$('imageDownloadImage').src='/api/panel/image-file?'+new URLSearchParams({id:row.id,kind:'native',token:options.token});}
  async function add(row,target){
   const manifest=await options.api('/api/panel/image-import',{id:row.id,context_id:target.id});
   const receipt=await options.native('imageDownload',manifest);
   if(!receipt?.ok)throw Object.assign(Error(receipt?.error||'Image saved; adding it failed.'),{code:receipt?.code,details:receipt?.details});
   await options.api('/api/panel/image-receipt',{id:row.id,context_id:target.id,receipt});
   await options.enableCopy();retry.hidden=true;
   status.textContent=receipt.ui_cleanup?.ok===false?'Saved; folders could not close.':'Saved.';
  }
  async function receive(load){
   if(busy)return;busy=true;controls();retry.hidden=true;options.clearError();status.textContent='Saving…';$('imageDownloadPreview').hidden=true;current=null;
   try{const target=await options.captureProject(),row=await load();show(row);await add(row,target);}
   catch(e){retry.hidden=!current;status.textContent=current?'Saved. Import failed.':'Could not save image.';options.showError(e);}
   finally{busy=false;controls();}
  }
  const clipboard=()=>receive(()=>options.api('/api/panel/image-clipboard',{}));
  const upload=file=>receive(async()=>{if(file.size>25*1024*1024)throw Error('Choose an image smaller than 25 MB.');return window.storylensResponse(await window.storylensFetch('/api/panel/image-upload',{method:'POST',headers:{'X-Hinglish-Token':options.token,'Content-Type':file.type||'application/octet-stream'},body:file}));});
  $('imageDownloadForm').onsubmit=event=>{event.preventDefault();const url=$('imageDownloadUrl').value.trim();if(url)receive(()=>options.api('/api/panel/image-download',{url}));};
  $('imageDownloadPaste').onclick=clipboard;
  document.addEventListener('paste',event=>{if(document.body.dataset.mode!=='imageDownload')return;const item=[...(event.clipboardData?.items||[])].find(item=>item.kind==='file'&&item.type.startsWith('image/'));if(item){event.preventDefault();lastPaste=Date.now();const file=item.getAsFile();if(file)upload(file);}else{const html=event.clipboardData?.getData('text/html')||'';if(/<img\b/i.test(html)){event.preventDefault();lastPaste=Date.now();receive(()=>options.api('/api/panel/image-clipboard-html',{html}));}}});
  document.addEventListener('keydown',event=>{if(document.body.dataset.mode!=='imageDownload'||!(event.ctrlKey||event.metaKey)||event.altKey||event.shiftKey||event.repeat)return;const key=event.key.toLowerCase();if(key==='b'){event.preventDefault();clipboard();}else if(key==='v'&&event.target.id!=='imageDownloadUrl'){const stamp=Date.now();setTimeout(()=>{if(!busy&&lastPaste<stamp)clipboard();},180);}});
  retry.onclick=async()=>{if(!current||busy)return;busy=true;controls();options.clearError();try{await add(current,await options.captureProject());}catch(e){status.textContent='Saved. Import failed.';options.showError(e);}finally{busy=false;controls();}};
  const previous=localStorage.getItem('storylens.directImage');if(previous)options.api('/api/panel/image-download?id='+encodeURIComponent(previous)).then(row=>{if(!current&&!busy)show(row);}).catch(()=>{});
 };
})();
