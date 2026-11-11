// DOM/controller contracts, not browser or publishing acceptance evidence.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('hinglish_app/static/prepare-post.html','utf8');
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.hidden=false;this.disabled=false;this.textContent='';if(['input','select','textarea','option'].includes(tag))this.value='';this.classList={toggle(){}};}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=[...children];}
 get firstChild(){return this.children[0];}
 setAttribute(key,value){this[key]=value;}
}
async function screen(search='',failure={},stored=new Map()){
 const ids=new Map(),buttons=[],grid=new Element(),calls=[];let poll;
 for(const match of html.matchAll(/<(button|input|select|textarea|div|section|p|span|b|a|h2|label)\b([^>]*)>/g)){
  const item=new Element(match[1]),attrs=match[2];
  const id=attrs.match(/\bid="([^"]+)"/);if(id)ids.set(id[1],item);
  for(const key of ['profile','mode']){const value=attrs.match(new RegExp('data-'+key+'="([^"]+)"'));if(value)item.dataset[key]=value[1];}
  if(item.dataset.profile||item.dataset.mode)buttons.push(item);
  item.hidden=/\bhidden\b/.test(attrs);const value=attrs.match(/\bvalue="([^"]*)"/);if(value)item.value=value[1];
 }
 const byId=id=>{assert.ok(ids.has(id),'Missing element '+id);return ids.get(id);};
 const records={cricket:[],gaming:[]};
 for(const profile of Object.keys(records))records[profile].push({id:profile+'-long',profile,mode:'long',count:1,source:{path:profile+'.mp4'},stages:{inspect:{},speech:{transcript:'Cricket story'}},status:'prepared',jobs_by_platform:{},jobs:[]});
 const metadata={title:'A title',description:'A description',tags:['Cricket','IPL','Highlights'],instagram_caption:'A cricket moment\n\n#Cricket #IPL #Highlights'};
 records.gaming.push({id:'gaming-highlights',profile:'gaming',mode:'highlights',count:1,source:{path:'full-stream.mp4'},stages:{highlights:{video:{path:'finished-highlight.mp4'},duration:600,width:1280,height:720},'copy:youtube:1':{metadata}},status:'prepared',jobs_by_platform:{},jobs:[]});
 const handoffId='b'.repeat(32);records.gaming.push({id:handoffId,profile:'gaming',mode:'shorts',count:2,source:{path:'exact-gaming.mp4'},stages:failure.working?{inspect:{}}:{'copy:youtube:1':{metadata},'copy:instagram:1':{metadata}},status:failure.working?'working':'prepared',current_stage:failure.working?'speech':undefined,jobs_by_platform:{},jobs:[]});
 const channelAccounts=profile=>({youtube:{name:profile+' YouTube'},instagram:{id:profile+'_handle'}});
 let sequence=0;
 async function fetch(url,options={}){
  if(url==='/api/bridge')return {json:async()=>({token:'fixture'})};
  if(url==='/api/local-browser')return {ok:true,json:async()=>({connected:true})};
  if(url.startsWith('/api/publisher?'))return {ok:true,json:async()=>({accounts:channelAccounts(url.split('=').at(-1)),tasks:failure.runningAfterStart?[...Object.values(records).flat().filter(d=>d.status==='working').map(d=>({id:'task-'+d.id,status:'working',message:'Words and timing 26/37 (584.6s)'})),{id:'other-task',status:'working',message:'Checking another saved result'}]:failure.tasks||[]})};
  const body=JSON.parse(options.body);calls.push(body);const list=records[body.profile];let result={};
  if(body.action==='list'&&body.profile==='cricket'&&failure.cricketListGate){await failure.cricketListGate;return {ok:false,json:async()=>({error:'Drafts unavailable.'})};}
  if(body.action==='list')result={simple_source_supported:true,highlights_source_supported:true,cancel_preparation_supported:true,release_actions_supported:true,repeat_uploads_allowed:Boolean(failure.repeatTesting),preparations:structuredClone(list),accounts:{youtube:{name:body.profile+' YouTube'},instagram:{id:body.profile+'_handle'}},declarations:{made_for_kids:false,synthetic_media:false},runtime:{service_online:true}};
  if(body.action==='cancel'){const d=list.find(d=>d.id===body.id);d.status='cancelled';d.cancel_requested=true;result=structuredClone(d);}
  if(body.action==='publish-source')result={id:body.profile+'-long'};
  if(body.action==='create'){
   const draft={id:'prepared-'+(++sequence),profile:body.profile,mode:body.mode,count:body.mode==='shorts'?body.count:1,source:{path:body.video},stages:{},status:'saved',jobs_by_platform:{},jobs:[]};list.unshift(draft);result=structuredClone(draft);
  }
  if(body.action==='start'){
   const draft=list.find(d=>d.id===body.id);draft.status='prepared';draft.message='Ready';
   if(failure.runningAfterStart){draft.status='working';draft.current_stage='speech';draft.stages={inspect:{}};}
   else for(let n=1;n<=draft.count;n++)for(const p of draft.mode==='shorts'?['youtube','instagram']:['youtube'])draft.stages[`copy:${p}:${n}`]={metadata:{...structuredClone(metadata),title:n===1?metadata.title:'A title '+n,instagram_caption:n===1?metadata.instagram_caption:'Clip '+n+' moment\n\n#Cricket #IPL #Highlights'}};
   result={id:draft.id,task:{id:'task-'+draft.id}};
  }
  if(body.action==='edit')Object.assign(list.find(d=>d.id===body.id).stages[`copy:${body.platform}:${body.index}`].metadata,body.metadata);
  if(body.action==='post'){
   if(failure.platform===body.platform&&failure.remaining>0){failure.remaining--;return {ok:false,json:async()=>({error:'Connection needs checking.'})};}
   const draft=list.find(d=>d.id===body.id);draft.release_actions={...draft.release_actions,[body.platform]:body.release_action};
   const jobs=Array.from({length:draft.count},(_,i)=>({id:body.platform+'-'+i,platform:body.platform,status:'ready',due:1,release_action:body.release_action,remote:{}}));
   draft.jobs=[...draft.jobs.filter(j=>j.platform!==body.platform),...jobs];draft.jobs_by_platform[body.platform]=jobs.map(j=>j.id);result={worker_enabled:true};
  }
  return {ok:true,json:async()=>result};
 }
 const context={document:{documentElement:{dataset:{}},body:new Element('body'),dispatchEvent(){},getElementById:byId,createElement:tag=>new Element(tag),querySelector:()=>grid,querySelectorAll:query=>buttons.filter(b=>query.includes('[data-profile]')&&b.dataset.profile||query.includes('[data-mode]')&&b.dataset.mode)},window:{storylensFetch:fetch,storylensResponse:response=>response.json()},CustomEvent:class{constructor(type,init){this.type=type;this.detail=init.detail;}},location:{search,hash:''},URLSearchParams,crypto:{randomUUID:()=>String(++sequence)},localStorage:{getItem:key=>stored.get(key)||null,setItem:(key,value)=>stored.set(key,value),removeItem:key=>stored.delete(key)},fetch,setInterval(fn){poll=fn;},console};
 vm.runInNewContext(fs.readFileSync('hinglish_app/static/prepare-post-progress.js','utf8'),context);
 vm.runInNewContext(fs.readFileSync('hinglish_app/static/prepare-post.js','utf8'),context);
 for(let n=0;n<10;n++)await new Promise(setImmediate);
 return {ids,byId,calls,buttons,records,stored,reload:()=>screen(search,failure,stored),poll:async()=>{poll();for(let n=0;n<6;n++)await new Promise(setImmediate);},click:async(id)=>{await byId(id).onclick();for(let n=0;n<3;n++)await new Promise(setImmediate);},mode:async(mode)=>{await buttons.find(b=>b.dataset.mode===mode).onclick();},profile:async(profile)=>{await buttons.find(b=>b.dataset.profile===profile).onclick();}};
}

