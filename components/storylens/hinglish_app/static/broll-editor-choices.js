(function(root){
 'use strict';
 function controller({api,wait=ms=>new Promise(resolve=>setTimeout(resolve,ms))}){
  let host=null,sending=false,connection={};
  return {
   get active(){return host;},
   async connect(editor){
    if(!['premiere','aftereffects','capcut'].includes(editor))throw Error('Choose an editing application.');
    if(sending)throw Error('Wait for the current editor receipt before changing the connection.');
    const result=await api({action:'connect',host:editor});host=editor;
    connection=result.transport?{transport:result.transport,context_id:result.context_id}:{};
    return result;
   },
   async select(value){
    if(!host)throw Error('Choose Premiere Pro, After Effects or CapCut first.');
    if(sending)throw Error('Wait for the current choice to finish.');
    sending=true;
    try{
     let result=await api({...value,...connection,action:'select',host});
     if(host==='capcut')return {...result,message:result.manifest?'New editable project prepared. Existing CapCut timeline items are not replaced.':'Choice saved for the new CapCut project.'};
     for(let n=0;n<30&&['queued','sent'].includes(result.status);n++){
      await wait(1000);result=await api({action:'status',id:result.id});
     }
     if(result.status!=='confirmed')throw Error(result.message||'The editor has not confirmed this choice. Retry the same choice to reconcile it.');
     return result;
    }finally{sending=false;}
   }
  };
 }
 function render(container,{api,onStatus,onConnect,initialEditor,hosts}){
  const c=controller({api});container.replaceChildren();
  for(const [host,name] of [['premiere','Premiere Pro'],['aftereffects','After Effects'],['capcut','CapCut']]){
   if(hosts&&!hosts.includes(host))continue;
   const button=document.createElement('button');button.type='button';button.textContent=name;
   button.className='editor-logo-button';button.setAttribute('aria-pressed','false');
   button.onclick=async()=>{button.disabled=true;try{
    const result=await c.connect(host);
    for(const other of container.querySelectorAll('button'))other.setAttribute('aria-pressed',String(other===button));
    onStatus(host==='capcut'?'CapCut · new editable project. Choose an option below.':name+' · '+result.name+'. Choose an option below.');
    if(onConnect)await onConnect(c);
   }catch(error){onStatus(error.message||String(error));}finally{button.disabled=false;}};
   container.append(button);
   if(host===initialEditor)setTimeout(()=>button.click(),0);
  }
  return c;
 }
 if(typeof module==='object'&&module.exports)module.exports={controller};
 else root.storylensBrollEditors={render};
})(typeof window==='undefined'?{}:window);
