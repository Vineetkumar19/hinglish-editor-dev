// Isolated controller tests: no real browser, network, credentials or publication.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function fixture({caption='Cricket #IPL',ready=true,account='vineet_editz19',interrupt=false,action='reel',emptyFirst=false,nativeFailure=false,jobs=1,switchDisconnect=false,contentDisconnected=false,resultDisconnected=false,openTabs=1,inboxTab=false,loadingTab=false,missingHost=false,injectionDenied=false,accountSequence=[],profileFailures=0,replyStop=false,datedRead=false}={}){
 const events=[],store={port:8765,key:'fixture-only',...(interrupt?{active:{id:'old',lease:'old-lease'}}:{})};
 const job={id:'job',lease:'lease',action,account:'vineet_editz19',caption};
 if(action==='instagram_comments_reply')Object.assign(job,{
   source_url:'https://www.instagram.com/vineet_editz19/reel/FIXTURE/',comment_id:'123',
   author:'viewer',comment_text:'Great clip!',reply_text:'Thanks for watching!'
 });
 if(datedRead)Object.assign(job,{
   source_url:'https://www.instagram.com/vineet_editz19/reel/FIXTURE/',
   cutoff:'2026-11-02T00:00:00+00:00',
 });
 const chrome={storage:{local:{async get(keys){if(typeof keys==='string')return {[keys]:store[keys]};return Object.fromEntries(keys.map(k=>[k,store[k]]))},async set(v){Object.assign(store,v)},async remove(keys){for(const k of [].concat(keys))delete store[k]}}},tabs:{async update(id,options){if(options.url){assert.equal(options.url,job.source_url);events.push('tabs:post')}else{assert.equal(options.active,true);events.push('tabs:activate')}},async query(){events.push('tabs:query');return openTabs?[{id:1,url:action==='instagram_comments_read'?'https://www.instagram.com/vineet_editz19/reel/FIXTURE/':'https://www.instagram.com/vineet_editz19/'}, ...(inboxTab?[{id:2,url:'https://www.instagram.com/direct/inbox/'}]:[])]:[]},async get(){return {id:1,url:'https://www.instagram.com/vineet_editz19/'}},async create(){events.push('tabs:create');return {id:1}},async sendMessage(id,m){events.push(m.action);if(m.action==='result'&&resultDisconnected){resultDisconnected=false;throw Error('Could not establish connection. Receiving end does not exist.')}if(m.action==='verifyPublished')return {ok:true,url:'https://www.instagram.com/vineet_editz19/reel/FIXTURE/',account:'vineet_editz19',caption_verified:true,posted_at:Date.now()/1000};if(contentDisconnected){contentDisconnected=false;throw Error('Could not establish connection. Receiving end does not exist.')}if(m.action==='switch'&&switchDisconnect){account='vineet_editz19';switchDisconnect=false;throw Error('Could not establish connection. Receiving end does not exist.')}if(m.action==='inspect'){if(emptyFirst){emptyFirst=false;return {ok:true,account:''}}return {ok:true,account}}if(['start','fileControl'].includes(m.action))return {ok:true,uploadControl:{x:100,y:200}};if(m.action==='ready')return {ok:true,ready};if(m.action==='result')return {ok:true,published:true,url:'https://www.instagram.com/vineet_editz19/reel/FIXTURE/'};return {ok:true}}},alarms:{onAlarm:{addListener(){}},async create(){}},runtime:{onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(){}},getURL:p=>'chrome-extension://fixture/'+p}};
 let claimed=0;
 const fetch=async(url,opts)=>{const op=url.split('/').at(-1),body=JSON.parse(opts.body);events.push(op==='phase'?'phase:'+body.status:op);
  let value={};if(op==='claim'){value=claimed>=jobs?{job:null}:{job:{...job,id:claimed?'job'+claimed:'job'},media:{name:'fixture.mp4',size:3,path:'D:/authorized/fixture.mp4'}};claimed++}
  if(op==='media')value={bytes:3,data:'YWJj'};
  if(op==='phase')value={stop:replyStop&&body.status==='sharing'};
  if(op==='finish')events.push(body.result.status+':'+body.id);
  return {ok:true,async json(){return value}};
 };
 const listeners=new Set();
 chrome.debugger={onEvent:{addListener:f=>listeners.add(f),removeListener:f=>listeners.delete(f)},async attach(){events.push('native:attach')},async detach(){events.push('native:detach')},async sendCommand(target,method,params){events.push(method);if(method==='DOM.getDocument')return {root:{nodeId:1}};if(method==='DOM.querySelector')return {nodeId:2};if(method==='DOM.describeNode')return {node:{backendNodeId:9}};if(method==='Input.dispatchMouseEvent'&&params.type==='mouseReleased'){for(const f of listeners)f({tabId:1},'Page.fileChooserOpened',{backendNodeId:9});}if(method==='DOM.setFileInputFiles'){if(nativeFailure)throw Error('Not allowed');assert.deepEqual([...params.files],['D:/authorized/fixture.mp4']);return {}}}};
 chrome.scripting={async executeScript(request){assert.deepEqual([...request.files],['dom-checks.js','analytics-dom.js','instagram.js']);events.push('reconnect')}};
 chrome.permissions={async contains({origins}){return origins[0]==='https://www.instagram.com/*'&&!missingHost}};
 chrome.tabs.reload=async()=>events.push('tabs:reload');
 {const send=chrome.tabs.sendMessage;chrome.tabs.sendMessage=async(id,m)=>{
   if(m.action==='profile'&&profileFailures-->0){events.push('profile:failed');return {ok:false,error:'Instagram has not loaded the existing post list for duplicate protection.'}}
   const result=await send(id,m);
   if(['switch','switchMenu','switchAccount','commentReplyPrepare','commentReplyReady'].includes(m.action))result.control={x:100,y:200};
   if(m.action==='commentsRead'&&datedRead){
     assert.equal(m.cutoff,job.cutoff);
     Object.assign(result,{account:job.account,rows:[],expired_source:true,
       source_url:job.source_url,source_published_at:'2026-11-01T00:00:00.000Z'});
   }
   if(m.action==='commentReplyReceipt')Object.assign(result,{confirmed:true,reply_id:'456',parent_id:m.comment_id});
   return result;
 }}
 if(loadingTab){const get=chrome.tabs.get;let reads=0;chrome.tabs.get=async(...args)=>{
   if(reads++===0){events.push('tab:loading');return {id:1,url:'about:blank',pendingUrl:'https://www.instagram.com/vineet_editz19/',status:'loading'}}
   events.push('tab:ready');return get(...args);
 }}
 if(injectionDenied)chrome.scripting.executeScript=async()=>{throw Error('Cannot access contents of the page. Extension manifest must request permission to access the respective host.')};
 if(accountSequence.length){const send=chrome.tabs.sendMessage;chrome.tabs.sendMessage=async(id,m)=>{
   if(m.action==='inspect'&&accountSequence.length){events.push('inspect');return {ok:true,account:accountSequence.shift()}}
   return send(id,m);
 }}
 const context=vm.createContext({chrome,fetch,AbortSignal,console,URL,importScripts(){},clearTimeout,setTimeout:(fn,ms)=>ms===300?0:ms===10000?setTimeout(fn,500):(fn(),0)});
 vm.runInContext(fs.readFileSync('editor_plugins/storylens-chrome/worker.js','utf8'),context);
 return {events,store,run:()=>vm.runInContext('run()',context)};
}

