(function(root){
 'use strict';
 let pending=null;
 function limit(orientation,value){
  const maximum=orientation==='horizontal'?2:5;
  return Math.max(1,Math.min(maximum,Number(value)||maximum));
 }
 function ask(){
  if(pending)return pending;
  const doc=root.document;
  if(!doc.getElementById('brollFormatStyle')){
   const style=doc.createElement('style');style.id='brollFormatStyle';
   style.textContent='.broll-format-dialog{background:#171a20;color:#f3f4f6;border:1px solid #46515b;border-radius:10px;padding:18px;max-width:calc(100vw - 32px)}.broll-format-dialog::backdrop{background:#0009}.broll-format-dialog h3{font:600 14px system-ui;margin:0 0 12px}.broll-format-actions{display:flex;gap:8px}.broll-format-actions button{display:flex;align-items:center;gap:8px;height:36px;padding:0 12px;background:#242932;border:1px solid #46515b;border-radius:6px;color:inherit;font:14px system-ui;cursor:pointer}.broll-format-actions button:focus-visible{outline:2px solid #ccd5de;outline-offset:2px}';
   doc.head.append(style);
  }
  let resolve;
  const promise=new Promise(done=>resolve=done);pending=promise;
  const dialog=doc.createElement('dialog');dialog.className='broll-format-dialog';dialog.setAttribute('aria-label','B-roll format');
  dialog.innerHTML='<h3>B-roll format</h3><div class="broll-format-actions"></div>';
  const finish=value=>{dialog.close();dialog.remove();pending=null;resolve(value);};
  for(const [value,label,w,h] of [['vertical','Vertical',10,16],['horizontal','Horizontal',16,10]]){
   const button=doc.createElement('button');button.type='button';button.dataset.orientation=value;
   button.innerHTML='<svg aria-hidden="true" width="18" height="18" viewBox="0 0 20 20"><rect x="'+((20-w)/2)+'" y="'+((20-h)/2)+'" width="'+w+'" height="'+h+'" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'+label;
   button.onclick=()=>finish(value);dialog.querySelector('div').append(button);
  }
  dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);},{once:true});
  doc.body.append(dialog);dialog.showModal();return promise;
 }
 root.storylensBrollFormat={ask,limit};
})(window);
