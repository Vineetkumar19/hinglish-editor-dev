/* Fixed stock-page policy. This same DOM reader is injected as a packaged function;
   no model-authored code, page fetches, cookies or account state are evaluated. */
(function(root){
 'use strict';
 const hosts={pexels:'www.pexels.com',pixabay:'pixabay.com'};
 function videoPage(provider,value){try{const u=new URL(value);return u.protocol==='https:'&&u.host===hosts[provider]&&
  (provider==='pexels'?/^\/video\/[a-z0-9-]+-\d+\/$/:/^\/videos\/[a-z0-9-]+-\d+\/$/).test(u.pathname)&&!u.username&&!u.password;}catch(_){return false;}}
 function media(provider,value){try{const u=new URL(value);return u.protocol==='https:'&&u.host===(provider==='pexels'?'videos.pexels.com':'cdn.pixabay.com')&&/\.mp4$/i.test(u.pathname)&&!u.username&&!u.password;}catch(_){return false;}}
 function searchUrl(provider,query,orientation){
  if(!hosts[provider]||typeof query!=='string'||!query.trim()||query.length>120||/[\x00-\x1f]/.test(query)||![null,undefined,'vertical','horizontal'].includes(orientation))throw Error('Choose a stock website, keyword and video format.');
  const base=provider==='pexels'?'https://www.pexels.com/search/videos/':'https://pixabay.com/videos/search/';
  return base+encodeURIComponent(query.trim())+'/'+(provider==='pexels'&&orientation?'?orientation='+(orientation==='vertical'?'portrait':'landscape'):'');
 }
 function pairSender(url,port){try{const u=new URL(url);return Number.isInteger(port)&&port>=1024&&port<=65535&&u.origin==='http://127.0.0.1:'+port&&u.pathname==='/stock-browser.html';}catch(_){return false;}}
 function scrape(provider,kind){
  // Everything below is self-contained for chrome.scripting.executeScript.
  const host=provider==='pexels'?'www.pexels.com':provider==='pixabay'?'pixabay.com':'';
  const pattern=provider==='pexels'?/^\/video\/[a-z0-9-]+-\d+\/$/:/^\/videos\/[a-z0-9-]+-\d+\/$/;
  const safePage=value=>{try{const u=new URL(value,location.href);return u.protocol==='https:'&&u.host===host&&pattern.test(u.pathname)&&!u.username&&!u.password?u.origin+u.pathname:'';}catch(_){return '';}};
  const safeMedia=value=>{try{const u=new URL(value);return u.protocol==='https:'&&u.host===(provider==='pexels'?'videos.pexels.com':'cdn.pixabay.com')&&/\.mp4$/i.test(u.pathname)&&!u.username&&!u.password?u.href:'';}catch(_){return '';}};
  const current=new URL(location.href);
  if(!host||current.protocol!=='https:'||current.host!==host)return {state:'failed',message:'Stock tab left the supported website.'};
  const text=(document.body?.innerText||'').slice(0,18000);
  if(/verify (?:that )?you are human|checking your browser|performing security verification|access denied|attention required|just a moment/i.test(document.title+' '+text))return {state:'needs_verification'};
  if(kind==='search')return {state:'complete',links:[...new Set([...document.querySelectorAll('a[href]')].map(a=>safePage(a.href)).filter(Boolean))].slice(0,24)};
  const page=safePage(location.href);if(!page)return {state:'failed',message:'Open a public video detail page.'};
  const title=(document.querySelector('h1')?.textContent||document.title||'Stock video').trim().slice(0,300);
  const id=page.match(/-(\d+)\/$/)[1];
  const belongs=url=>{const path=url?new URL(url).pathname:'';return provider==='pexels'?path.includes('/'+id+'/'):new RegExp('/'+id+'-').test(path);};
  const result=(url,v={})=>{
   const filename=new URL(url).pathname.match(/[_-](\d{3,4})_(\d{3,4})(?:_|\.)/);
   return {state:'complete',result:{page_url:page,media_url:url,title,width:v.videoWidth||Number(filename?.[1]||0),height:v.videoHeight||Number(filename?.[2]||0),duration:Number.isFinite(v.duration)&&v.duration<=1800?v.duration:0,thumbnail:v.poster||''}};
  };
  for(const v of document.querySelectorAll('video')){
   const url=safeMedia(v.currentSrc||v.src||[...v.querySelectorAll?.('source[src]')||[]].map(s=>s.src).find(s=>safeMedia(s))||'');
   if(url&&belongs(url))return result(url,v);
  }
  // Both sites advertise the selected public MP4 in their visible Canva edit
  // link even when background-tab autoplay has not loaded the player. Read
  // that link only; never visit Canva, replay session data, or fetch an API.
  for(const a of document.querySelectorAll('a[href]')){
   try{
    const u=new URL(a.href),external=u.searchParams.get('external-id');
    if(u.protocol!=='https:'||u.host!=='www.canva.com'||u.pathname!=='/content-partner/'||external!==(provider==='pexels'?id:'video:'+id))continue;
    const url=safeMedia(u.searchParams.get('file-url')||'');
    if(url&&belongs(url))return result(url);
   }catch(_){}
  }
  return {state:'complete',result:null};
 }
 function parallelReady(status,version){
  const v=String(version).split('.').map(Number);
  return status?.parallel_provider_claims===true&&v.length===3&&v.every(Number.isInteger)&&(v[0]>0||v[0]===0&&(v[1]>1||v[1]===1&&v[2]>=2));
 }
 async function launchReady(providers,active,claim,perform,onError){
  const started=[];
  for(const provider of providers){
   if(!hosts[provider]||active.has(provider))continue;
   active.add(provider);
   let task;
   try{task=await claim(provider);}catch(e){active.delete(provider);onError(e);continue;}
   if(!task){active.delete(provider);continue;}
   started.push(provider);
   Promise.resolve().then(()=>perform(task)).catch(onError).finally(()=>active.delete(provider));
  }
  return started;
 }
 const api={videoPage,media,searchUrl,pairSender,scrape,launchReady,parallelReady};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.Stock=api;
})(typeof self!=='undefined'?self:this);
