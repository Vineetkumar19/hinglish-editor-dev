/* Only Explorer-file Ctrl+V in AfterFX. No shell or keyboard injection. */
const path=require('path');
function createClipboardWatcher({root,parentPid=process.pid,onPaste,onState=()=>{},spawn=require('child_process').spawn}){
 let child=null,ready=false,buffer='',stderr='',timer=null,startPromise=null;
 function status(value){onState(value);return value;}
 function stop(){if(timer){clearTimeout(timer);timer=null;}const old=child;child=null;ready=false;startPromise=null;if(old)old.kill();return status({ok:true,enabled:false,message:'Keyboard paste is off.'});}
 function setEnabled(enabled){
  if(!enabled)return Promise.resolve(stop());
  if(ready)return Promise.resolve({ok:true,enabled:true,message:'Ctrl+V file paste is ready in After Effects.'});
  if(startPromise)return startPromise;
  buffer='';stderr='';
  startPromise=new Promise(resolve=>{
   let settled=false;
   const finish=value=>{if(settled)return;settled=true;if(timer){clearTimeout(timer);timer=null;}resolve(value);};
   const failed=details=>{const value={ok:false,enabled:false,message:'Keyboard paste could not start. Reopen the Storylens panel.',details:String(details||stderr)};finish(status(value));stop();};
   try{child=spawn(path.join(root,'.venv','Scripts','python.exe'),['-E','-X','utf8',path.join(root,'hinglish_app','adobe_clipboard.py'),'--parent-pid',String(parentPid)],{cwd:root,windowsHide:true,shell:false,stdio:['ignore','pipe','pipe']});}
   catch(error){failed(error.message);return;}
   const current=child;
   current.stderr.on('data',data=>{stderr=(stderr+String(data)).slice(-4000);});
   current.on('error',error=>{if(child===current)failed(error.message);});
   current.on('exit',()=>{if(child===current){child=null;ready=false;startPromise=null;finish(status({ok:false,enabled:false,message:'Keyboard paste stopped. Reopen the Storylens panel.',details:stderr}));}});
   current.stdout.on('data',data=>{
    if(child!==current)return;buffer+=String(data);if(buffer.length>131072){failed('Oversized helper response');return;}
    let newline;while((newline=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,newline);buffer=buffer.slice(newline+1);let value;try{value=JSON.parse(line);}catch(_){continue;}
     if(value.event==='ready'){ready=true;finish(status({ok:true,enabled:true,message:'Ctrl+V file paste is ready in After Effects.'}));}
     else if(value.event==='error'){failed(value.details||value.message);}
     else if(ready&&value.event==='paste'&&typeof value.request_id==='string'&&value.request_id.length<100&&Array.isArray(value.paths)&&value.paths.length===1&&typeof value.paths[0]==='string'&&value.paths[0].length<32768){onPaste({request_id:value.request_id,paths:value.paths});}
    }
   });
   timer=setTimeout(()=>failed('Keyboard helper did not become ready'),7000);
  });
  return startPromise;
 }
 return {setEnabled,stop};
}
module.exports={createClipboardWatcher};