test('Clear removes submitted Long results without cancelling or deleting its saved jobs; refresh stays empty',async()=>{
 const s=await screen();s.byId('source').value='long.mp4';await s.click('run');await s.click('longSchedule');
 const saved=s.records.cricket.find(d=>d.id.startsWith('prepared-')),jobs=JSON.stringify(saved.jobs),before=s.calls.length;
 await s.click('clear');assert.equal(s.byId('source').value,'');assert.equal(s.byId('longTitle').value,'');assert.equal(s.byId('longMetadata').hidden,true);assert.equal(s.byId('longStages').hidden,true);assert.equal(s.byId('longReceipt').children.length,0);
 await s.poll();assert.equal(s.byId('longMetadata').hidden,true);assert.equal(s.byId('source').value,'');assert.equal(JSON.stringify(saved.jobs),jobs);
 assert.ok(s.calls.slice(before).every(c=>c.action==='list'));
 const reloaded=await s.reload();assert.equal(reloaded.byId('longMetadata').hidden,true);assert.equal(reloaded.byId('source').value,'');
 await s.profile('gaming');assert.equal(s.byId('run').hidden,false);await s.profile('cricket');assert.equal(s.byId('source').value,'');
});

test('Clear suppresses stale Shorts handoff URLs after reload but allows deliberate saved selection',async()=>{
 const id='b'.repeat(32),s=await screen('?profile=gaming&drafts='+id);assert.equal(s.byId('title').value,'A title');
 const before=s.calls.length;await s.click('clearReview');await s.poll();assert.equal(s.byId('title').value,'');assert.equal(s.byId('reviewBody').hidden,true);
 const reload=await s.reload();assert.equal(reload.byId('title').value,'');assert.equal(reload.calls.some(c=>c.action==='post'||c.action==='cancel'),false);
 await reload.mode('shorts');reload.byId('saved').value=id;await reload.byId('saved').onchange();assert.equal(reload.byId('title').value,'A title');assert.equal(reload.byId('reviewBody').hidden,false);
 assert.ok(s.calls.slice(before).every(c=>c.action==='list'));
});

