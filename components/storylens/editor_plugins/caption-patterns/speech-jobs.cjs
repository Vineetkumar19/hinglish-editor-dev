/* Node side of the existing native bridge. Saved jobs survive panel refresh; no shell or AE edits. */
const fs=require('fs'),path=require('path'),crypto=require('crypto'),processes=new Map();
const valid=id=>typeof id==='string'&&/^[a-f0-9]{32}$/.test(id);
function folder(root,id){if(!valid(id))throw Error('Choose the saved speech timing request.');return path.join(root,'output/captions/ae-speech',id);}
function read(file){return JSON.parse(fs.readFileSync(file,'utf8'));}
function save(file,value){const tmp=file+'.'+crypto.randomBytes(6).toString('hex')+'.tmp';fs.writeFileSync(tmp,JSON.stringify(value,null,2));fs.renameSync(tmp,file);}
function fail(dir,details){let value=read(path.join(dir,'status.json'));if(['complete','failed'].includes(value.status))return;save(path.join(dir,'status.json'),{...value,status:'failed',stage:'Speech timing stopped',error:{code:'editing_worker_crashed',message:'The local speech worker stopped. Your script and saved audio are kept. Check Technical details and retry Generate captions.',details}});}
function status(root,id){const dir=folder(root,id),file=path.join(dir,'status.json');if(!fs.existsSync(file))throw Error('This saved speech timing task is unavailable. Generate captions again.');let value=read(file);if(!['complete','failed'].includes(value.status)&&!processes.has(dir)){const lease=path.join(dir,'worker.json');if(fs.existsSync(lease)){try{process.kill(read(lease).pid,0);}catch(error){if(error.code==='ESRCH')fail(dir,'The saved speech worker is no longer running.');}}else fail(dir,'The speech worker did not start.');value=read(file);}return value;}
function start(root,input,options={}){
 const dir=folder(root,input.request_id),ctx=input.context,capture=input.timing_context;
 if(typeof input.script!=='string'||!input.script.trim()||input.script.length>6000||input.script.trim().split(/\s+/).length>1000)throw Error('Paste the final spoken script (up to 6,000 characters).');
 if(!ctx||!/^\d+$/.test(ctx.comp_id||'')||!ctx.project_id||!capture||capture.project_id!==ctx.project_id||String(capture.sequence_id)!==ctx.comp_id)throw Error('The composition changed. Return to the intended caption timeline and retry.');
 if(!Number.isFinite(capture.duration)||capture.duration<=0||capture.duration>3600||capture.unsupported?.length||!Array.isArray(capture.clips)||!capture.clips.length||capture.clips.length>1000)throw Error('Enable straight narration audio in this composition and retry Speech timing. Existing layers are kept.');
 for(const clip of capture.clips){if(typeof clip.path!=='string'||/^(?:\\\\|\/\/|[a-z]+:\/\/)/i.test(clip.path)||!path.isAbsolute(clip.path)||!fs.existsSync(clip.path)||!fs.statSync(clip.path).isFile())throw Error('Relink the local narration file and retry Speech timing.');}
 const request={script:input.script,context:ctx,timing_context:capture},content=JSON.stringify(request),file=path.join(dir,'request.json');
 if(fs.existsSync(file)){if(JSON.stringify(read(file))!==content)throw Error('This timing request changed. Generate a new version.');return status(root,input.request_id);}
 const python=path.join(root,'.venv/Scripts/python.exe');if(!fs.existsSync(python))throw Error('The local speech runtime is unavailable. Restore the Storylens Python environment and retry.');
 fs.mkdirSync(dir,{recursive:true});save(file,request);save(path.join(dir,'status.json'),{id:input.request_id,status:'queued',stage:'Waiting for the local speech queue',progress:0});
 const log=fs.openSync(path.join(dir,'worker.log'),'a');let child;
 try{child=(options.spawn||require('child_process').spawn)(python,['-u','-m','hinglish_app.caption_native_timing','--root',root,'--id',input.request_id],{cwd:root,windowsHide:true,shell:false,stdio:['ignore',log,log],env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONUNBUFFERED:'1',OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1',MKL_NUM_THREADS:'1'}});processes.set(dir,child);save(path.join(dir,'worker.json'),{pid:child.pid,started:Date.now()});child.on('error',e=>{processes.delete(dir);fail(dir,String(e));});child.on('exit',(code,signal)=>{processes.delete(dir);let tail='';try{tail=fs.readFileSync(path.join(dir,'worker.log'),'utf8').slice(-12000);}catch(_){}fail(dir,'Worker exit '+code+(signal?' '+signal:'')+'\n'+tail);});}
 catch(e){processes.delete(dir);fail(dir,String(e));throw e;}finally{fs.closeSync(log);}
 return status(root,input.request_id);
}
module.exports={start,status};
