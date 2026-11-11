/* Small on-demand viewport helper, reused only during a burst of Paste actions. */
const path=require('path');
function record(root,phase,value){try{const fs=require('fs'),folder=path.join(root,'cache','editor-panel');fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,'project-view-'+phase+'.json'),JSON.stringify({time:Date.now(),...value},null,2));}catch(_){}}
function createClient(root,{spawn=require('child_process').spawn,idleMs=15000,leaseMs=60000,timeoutMs=4000}={}){
 let child=null,pending=new Map(),sequence=0,idle=null,buffer='';
 const unavailable=details=>({ok:false,reason:'scroll-unavailable',details:String(details||'Viewport helper stopped').slice(0,800)});
 function stop(reason='Viewport helper stopped'){
  clearTimeout(idle);idle=null;const old=child;child=null;buffer='';
  for(const waiter of pending.values()){clearTimeout(waiter.timer);waiter.resolve(unavailable(reason));}pending.clear();
  if(old)try{old.kill();}catch(_){}
 }
 function armIdle(delay=idleMs){clearTimeout(idle);if(!pending.size){idle=setTimeout(()=>stop(),delay);idle.unref?.();}}
 function start(){
  if(child)return child;
  const owned=spawn(path.join(root,'.venv','Scripts','python.exe'),['-E','-X','utf8','-u','-m','hinglish_app.adobe_project_view','--worker'],{cwd:root,windowsHide:true,shell:false,stdio:['pipe','pipe','pipe']});
  child=owned;
  owned.stdout.on('data',chunk=>{
   if(child!==owned)return;buffer+=String(chunk);if(buffer.length>131072){stop('Viewport response is too large');return;}
   let split;while((split=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,split);buffer=buffer.slice(split+1);let message;try{message=JSON.parse(line);}catch(_){stop('Viewport helper returned an unreadable response');return;}
    const waiter=pending.get(message.id);if(!waiter)continue;pending.delete(message.id);clearTimeout(waiter.timer);waiter.resolve(message.result||unavailable());armIdle(waiter.action==='capture'?leaseMs:idleMs);
   }
  });
  owned.stderr.on('data',()=>{});owned.stdin.on('error',e=>{if(child===owned)stop(e.message);});owned.on('error',e=>{if(child===owned)stop(e.message);});owned.on('exit',()=>{if(child===owned)stop();});
  return owned;
 }
 async function request(action,projectId,snapshot){
  if(typeof projectId!=='string'||!path.win32.isAbsolute(projectId))return {ok:false,reason:'project-unavailable'};
  const started=Date.now(),id=++sequence;clearTimeout(idle);
  const answer=await new Promise(resolve=>{
   try{const owned=start(),timer=setTimeout(()=>stop('Viewport helper timed out'),timeoutMs);timer.unref?.();pending.set(id,{resolve,timer,action});
    owned.stdin.write(JSON.stringify({id,action,project_id:projectId,snapshot})+'\n',e=>{if(e&&child===owned)stop(e.message);});
   }catch(e){stop(e.message);resolve(unavailable(e.message));}
  });
  const result={...answer,elapsed_ms:Date.now()-started};record(root,action,result);return result;
 }
 return {capture:projectId=>request('capture',projectId),restore:snapshot=>request('restore',snapshot?.project_id,snapshot),stop};
}
const clients=new Map();
function client(root){if(!clients.has(root))clients.set(root,createClient(root));return clients.get(root);}
module.exports={createClient,capture:(root,projectId)=>client(root).capture(projectId),restore:(root,snapshot)=>client(root).restore(snapshot),recordTiming:(root,value)=>record(root,'paste-timing',value),stop:()=>{for(const c of clients.values())c.stop();clients.clear();}};