test('Clear stays disabled during active preparation, and Highlights can be cleared without cancelling',async()=>{
 const working=await screen('?profile=gaming&drafts='+'b'.repeat(32),{working:true});assert.equal(working.byId('clear').disabled,true);assert.equal(working.byId('clearReview').disabled,true);
 await working.click('clear');assert.equal(working.byId('source').value,'');assert.equal(working.byId('title').disabled,true);assert.equal(working.byId('reviewBody').hidden,false);
 const s=await screen();await s.profile('gaming');s.byId('saved').value='gaming-highlights';await s.byId('saved').onchange();assert.equal(s.byId('title').value,'A title');await s.click('clear');await s.poll();assert.equal(s.byId('reviewBody').hidden,true);assert.equal(s.byId('title').value,'');
 assert.equal(s.calls.some(c=>['cancel','start','post','create'].includes(c.action)),false);
});
test('testing repeat Run and Clear create fresh requests, while posting retries retain their preparation',async()=>{
 const s=await screen('',{repeatTesting:true});s.byId('source').value='same.mp4';await s.click('run');await s.click('longSchedule');
 await s.click('run');const creates=s.calls.filter(c=>c.action==='create');assert.equal(creates.length,2);assert.notEqual(creates[0].request_id,creates[1].request_id);
 await s.click('clear');s.byId('source').value='same.mp4';await s.click('run');
 const all=s.calls.filter(c=>c.action==='create');assert.equal(new Set(all.map(c=>c.request_id)).size,3);
});

