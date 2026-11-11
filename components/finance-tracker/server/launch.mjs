import {spawn} from 'node:child_process';
import {mkdirSync,openSync,closeSync,appendFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
const url='http://127.0.0.1:4310';
async function healthy(){try{const r=await fetch(url+'/api/health',{signal:AbortSignal.timeout(1500)});const health=await r.json();return health.service==='finance-tracker'||health.name==='Daybook';}catch{return false;}}
try{
 mkdirSync('data',{recursive:true});
 if(!await healthy()){
  const out=openSync('data/server.log','a'),err=openSync('data/server-error.log','a');
  const child=spawn(process.execPath,['server/bootstrap.mjs'],{cwd:process.cwd(),windowsHide:true,detached:true,stdio:['ignore',out,err]});
  child.on('error',e=>appendFileSync('data/launcher-error.log',e.message+'\n'));child.unref();closeSync(out);closeSync(err);
 }
 let ready=false;for(let i=0;i<30;i++){if(await healthy()){ready=true;break;}await new Promise(r=>setTimeout(r,300));}
 if(!ready)throw new Error('Finance Tracker did not start. See data/server-error.log.');
 if(!process.argv.includes('--no-browser')){const browser=spawn('rundll32.exe',['url.dll,FileProtocolHandler',url],{windowsHide:true,detached:true,stdio:'ignore'});browser.on('error',e=>appendFileSync('data/launcher-error.log',e.message+'\n'));browser.unref();}
 console.log('Finance Tracker ready: '+url);
}catch(e){appendFileSync('data/launcher-error.log',new Date().toISOString()+' '+e.stack+'\n');console.error(e.message);process.exitCode=1;}
