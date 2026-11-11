/* Opt-in Storylens commands in AE/Explorer only. No remapping or input injection. */
const path=require('path');
function createShortcutWatcher({root,parentPid=process.pid,onShortcut,onState=()=>{},spawn=require('child_process').spawn}){
 let child=null,ready=false,buffer='',stderr='',timer=null,startPromise=null,cancelStart=null,closing=null,stopPromise=null,generation=0,desired=false;
 function status(value){onState(value);return value;}
 function stop(){desired=false;++generation;if(closing)return stopPromise;if(cancelStart)cancelStart();if(timer){clearTimeout(timer);timer=null;}const old=child;child=null;ready=false;startPromise=null;if(!old)return Promise.resolve(status({ok:true,enabled:false}));
  closing=old;stopPromise=new Promise(resolve=>{let closed=false,deadline;const finish=value=>{if(closed)return;closed=true;clearTimeout(deadline);resolve(status(value));};
   old.once('exit',()=>{closing=null;stopPromise=null;finish({ok:true,enabled:false,message:'Storylens shortcuts are off.'});});
   if(old.stdin?.end){deadline=setTimeout(()=>finish({ok:false,enabled:false,message:'The shortcut listener has not confirmed shutdown. Close Storylens before turning shortcuts on again.'}),2000);old.stdin.end('stop\n');}
   else{old.kill();closing=null;finish({ok:true,enabled:false});}
  });return stopPromise;}
 function setEnabled(enabled,expected){
  if(expected===undefined){desired=!!enabled;expected=++generation;}else if(expected!==generation||!desired)return Promise.resolve({ok:true,enabled:false});
  if(!enabled)return Promise.resolve(stop());
  if(closing)return stopPromise.then(result=>result.ok?setEnabled(true,expected):result);
  if(ready)return Promise.resolve({ok:true,enabled:true,message:'Storylens shortcuts are ready in AE and Explorer.'});
  if(startPromise)return startPromise;
  buffer='';stderr='';
  startPromise=new Promise(resolve=>{
   let settled=false;
   const finish=value=>{if(settled)return;settled=true;cancelStart=null;if(timer){clearTimeout(timer);timer=null;}resolve(value);};
   cancelStart=()=>finish({ok:true,enabled:false});
   const failed=details=>{const value={ok:false,enabled:false,message:'Storylens shortcuts could not start. Reopen the Storylens panel.',details:String(details||stderr)};finish(status(value));stop();};
   try{child=spawn(path.join(root,'.venv','Scripts','python.exe'),['-E','-X','utf8','-m','hinglish_app.adobe_shortcuts','--parent-pid',String(parentPid)],{cwd:root,windowsHide:true,shell:false,stdio:['pipe','pipe','pipe']});}
   catch(error){failed(error.message);return;}
   const current=child;
   current.stderr.on('data',data=>{stderr=(stderr+String(data)).slice(-4000);});
   current.on('error',error=>{if(child===current)failed(error.message);});
   current.on('exit',()=>{if(child===current){child=null;ready=false;startPromise=null;finish(status({ok:false,enabled:false,message:'Storylens shortcuts stopped. Reopen the Storylens panel.',details:stderr}));}});
   current.stdout.on('data',data=>{
    if(child!==current)return;buffer+=String(data);if(buffer.length>131072){failed('Oversized helper response');return;}
    let newline;while((newline=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,newline);buffer=buffer.slice(newline+1);let value;try{value=JSON.parse(line);}catch(_){continue;}
     if(value.event==='ready'){ready=true;finish(status({ok:true,enabled:true,message:'Storylens shortcuts are ready in AE and Explorer.'}));}
     else if(value.event==='error'){failed(value.details||value.message);}
     else if(ready&&value.event==='shortcut'&&typeof value.request_id==='string'&&value.request_id.length<100&&['copy','paste','undo'].includes(value.command)&&['project','explorer'].includes(value.source)&&Number.isSafeInteger(value.window_handle)&&value.window_handle>0){onShortcut(value);}
    }
   });
   timer=setTimeout(()=>failed('Shortcut listener did not become ready'),7000);
  });
  return startPromise;
 }
 return {setEnabled,stop};
}
module.exports={createShortcutWatcher};

