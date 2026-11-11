// No browser, credentials, videos or remote changes: fixed upload-ID handoff tests.
const {test}=require('node:test');const assert=require('node:assert/strict');
const vm=require('node:vm');const fs=require('node:fs');
function fixture({permitted=true,wrongControl=false,stop=false,navigation=[],preview=false,staleList=false,missingClick=false,switchVia=false,longVideo=false}={}){
 const events=[],store={},job={id:'task',lease:'lease',channel_id:'UC'+'g'.repeat(22),video_id:'new00000001',publish_at:'2030-10-20T12:30:00+00:00'};
 job.action=preview?'youtube_schedule_preview':'youtube_schedule';
 if(switchVia)job.switch_via={channel_id:'UC'+'a'.repeat(22),channel_name:'Alternate channel'};
 if(longVideo)job.video_kind='long';
 let currentChannel=job.channel_id,pendingChannel='';const receipts=[];
 const tab={id:1,url:`https://studio.youtube.com/channel/${job.channel_id}/videos/short`,status:'complete'};
 const chrome={permissions:{async contains(){return permitted}},
  storage:{local:{async get(){return store},async set(v){Object.assign(store,v)}}},
  tabs:{async query(){events.push('query');return [tab]},async get(){return navigation.length?{...tab,...navigation.shift()}:tab},async create(){throw Error('Should reuse one Studio tab')},async update(){return tab},
   async reload(){events.push('reload');staleList=false},
   async sendMessage(id,m){events.push(m.action);assert.equal(m.job.video_id,job.video_id);if(m.action==='channel')return {ok:true,channel_id:job.channel_id};if(m.action==='inspect'&&staleList)return {ok:true,ready:false};if(m.action==='date'||m.action==='time')return {ok:true,control:{selector:'input[data-storylens-input="fixture-time"]'}};
    if(m.action==='open')return {ok:true,control:{selector:'[data-storylens-click="fixture-visibility"]'}};
    if(m.action==='ready')return {ok:true,ready:!wrongControl,driver_version:'0.4.7'};return {ok:true,ready:true};}},
  scripting:{async executeScript(o){assert.deepEqual([...o.files],['youtube-dom.js'])}},
  debugger:{async attach(){events.push('attach')},async detach(){events.push('detach')},async sendCommand(t,m,p){if(m==='DOM.getDocument')return {root:{nodeId:1}};if(m==='DOM.querySelector')return {nodeId:missingClick&&p.selector.includes('data-storylens-click')?0:2};if(m==='DOM.getBoxModel'){events.push('box');assert.equal(events.at(-2),'attach');return {model:{width:100,height:30,content:[100,200,200,200,200,230,100,230]}}}if(m==='DOM.focus')events.push('focus');if(m==='Input.dispatchMouseEvent'){events.push(p.type);assert.equal(p.x,150);assert.equal(p.y,215)}if(m==='Input.insertText')events.push('text:'+p.text)}}};
 if(switchVia){const send=chrome.tabs.sendMessage;chrome.tabs.sendMessage=async(id,m)=>{
   if(m.action==='channel'){events.push('channel:'+currentChannel);return {ok:true,channel_id:currentChannel}}
   if(['accountMenu','switchMenu','switchChannel'].includes(m.action)){
     events.push(m.action+':'+m.job.channel_id);
     if(m.action==='switchChannel')pendingChannel=m.job.channel_id;
     return {ok:true,control:{selector:'[data-storylens-click="fixture-switch"]'}};
   }
   if(['open','ready','commit'].includes(m.action))assert.equal(currentChannel,job.channel_id,'Visibility changes require the destination channel');
   return send(id,m);
 };
 const command=chrome.debugger.sendCommand;chrome.debugger.sendCommand=async(t,m,p)=>{
   const result=await command(t,m,p);
   if(m==='Input.dispatchMouseEvent'&&p.type==='mouseReleased'&&pendingChannel){currentChannel=pendingChannel;pendingChannel='';}
   return result;
 };}
 if(longVideo)chrome.tabs.update=async(id,options)=>{if(options.url){events.push('navigate:'+options.url);tab.url=options.url;}return tab;};
 const api=async(action,body)=>{events.push(action+':'+(body.status||''));if(action==='phase')return {stop:stop&&body.status==='sharing'};if(action==='finish'){receipts.push(body.result);assert.equal(body.result.status,preview?'complete':'submitted');assert.equal(body.result.video_id,job.video_id);if(preview)assert.equal(body.result.controls_verified,true)};return {}};
 const context=vm.createContext({chrome,console,Intl,Date,Error,URL,setTimeout:(f)=>{f();return 0}});
 vm.runInContext(fs.readFileSync('editor_plugins/storylens-chrome/youtube.js','utf8'),context);
 context.job=job;context.api=api;return {events,receipts,job,run:()=>vm.runInContext('storylensYouTubeTask(job,api)',context)};
}

