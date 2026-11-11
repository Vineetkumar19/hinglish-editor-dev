/* Browser controls use the existing installed panel's complete native dispatch. */
(()=>{
 const token=document.documentElement.dataset.token;
 async function api(path,body){const r=await window.storylensFetch('/api/native-tools/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(body?{body:JSON.stringify(body)}:{})});return window.storylensResponse(r);}
 const pending=new Map();let stopped=false,chain=Promise.resolve();
 window.storylensBrowserNative={
  request(host,action,payload){
   const reads={animationPresets:['catalog'],effectsLibrary:['catalog'],cinematicText:['catalog'],presetLibrary:['categories','catalog','motionCatalog','toolkitCatalog']};
   if(reads[action]?.includes(payload?.action))return api('catalog',{action,payload});
   const execute=async()=>{
   if(action==='presetLibrary'&&['gallery','galleryStatus'].includes(payload?.action)){const state=await api('connections');if(!state.connections.some(c=>c.host===host))return api('catalog',{action,payload});}
   const key=action+JSON.stringify(payload),old=pending.get(key),request_id=old||crypto.randomUUID();pending.set(key,request_id);
   let row=await api('command',{host,action,payload,request_id});
   while(['queued','sent'].includes(row.status)&&!stopped){await new Promise(r=>setTimeout(r,700));row=await api('status?id='+row.id);}
   if(stopped)throw Error('The browser panel closed. Check the editor before repeating this action.');
   if(row.status!=='confirmed'){if(row.status==='failed')pending.delete(key);throw Error(row.error||'The editor has not confirmed this action. Check its current project.');}
   pending.delete(key);return row.result;
   };const next=chain.catch(()=>{}).then(execute);chain=next;return next;
  },
  listen({host,native,isBusy,onError}){
   const client=crypto.randomUUID();let identity=null,timer=null,alive=true,delivering=false;
   async function poll(){
    if(!alive)return;
    try{
     if(!isBusy()&&!delivering){
      if(!identity){const project=await native('projectContext');identity=await api('register',{client,host,project_id:project.project_id});}
      const {command}=await api('poll',identity);
      if(command){
       delivering=true;let result,error;
       try{const current=await native('projectContext');if(current.project_id!==command.project_id){identity=await api('register',{client,host,project_id:current.project_id});throw Error('The editor project changed. Check the intended project, then retry.');}result=await native(command.action,command.payload);}
       catch(e){error=String(e.message||e);}
       await api('receipt',{...identity,id:command.id,result,error});
       // Save As may change the project identity. Confirm the completed command
       // first, then refresh registration for subsequent requests. Never replay.
       const after=await native('projectContext');
       identity=await api('register',{client,host,project_id:after.project_id});
       delivering=false;
      }
     }
    }catch(e){identity=null;delivering=false;/* disconnected state is shown by the requesting browser */}
    if(alive)timer=setTimeout(poll,1500);
   }
   poll();return {stop(){alive=false;clearTimeout(timer);},isRunning:()=>delivering};
  }
 };
 window.addEventListener('beforeunload',()=>{stopped=true;});
})();