test('Long shows its review and compact optional Shorts row; direct Shorts shows the shared review',async()=>{
 const s=await screen();assert.equal(s.byId('reviewBody').hidden,true);assert.equal(s.byId('longMetadata').hidden,false);assert.equal(s.byId('run').hidden,false);assert.equal(s.byId('longPost').disabled,true);
 await s.mode('shorts');assert.equal(s.byId('reviewBody').hidden,false);assert.equal(s.byId('instagramMetadata').hidden,false);
 for(const id of ['postClips','scheduleClips']){assert.equal(s.byId(id).hidden,false);assert.equal(s.byId(id).disabled,true);}
 assert.equal(s.byId('clip').hidden,false);assert.equal(s.byId('clip').children.length,5);
 for(const id of ['postYoutube','scheduleYoutube','postInstagram','scheduleInstagram'])assert.equal(s.ids.has(id),false);
 assert.equal(s.byId('run').hidden,false);assert.equal(s.byId('longPost').hidden,true);
 for(const id of ['prepare','runWorkflow','minuteTest','resume','stop','saveYoutube','saveInstagram','buffer'])assert.equal(s.ids.has(id),false);
});
test('Connections stays compact and read-only until the owner chooses an account action',async()=>{
 const s=await screen();assert.equal(s.byId('connectionPanel').hidden,true);await s.click('connections');
 assert.equal(s.byId('connectionPanel').hidden,false);assert.equal(s.byId('youtubeConnection').textContent,'YouTube · Not connected');
 assert.equal(s.byId('chromeConnection').textContent,'Chrome publisher · Connected');
 assert.equal(s.calls.some(c=>['publish-source','post','connect-youtube'].includes(c.action)),false);
 await s.click('connections');assert.equal(s.byId('connectionPanel').hidden,true);
});
test('Gaming Highlights offers optional Shorts from the finished output, without posting it again',async()=>{
 const s=await screen();assert.equal(s.byId('highlightShorts').hidden,true);await s.profile('gaming');
 assert.equal(s.byId('reviewSection').hidden,true);assert.equal(s.byId('highlightShorts').hidden,false);assert.equal(s.byId('savedHighlights').value,'');assert.equal(s.byId('startHighlightShorts').disabled,true);
 s.byId('saved').value='gaming-highlights';await s.byId('saved').onchange();
 assert.equal(s.byId('highlightShorts').hidden,false);assert.equal(s.byId('savedHighlights').value,'gaming-highlights');assert.equal(s.byId('startHighlightShorts').disabled,false);
 s.byId('highlightShortsCount').value='5';await s.click('startHighlightShorts');
 const create=s.calls.find(c=>c.action==='create');assert.equal(create.video,'finished-highlight.mp4');assert.equal(create.source_preparation,'gaming-highlights');assert.equal(create.mode,'shorts');assert.equal(create.count,5);assert.equal(create.thumbnail,'');
 assert.equal(s.byId('highlightShorts').hidden,true);assert.equal(s.byId('instagramMetadata').hidden,false);assert.equal(s.byId('clip').children.length,5);
 assert.equal(s.calls.some(c=>['post','publish-source'].includes(c.action)),false);
});

