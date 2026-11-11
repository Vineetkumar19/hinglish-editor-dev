importScripts('stock.js');
const origins={pexels:'https://www.pexels.com/*',pixabay:'https://pixabay.com/*'};
let busy=false,config=null;
const running=new Set();
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function settings(){return config||(config=await chrome.storage.local.get(['port','key','client','tabs']));}
async function call(action,body){
 const c=await settings();if(!c.key||!Number.isInteger(c.port)||c.port<1024||c.port>65535)throw Error('Connect Stock Search from its popup.');
 const response=await fetch('http://127.0.0.1:'+c.port+'/api/stock-browser/worker/'+action,{method:'POST',redirect:'error',signal:AbortSignal.timeout(8000),headers:{'Content-Type':'application/json','X-Storylens-Stock':c.key},body:JSON.stringify({client:c.client,...body})});
 const value=await response.json();if(!response.ok)throw Error(value.error||'Reconnect Stock Search.');return value;
}
async function providers(){const found=[];for(const [name,origin] of Object.entries(origins))if(await chrome.permissions.contains({origins:[origin]}))found.push(name);return found;}
async function hello(){return call('hello',{version:chrome.runtime.getManifest().version,providers:await providers()});}
function publicWorkingPage(provider,value){try{const u=new URL(value);return u.origin===origins[provider].slice(0,-2)&&(Stock.videoPage(provider,value)||(provider==='pexels'?/^\/search\/videos\/[^/]+\/$/:/^\/videos\/search\/[^/]+\/$/).test(u.pathname));}catch(_){return false;}}
async function navigate(provider,url){
 const c=await settings();c.tabs=c.tabs||{};let tab=null;
 if(c.tabs[provider])try{tab=await chrome.tabs.get(c.tabs[provider]);if(!publicWorkingPage(provider,tab.url))tab=null;}catch(_){}
 if(tab)tab=await chrome.tabs.update(tab.id,{url,muted:true});
 else{tab=await chrome.tabs.create({url,active:false});c.tabs[provider]=tab.id;await chrome.tabs.update(tab.id,{muted:true});await chrome.storage.local.set({tabs:c.tabs});}
 for(let n=0;n<14;n++){await pause(500);const t=await chrome.tabs.get(tab.id);if(t.status==='complete')break;}
 return tab.id;
}
async function read(id,provider,kind){
 let timer;
 const values=await Promise.race([chrome.scripting.executeScript({target:{tabId:id},func:Stock.scrape,args:[provider,kind]}),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('The stock page did not respond. Other websites continue.')),10000);})]).finally(()=>clearTimeout(timer));
 return values[0]?.result||{state:'failed',message:'The public video page could not be read.'};
}
async function collect(task){
 const started=Date.now(),results=[];let id=await navigate(task.provider,Stock.searchUrl(task.provider,task.query,task.orientation));
 let search=await read(id,task.provider,'search');
 if(search.state==='needs_verification'){await chrome.tabs.update(id,{active:true});return {state:search.state,results};}
 if(search.state==='failed')return {...search,results};
 if(!search.links?.length){await pause(1200);search=await read(id,task.provider,'search');}
 for(const page of search.links||[]){
  if(results.length>=task.limit||Date.now()-started>82000)break;
  if(!Stock.videoPage(task.provider,page))continue;
  await hello();id=await navigate(task.provider,page);let detail;
  for(let n=0;n<4;n++){
   detail=await read(id,task.provider,'detail');
   if(detail.state==='needs_verification'){await chrome.tabs.update(id,{active:true});return {state:detail.state,results};}
   if(detail.state==='failed'||detail.result?.media_url)break;
   await pause(600);
  }
  const row=detail?.result;if(!row||!Stock.media(task.provider,row.media_url))continue;
  if(row.width&&row.height&&(task.orientation==='vertical'&&!(row.height>row.width)||task.orientation==='horizontal'&&!(row.width>row.height)))continue;
  if(!results.some(r=>r.media_url===row.media_url))results.push(row);
 }
 return {state:'complete',results};
}
async function tick(){
 if(busy)return;busy=true;
 try{
  const c=await settings();if(!c.key)return;
  const connection=await hello();
  const perform=async task=>{
   let result;try{result=await collect(task);}catch(e){result={state:'failed',results:[],message:String(e.message).slice(0,700)};}
   await call('finish',{id:task.id,lease:task.lease,...result});
  };
  if(!Stock.parallelReady(connection,chrome.runtime.getManifest().version)){
   const {task}=await call('claim',{});if(task)await perform(task);return;
  }
  await Stock.launchReady(await providers(),running,
   async provider=>(await call('claim',{provider})).task,
   perform,e=>{void chrome.storage.local.set({lastError:String(e.message).slice(0,700)});});
 }catch(e){await chrome.storage.local.set({lastError:String(e.message).slice(0,700)});}
 finally{busy=false;setTimeout(tick,2500);}
}
chrome.runtime.onMessageExternal.addListener((message,sender,reply)=>{
 if(!message||message.type!=='pair'||!Stock.pairSender(sender.url,message.port)||typeof message.key!=='string'||!/^[a-zA-Z0-9_-]{40,80}$/.test(message.key)){reply({error:'Open the local Storylens stock connection page.'});return false;}
 (async()=>{
  const enabled=await providers();if(!enabled.length)throw Error('Enable Pexels and Pixabay in the Stock Search popup first.');
  config={port:message.port,key:message.key,client:crypto.randomUUID(),tabs:{}};
  await chrome.storage.local.set(config);const status=await hello();reply({connected:status.connected});void tick();
 })().catch(e=>reply({error:e.message}));return true;
});
chrome.runtime.onMessage.addListener((m,sender,reply)=>{
 if(sender.id!==chrome.runtime.id)return false;
 if(m?.type==='check'){tick().then(()=>reply({ok:true}));return true;}
 return false;
});
chrome.alarms.create('stock-poll',{periodInMinutes:.5});
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='stock-poll')void tick();});
chrome.runtime.onStartup.addListener(()=>void tick());
void tick();