test('requested round trip verifies both channels then schedules a long video only on its destination',async()=>{
 const f=fixture({switchVia:true,longVideo:true});await f.run();
 assert.deepEqual([...f.receipts[0].switch_trace],[f.job.channel_id,f.job.switch_via.channel_id,f.job.channel_id]);
 assert.equal(f.events.filter(e=>e.startsWith('switchChannel:')).length,2);
 assert.ok(f.events.some(e=>e.endsWith('/videos/upload')));
 assert.equal(f.events.filter(e=>e==='commit').length,1);
});
test('only returned upload ID is scheduled, with exact India date/time and durable submission boundary',async()=>{
 const f=fixture();await f.run();assert.ok(f.events.includes('text:Oct 20, 2030'));assert.ok(f.events.includes('text:18:00'));
 assert.ok(f.events.indexOf('phase:sharing')<f.events.indexOf('commit'));
 assert.equal(f.events.filter(e=>e==='commit').length,1);assert.ok(f.events.includes('finish:'));
});
test('missing optional Studio permission blocks before any browser access',async()=>{const f=fixture({permitted:false});await assert.rejects(f.run(),/Enable YouTube Studio/);assert.deepEqual(f.events,[])});
test('date/time confirmation failure never submits a schedule',async()=>{const f=fixture({wrongControl:true});await assert.rejects(f.run(),/did not confirm/);assert.ok(!f.events.includes('commit'))});
test('Stop before the durable submission boundary prevents Schedule',async()=>{const f=fixture({stop:true});await assert.rejects(f.run(),/Stopped/);assert.ok(!f.events.includes('commit'))});
test('blank/loading/hidden URLs while Studio opens do not assert sign-out',async()=>{
 const f=fixture({navigation:[{url:'about:blank',status:'complete'},{url:undefined,status:'loading'},
  {url:'https://www.youtube.com/',pendingUrl:'https://studio.youtube.com/channel/loading',status:'loading'}]});
 await f.run();assert.equal(f.events.filter(e=>e==='commit').length,1);
});
test('settled Google sign-in page requires the user and never changes video visibility',async()=>{
 const f=fixture({navigation:[{url:'https://accounts.google.com/ServiceLogin',status:'complete'}]});
 await assert.rejects(f.run(),/sign-in is required/);assert.ok(!f.events.includes('inspect'));assert.ok(!f.events.includes('commit'));
});
test('settled unrelated page is not misreported as sign-in',async()=>{
 const f=fixture({navigation:[{url:'chrome-error://chromewebdata/',status:'complete'}]});
 await assert.rejects(f.run(),/unexpected page/);assert.ok(!f.events.includes('commit'));
});
test('preview traverses controls and cancels without sharing or committing',async()=>{
 const f=fixture({preview:true});await f.run();assert.ok(f.events.includes('ready'));assert.ok(f.events.includes('cancel'));
 assert.ok(!f.events.includes('commit'));assert.ok(!f.events.includes('phase:sharing'));
});
test('stale upload list refreshes the same tab before opening controls and schedules the exact new ID once',async()=>{
 const f=fixture({staleList:true});await f.run();assert.equal(f.events.filter(e=>e==='reload').length,1);
 assert.ok(f.events.indexOf('reload')<f.events.indexOf('open'));assert.equal(f.events.filter(e=>e==='commit').length,1);
});

test('missing exact visibility control never clicks or submits and detaches debugger',async()=>{
 const f=fixture({missingClick:true});await assert.rejects(f.run(),/visibility control disappeared/);
 assert.ok(!f.events.includes('mousePressed'));assert.ok(!f.events.includes('commit'));
 assert.equal(f.events.at(-1),'detach');
});