test('waits for a newly created tab to reach Instagram before adapter injection',async()=>{
 const f=fixture({openTabs:0,loadingTab:true,contentDisconnected:true});await f.run();
 assert.ok(f.events.indexOf('tab:ready')<f.events.indexOf('reconnect'));
 assert.ok(f.events.includes('published:job'));
});

test('a failed switched-account profile refreshes once before any upload and still shares only once',async()=>{
 const f=fixture({profileFailures:1});await f.run();
 assert.equal(f.events.filter(e=>e==='tabs:reload').length,1);
 assert.ok(f.events.indexOf('tabs:reload')<f.events.indexOf('start'));
 assert.equal(f.events.filter(e=>e==='share').length,1);assert.ok(f.events.includes('published:job'));
});

test('a profile that fails after the bounded refresh stops without selecting media or sharing',async()=>{
 const f=fixture({profileFailures:2});await f.run();
 assert.equal(f.events.filter(e=>e==='tabs:reload').length,1);
 assert.ok(!f.events.includes('start'));assert.ok(!f.events.includes('share'));assert.ok(f.events.includes('needs_review:job'));
});

test('an account check cannot succeed from a cached sidebar when its profile is unavailable',async()=>{
 const f=fixture({action:'inspect',profileFailures:2});await f.run();
 assert.ok(!f.events.includes('complete:job'));assert.ok(f.events.includes('needs_review:job'));
 assert.ok(!f.events.includes('start'));assert.ok(!f.events.includes('share'));
});

