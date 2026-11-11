(function(root){
 'use strict';
 async function deliver(command,native,ack){
  if(command?.manifest?.type!=='timed_choice'||command.manifest.operation_id!==command.id)throw Error('Reconnect this saved timed choice.');
  let receipt;
  try{receipt=await native('import',command.manifest);if(!receipt?.ok)throw Error('The editor has not confirmed this choice.');}
  catch(error){return ack({id:command.id,error:String(error.message||error)});}
  return ack({id:command.id,receipt});
 }
 function create({api,native,isBusy,onError}){
  const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
  const client=Array.from(bytes,n=>n.toString(16).padStart(2,'0')).join('');
  let generation=0,timer=null;
  async function start(context){
   const mine=++generation;clearTimeout(timer);
   const connected=await api('/api/panel/broll-native',{action:'register',client,context_id:context.id});
   const identity={lease:connected.lease,client};
   async function poll(){
    if(mine!==generation)return;
    try{if(!isBusy()){
      const {command}=await api('/api/panel/broll-native',{action:'poll',...identity});
      if(command)await deliver(command,native,value=>api('/api/panel/broll-native',{action:'receipt',...identity,...value}));
    }}catch(error){onError(error);}
    if(mine===generation)timer=setTimeout(poll,2000);
   }
   timer=setTimeout(poll,200);return connected;
  }
  return {start,stop(){generation++;clearTimeout(timer);}};
 }
 if(typeof module==='object'&&module.exports)module.exports={deliver,create};
 else root.storylensTimedChoicePanel={create};
})(typeof window==='undefined'?{}:window);