test('empty Highlights keeps Want to create Shorts without a selected old filename; only the middle review row is hidden',async()=>{
 const s=await screen();await s.profile('gaming');
 assert.equal(s.byId('saved').hidden,true);assert.equal(s.byId('reviewSection').hidden,true);assert.equal(s.byId('highlightShorts').hidden,false);assert.equal(s.byId('savedHighlights').value,'');assert.equal(s.byId('startHighlightShorts').disabled,true);
 await s.poll();assert.equal(s.byId('savedHighlights').value,'');assert.equal(s.byId('source').value,'');
 const exact=await screen('?profile=gaming&drafts=gaming-highlights');
 assert.equal(exact.byId('reviewSection').hidden,false);assert.equal(exact.byId('saved').hidden,true);assert.equal(exact.byId('savedHighlights').value,'gaming-highlights');assert.equal(exact.byId('highlightShorts').hidden,false);
 await exact.click('clear');await exact.poll();assert.equal(exact.byId('savedHighlights').value,'');assert.equal(exact.byId('reviewSection').hidden,true);assert.equal(exact.byId('highlightShorts').hidden,false);
 assert.equal(s.calls.some(c=>['start','create','post','publish-source'].includes(c.action)),false);
});
test('Cancel clears the exact displayed preparation and never starts or posts another job',async()=>{
 const s=await screen('?profile=gaming&drafts='+'b'.repeat(32),{working:true});
 assert.equal(s.byId('cancelReview').disabled,false);await s.click('cancelReview');
 const cancel=s.calls.filter(c=>c.action==='cancel');assert.equal(cancel.length,1);assert.equal(cancel[0].id,'b'.repeat(32));assert.equal(cancel[0].profile,'gaming');
 assert.equal(s.byId('title').value,'');assert.equal(s.byId('cancelReview').disabled,true);
 assert.equal(s.calls.some(c=>['start','create','post','publish-source'].includes(c.action)),false);
});
test('Cancel clears a source selection before a Long job exists',async()=>{
 const s=await screen();s.byId('source').value='wrong-file.mp4';s.byId('source').oninput();assert.equal(s.byId('cancelLong').disabled,false);
 await s.click('cancelLong');assert.equal(s.byId('source').value,'');assert.equal(s.calls.some(c=>c.action==='cancel'),false);
});
test('existing worker counts fill the active stage bar without submitting work',async()=>{
 const s=await screen('?profile=gaming&drafts='+'b'.repeat(32),{working:true,tasks:[{id:'active',status:'working',message:'Words and timing 170/649 (2500.9s)'}]});
 const card=s.byId('stages').children.find(c=>c.dataset.stage==='speech');assert.equal(card.className,'stage-card active');assert.equal(card.children[1].children[0].value,26);assert.match(card.children[2].textContent,/169\/649 batches · 480 left/);
 assert.equal(s.calls.some(c=>['start','create','post','publish-source'].includes(c.action)),false);
});
test('real nested task response connects Run to its own numeric progress, even with another active task',async()=>{
 const s=await screen('',{runningAfterStart:true});await s.mode('shorts');s.byId('source').value='chosen.mp4';s.byId('count').value='4';await s.click('run');
 const card=s.byId('stages').children.find(c=>c.dataset.stage==='speech');assert.equal(card.children[1].children[0].value,67);assert.match(card.children[2].textContent,/25\/37 batches/);
 assert.equal(s.byId('reviewProgressCount').textContent,'1/15 steps complete · 14 remaining');
 assert.equal(s.calls.some(c=>['post','publish-source'].includes(c.action)),false);
});
test('old Studio links preserve the selected profile and reach the unified screen',()=>{
 const legacy=fs.readFileSync('hinglish_app/static/publisher.html','utf8');let destination='';
 vm.runInNewContext(legacy.match(/<script>(.*?)<\/script>/s)[1],{location:{search:'?profile=gaming&drafts=exact',hash:'#youtubeConnect',replace:value=>destination=value}});
 assert.equal(destination,'prepare-post.html?profile=gaming&drafts=exact#connections');
 for(const label of ['Preparation history','Review &amp; authorize','Your Learning Memory','Publishing Studio'])assert.equal(legacy.includes(label),false);
 assert.equal(html.includes('data-scheduled-host'),true);
});
test('Ask handoff opens only its exact preparation and missing IDs never select a different video',async()=>{
 const id='b'.repeat(32),s=await screen('?profile=gaming&drafts='+id);
 assert.equal(s.byId('saved').value,id);assert.equal(s.byId('title').value,'A title');
 assert.equal(s.buttons.find(b=>b.dataset.mode==='shorts')['aria-pressed'],'true');
 const missing=await screen('?profile=cricket&drafts='+id);
 assert.match(missing.byId('status').textContent,/exact saved preparation is unavailable/);
 assert.equal(missing.byId('title').value,'');assert.equal(missing.calls.some(c=>c.action==='post'),false);
});
test('Long Run prepares only, displays editable copy, and Schedule posts only the reviewed Long',async()=>{
 const s=await screen();s.byId('source').value='long.mp4';s.byId('thumbnail').value='thumb.jpg';await s.click('run');
 const creation=s.calls.find(c=>c.action==='create');assert.equal(creation.mode,'long');assert.equal(s.calls.some(c=>['publish-source','post'].includes(c.action)),false);
 assert.equal(s.byId('longTitle').value,'A title');assert.equal(s.byId('longTitle').disabled,false);assert.equal(s.byId('longSchedule').disabled,false);assert.equal(s.byId('reviewBody').hidden,true);
 s.byId('longTitle').value='Owner reviewed title';s.byId('longTitle').oninput();await s.click('longSchedule');
 const actions=s.calls.filter(c=>['edit','post'].includes(c.action));assert.deepEqual(actions.map(c=>c.action),['edit','post']);
 assert.equal(actions[0].metadata.title,'Owner reviewed title');assert.equal(actions[1].platform,'youtube');assert.equal(actions[1].release_action,'schedule');assert.equal(actions[1].id,actions[0].id);
 assert.equal(s.calls.some(c=>c.action==='publish-source'),false);
});
test('choosing a Shorts count does not expand details or submit work until Start',async()=>{
 const s=await screen();s.byId('saved').value='cricket-long';await s.byId('saved').onchange();s.byId('savedCount').value='4';s.byId('savedCount').oninput();
 assert.equal(s.byId('reviewBody').hidden,true);assert.equal(s.calls.some(c=>c.action==='create'),false);
 await s.click('startSaved');assert.equal(s.byId('reviewBody').hidden,false);assert.equal(s.byId('clip').children.length,4);
 assert.equal(s.calls.find(c=>c.action==='create').source_preparation,'cricket-long');assert.equal(s.calls.some(c=>c.action==='post'),false);
});
test('Shorts Run prepares only; edited caption is saved before the explicit platform action',async()=>{
 const s=await screen();await s.mode('shorts');assert.equal(s.byId('longPost').hidden,true);assert.equal(s.byId('run').hidden,false);
 s.byId('source').value='shorts.mp4';s.byId('count').value='3';await s.click('run');
 const creation=s.calls.find(c=>c.action==='create');assert.equal(creation.mode,'shorts');assert.equal(creation.count,3);assert.equal(s.calls.some(c=>c.action==='post'||c.action==='publish-source'),false);
 assert.equal(s.byId('caption').value.startsWith('A cricket moment'),true);
 s.byId('caption').value='Edited moment\n\n#Cricket #IPL #Highlights';s.byId('caption').oninput();await s.click('scheduleClips');
 const actions=s.calls.filter(c=>['edit','post'].includes(c.action));assert.deepEqual(actions.map(c=>c.action),['edit','post','post']);assert.equal(actions[0].metadata.instagram_caption,s.byId('caption').value);
 assert.deepEqual(actions.slice(1).map(c=>c.platform),['youtube','instagram']);assert.equal(actions[1].id,actions[2].id);assert.equal(actions[1].release_action,actions[2].release_action);
 await s.click('scheduleClips');assert.equal(s.calls.filter(c=>c.action==='post').length,2);
});
test('every clip remains inspectable and switching saves edits for the previous exact index',async()=>{
 const s=await screen();await s.mode('shorts');s.byId('source').value='shorts.mp4';s.byId('count').value='3';s.byId('count').oninput();
 assert.equal(s.byId('clip').children.length,3);await s.click('run');assert.equal(s.byId('clip').disabled,false);
 s.byId('title').value='Edited first clip';s.byId('title').oninput();s.byId('clip').value='2';await s.byId('clip').onchange();
 const edit=s.calls.find(c=>c.action==='edit');assert.equal(edit.index,1);assert.equal(edit.metadata.title,'Edited first clip');
 assert.equal(s.byId('title').value,'A title 2');assert.match(s.byId('caption').value,/Clip 2/);
 s.byId('clip').value='3';await s.byId('clip').onchange();assert.equal(s.byId('title').value,'A title 3');assert.match(s.byId('caption').value,/Clip 3/);
});
test('a partial shared action retries only its unfinished platform with the same action',async()=>{
 const s=await screen('',{platform:'instagram',remaining:1});await s.mode('shorts');s.byId('source').value='shorts.mp4';s.byId('count').value='2';await s.click('run');
 await s.click('scheduleClips');assert.equal(s.byId('postClips').disabled,true);assert.equal(s.byId('scheduleClips').disabled,false);
 await s.click('scheduleClips');const posts=s.calls.filter(c=>c.action==='post');
 assert.deepEqual(posts.map(c=>c.platform),['youtube','instagram','instagram']);assert.equal(new Set(posts.map(c=>c.id)).size,1);
 assert.equal(s.byId('scheduleClips').disabled,true);
});
test('saved Long starts Shorts from the selected source; Gaming Highlights has Run and no Instagram output',async()=>{
 const s=await screen();s.byId('saved').value='cricket-long';s.byId('savedCount').value='4';await s.click('startSaved');
 const child=s.calls.find(c=>c.action==='create');assert.equal(child.source_preparation,'cricket-long');assert.equal(child.count,4);assert.equal(child.video,'cricket.mp4');assert.equal(s.calls.some(c=>c.action==='post'),false);
 await s.profile('gaming');assert.equal(s.byId('youtubeAccount').textContent,'gaming YouTube');assert.equal(s.byId('instagramAccount').textContent,'@gaming_handle');
 assert.deepEqual(s.buttons.filter(b=>b.dataset.mode&&!b.hidden).map(b=>b.dataset.mode),['shorts','highlights']);
 assert.equal(s.buttons.find(b=>b.dataset.mode==='highlights')['aria-pressed'],'true');assert.equal(s.byId('longPost').hidden,true);
 await s.mode('long');assert.equal(s.buttons.find(b=>b.dataset.mode==='highlights')['aria-pressed'],'true');
 await s.mode('highlights');s.byId('source').value='gaming.mp4';s.byId('thumbnail').value='gaming.jpg';s.byId('minutes').value='15';await s.click('run');
 const highlight=s.calls.filter(c=>c.action==='create').at(-1);assert.equal(highlight.profile,'gaming');assert.equal(highlight.mode,'highlights');assert.equal(highlight.thumbnail,'gaming.jpg');assert.equal(s.byId('instagramMetadata').hidden,true);
 const before=s.calls.length;await s.click('scheduleClips');assert.deepEqual(s.calls.slice(before).filter(c=>c.action==='post').map(c=>c.platform),['youtube']);
 await s.profile('cricket');assert.equal(s.buttons.find(b=>b.dataset.mode==='highlights').hidden,true);assert.equal(s.byId('instagramAccount').textContent,'@cricket_handle');
 assert.equal(s.buttons.find(b=>b.dataset.mode==='long').hidden,false);
});



test('Channel names load while drafts wait, and a stale Cricket error leaves the Gaming header intact',async()=>{
 let releaseCricket;
 const cricketListGate=new Promise(resolve=>{releaseCricket=resolve;});
 const s=await screen('',{cricketListGate});
 assert.equal(s.byId('youtubeAccount').textContent,'cricket YouTube');
 assert.equal(s.byId('instagramAccount').textContent,'@cricket_handle');
 await s.profile('gaming');
 releaseCricket();
 await s.poll();
 assert.equal(s.byId('youtubeAccount').textContent,'gaming YouTube');
 assert.equal(s.byId('instagramAccount').textContent,'@gaming_handle');
 assert.match(s.byId('status').textContent,/Gaming/);
});