test('missing host access is distinguished from a loading page and stops before upload',async()=>{
 const f=fixture({contentDisconnected:true,missingHost:true});await f.run();
 assert.match(f.store.message,/does not have Instagram host access/);
 assert.ok(!f.events.includes('reconnect'));assert.ok(!f.events.includes('start'));assert.ok(!f.events.includes('share'));
});

test('injection failure reports the checked Instagram origin and target tab',async()=>{
 const f=fixture({contentDisconnected:true,injectionDenied:true});await f.run();
 assert.match(f.store.message,/Instagram adapter could not attach to https:\/\/www.instagram.com \(tab 1, ready\)/);
 assert.ok(!f.events.includes('start'));assert.ok(!f.events.includes('share'));
});
test('checks account, transfers scoped media, records sharing before a single Share, and verifies result',async()=>{
 const f=fixture();await f.run();assert.equal(f.events.filter(e=>e==='share').length,1);
 assert.ok(f.events.indexOf('phase:sharing')<f.events.indexOf('share'));
 assert.ok(f.events.indexOf('Input.dispatchMouseEvent')<f.events.indexOf('DOM.setFileInputFiles'));
 assert.ok(f.events.includes('published:job'));assert.ok(f.events.includes('DOM.setFileInputFiles'));assert.ok(f.events.indexOf('native:detach')<f.events.indexOf('uploaded'));assert.equal(f.store.active,undefined);
 await f.run();assert.equal(f.events.filter(e=>e==='share').length,1);
});
test('invalid account blocks before file transfer or Share',async()=>{
 const f=fixture({account:'other_user'});await f.run();assert.ok(!f.events.includes('start'));assert.ok(!f.events.includes('share'));assert.ok(f.events.includes('needs_review:job'));
});
test('caption or preview mismatch never clicks Share',async()=>{
 const f=fixture({ready:false});await f.run();assert.ok(!f.events.includes('share'));assert.ok(f.events.includes('abortOwned'));assert.ok(f.events.includes('needs_review:job'));
});
test('interrupted task is reconciled as needs_review before any new claim',async()=>{
 const f=fixture({interrupt:true});await f.run();assert.ok(f.events.indexOf('needs_review:old')<f.events.indexOf('claim'));
});
test('preview transfers video and caption but cannot click Share',async()=>{
 const f=fixture({action:'preview'});await f.run();assert.ok(f.events.includes('uploaded'));assert.ok(f.events.includes('ready'));assert.ok(!f.events.includes('share'));assert.ok(f.events.includes('complete:job'));
});
test('receipt recovery reads the existing post and never opens the uploader or clicks Share',async()=>{
 const f=fixture({action:'verify_reel'});await f.run();
 assert.ok(f.events.includes('verifyPublished'));assert.ok(f.events.includes('complete:job'));
 for(const action of ['start','profile','native:attach','share','phase:sharing'])assert.ok(!f.events.includes(action),action);
});
test('waits for the profile to load rather than reporting an empty page as signed out',async()=>{
 const f=fixture({action:'preview',emptyFirst:true});await f.run();assert.equal(f.events.filter(e=>e==='inspect').length,2);assert.ok(f.events.includes('complete:job'));assert.ok(!f.events.includes('share'));
});

test('native file-selection rejection detaches, cleans only its owned composer, and never submits a post',async()=>{const f=fixture({nativeFailure:true});await f.run();assert.ok(f.events.includes('native:detach'));assert.ok(!f.events.includes('share'));assert.ok(f.events.includes('abortOwned'));assert.ok(f.events.includes('needs_review:job'));});

test('sequential jobs reuse one Instagram tab instead of opening a tab per video',async()=>{
 const f=fixture({action:'inspect',jobs:2,openTabs:0});await f.run();await f.run();
 assert.equal(f.events.filter(e=>e==='tabs:create').length,1);
 assert.ok(f.events.includes('complete:job'));assert.ok(f.events.includes('complete:job1'));
});

test('a normal account-switch navigation reconnects before uploading and never repeats Share',async()=>{
 const f=fixture({account:'other_user',switchDisconnect:true});await f.run();
 assert.equal(f.events.filter(e=>e==='switch').length,1);
 assert.equal(f.events.filter(e=>e==='share').length,1);
 assert.ok(f.events.includes('published:job'));
});

