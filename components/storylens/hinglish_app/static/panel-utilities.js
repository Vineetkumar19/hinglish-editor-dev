/* Compact Adobe-only utility controls; standalone pages retain their layout. */
(()=>{
 const q=new URLSearchParams(location.search);if(q.get('panel')!=='1')return;
 const $=id=>document.getElementById(id),make=(cls)=>{const el=document.createElement('div');el.className=cls;return el;};
 if($('downloadForm')&&document.documentElement.dataset.downloadQueue==='1'){
  document.documentElement.classList.add('queue-panel');
 }else if($('downloadForm')){
  document.documentElement.classList.add('compact-download');if(['aftereffects','premiere'].includes(q.get('host')))document.documentElement.classList.add('native-download');
  const form=$('downloadForm'),row=make('panel-download-row');
  for(const [id,label]of[['downloadMode','Format'],['downloadQuality','Quality']])$(id).setAttribute('aria-label',label);
  const format=$('downloadMode').parentElement,quality=$('qualityField'),start=$('startDownload');start.textContent='Download';row.append(format,quality,start);
  form.insertBefore(row,$('downloadUrl').nextSibling);$('downloadUrl').setAttribute('aria-label','Video link');
  const heading=$('downloadTitle').parentElement,selector=$('chooseVideo').parentElement;
  if(document.documentElement.classList.contains('native-download')){
   const result=$('downloadResult'),layout=make('panel-download-result'),preview=make('panel-download-preview'),copy=make('panel-download-copy');
   preview.append($('videoPreview'),$('audioPreview'));copy.append(heading,selector,$('assetSummary'));layout.append(preview,copy);result.insertBefore(layout,result.firstChild);
  }else heading.append(selector);
  const delivery=make('native-download-status');delivery.id='nativeDownloadStatus';delivery.setAttribute('role','status');$('assetSummary').after(delivery);

 }else if($('photoForm')&&document.documentElement.dataset.photoFlow!=='selective'){
  document.documentElement.classList.add('compact-photos');
  const form=$('photoForm'),first=make('panel-photo-input'),second=make('panel-photo-history');
  $('dropTitle').textContent='Choose screenshot';$('collectPhotos').textContent='Submit';
  $('photoQuality').value='0';$('photoQuality').setAttribute('aria-hidden','true');
  first.append($('photoDrop'),$('collectPhotos'));form.insertBefore(first,form.firstChild);
  $('savedPhotos').setAttribute('aria-label','Saved collections and Trash');
  $('refreshPhotos').textContent='Refresh';$('trashPhotos').textContent='Trash';$('restorePhotos').textContent='Restore';
  second.append($('savedPhotos'),$('refreshPhotos'),$('trashPhotos'),$('restorePhotos'));first.after(second);
 }
})();