test('extension reload reconnects its packaged adapter before checking account and uploading',async()=>{
 const f=fixture({contentDisconnected:true});await f.run();
 assert.equal(f.events.filter(e=>e==='reconnect').length,1);
 assert.ok(f.events.indexOf('reconnect')<f.events.indexOf('inspect'));
 assert.ok(f.events.indexOf('inspect')<f.events.indexOf('start'));
 assert.equal(f.events.filter(e=>e==='share').length,1);
 assert.ok(f.events.includes('published:job'));
});

test('connection loss after Share verifies the existing publication without uploading again',async()=>{
 const f=fixture({resultDisconnected:true});await f.run();
 assert.equal(f.events.filter(e=>e==='share').length,1);
 assert.equal(f.events.filter(e=>e==='start').length,1);
 assert.ok(f.events.includes('verifyPublished'));
 assert.ok(f.events.includes('published:job'));
 assert.ok(!f.events.includes('abortOwned'));
 assert.ok(f.events.includes('tabs:activate'));
});

test('caption-free Reel skips native caption entry and still verifies before one Share',async()=>{
 const f=fixture({caption:''});await f.run();
 assert.ok(!f.events.includes('Input.insertText'));
 assert.ok(f.events.includes('ready'));
 assert.equal(f.events.filter(e=>e==='share').length,1);
 assert.ok(f.events.includes('published:job'));
});

test('a separate Instagram inbox does not block or receive the publishing job',async()=>{
 const f=fixture({caption:'',inboxTab:true});await f.run();
 assert.ok(f.events.includes('published:job'));
 assert.ok(!f.events.includes('tabs:create'));
 assert.equal(f.events.filter(e=>e==='share').length,1);
});

test('switching waits for three consecutive target-account confirmations before opening an upload',async()=>{
 const target='vineet_editz19';
 const f=fixture({accountSequence:['other',target,'other',target,target,target]});await f.run();
 assert.equal(f.events.filter(e=>e==='inspect').length,6);
 assert.ok(f.events.indexOf('start')>f.events.lastIndexOf('inspect'));
 assert.equal(f.events.filter(e=>e==='share').length,1);assert.ok(f.events.includes('published:job'));
 assert.ok(f.events.indexOf('native:attach')<f.events.indexOf('switch'));
 assert.ok(f.events.indexOf('switch')<f.events.indexOf('switchMenu'));
 assert.ok(f.events.indexOf('switchMenu')<f.events.indexOf('switchAccount'));
 assert.ok(f.events.indexOf('switchAccount')<f.events.indexOf('native:detach'));
});


test('comment read uses the existing post without navigation, composer, or submission',async()=>{
 const f=fixture({action:'instagram_comments_read'});await f.run();
 assert.deepEqual(f.events,['claim','tabs:query','commentsRead','finish','complete:job']);
});


test('Chrome reads an exact owned permalink with the date cutoff and does not submit',async()=>{
 const f=fixture({action:'instagram_comments_read',datedRead:true});
 await f.run();
 assert.ok(f.events.indexOf('tabs:post')<f.events.indexOf('verifyCommentPost'));
 assert.ok(f.events.indexOf('verifyCommentPost')<f.events.indexOf('commentsRead'));
 assert.ok(f.events.includes('complete:job'));
 assert.ok(!f.events.includes('phase:sharing'));
});

test('Chrome reply clicks Post once after authorization and checks the exact thread',async()=>{
 const f=fixture({action:'instagram_comments_reply'});
 await f.run();
 assert.equal(f.events.filter(event=>event==='phase:sharing').length,1);
 assert.equal(f.events.filter(event=>event==='Input.dispatchMouseEvent').length,4);
 assert.ok(f.events.indexOf('phase:sharing')<f.events.indexOf('commentReplyReceipt'));
 assert.ok(f.events.includes('complete:job'));
 assert.ok(!f.events.includes('start')&&!f.events.includes('share'));
});

test('Chrome reply cannot click Post when the broker revokes authorization',async()=>{
 const f=fixture({action:'instagram_comments_reply',replyStop:true});
 await f.run();
 assert.equal(f.events.filter(event=>event==='Input.dispatchMouseEvent').length,2);
 assert.ok(!f.events.includes('commentReplyReceipt'));
 assert.ok(f.events.includes('needs_review:job'));
});
