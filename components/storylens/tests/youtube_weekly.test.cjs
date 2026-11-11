// Fixed DOM/worker contracts; no real platform edit is performed here.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const channel='UC'+'a'.repeat(22),video='video000001';
const job={id:'task',action:'youtube_weekly_metadata',channel_id:channel,video_id:video,
 metadata:{title:'New title',description:'New description #Cricket #IPL #Analysis'},
 expected_metadata:{title:'Old title',description:'Old description'}};
function dom({visibility='Public',home=channel,title='Old title',description='Old description',disabled=true}={}){
 let listener,saves=0,undos=0;
 const element=(text='',attrs={})=>({innerText:text,disabled:false,attrs,
  getBoundingClientRect:()=>({width:100,height:30}),getAttribute(k){return this.attrs[k]??null;},setAttribute(k,v){this.attrs[k]=v;}});
 const titleField=element(title),descriptionField=element(description),save=element('Save',{'aria-label':'Save'}),undo=element('Undo changes',{'aria-label':'Undo changes'});
 save.disabled=disabled;save.click=()=>{saves++;save.disabled=true;};undo.click=()=>{undos++;save.disabled=true;};
 const homeLink=element();homeLink.href='https://studio.youtube.com/channel/'+home;
 const document={body:{innerText:''},querySelectorAll(selector){return ({'a#home-button':[homeLink],
  '#title-textarea [contenteditable="true"]':[titleField],'#description-textarea [contenteditable="true"]':[descriptionField],
  'button,[role="button"]':[save,undo],'button':[save,undo],
  'ytcp-video-metadata-visibility #icon-and-type':[element(visibility)]})[selector]||[];}};
 function load(){const ctx={window:{},document,location:{pathname:'/video/'+video+'/edit'},URL,
  chrome:{runtime:{id:'extension',onMessage:{addListener(fn){listener=fn;}}}}};
  vm.runInNewContext(fs.readFileSync('editor_plugins/storylens-chrome/youtube-weekly-dom.js','utf8'),ctx);}
 load();
 const send=action=>new Promise(resolve=>listener({source:'storylens-youtube-weekly',action,job},{id:'extension'},resolve));
 return {send,load,titleField,descriptionField,save,saves:()=>saves,undos:()=>undos};
}
test('wrong channel, non-public video and unsaved edits stop before Save',async()=>{
 for(const options of [{home:'UC'+'b'.repeat(22)},{visibility:'Scheduled'},{disabled:false}]){
  const d=dom(options);const r=await d.send('inspect');assert.equal(r.ok,false);assert.equal(d.saves(),0);
 }
});
test('saved manual edits are accepted as the starting text without cancelling future weeks',async()=>{
 const d=dom({title:'Manual owner edit',description:'Owner revised description'});
 const r=await d.send('inspect');assert.equal(r.ok,true);assert.equal(r.already_matches,false);assert.equal(d.saves(),0);
 d.titleField.innerText=job.metadata.title;d.save.disabled=false;
 assert.equal((await d.send('discard')).discarded,true);assert.equal(d.undos(),1);
});
test('a pre-Save readiness failure is retryable and never discards the owner’s unsaved work',async()=>{
 let discarded=0,saved=0;
 const context={setTimeout:fn=>fn(),chrome:{tabs:{get:async()=>({status:'complete',url:'https://studio.youtube.com/video/'+video+'/edit'}),update:async()=>{},
  sendMessage:async(_,message)=>{if(message.action==='discard')discarded++;if(message.action==='commit')saved++;return {ok:false,error:'Studio has unsaved manual changes. Waiting until they are saved or discarded.'};}},scripting:{executeScript:async()=>{}}}};
 vm.runInNewContext(fs.readFileSync('editor_plugins/storylens-chrome/youtube-weekly.js','utf8'),context);
 await assert.rejects(()=>context.storylensWeeklyYouTubeTask({...job,week:1,lease:'lease'},async()=>({stop:false}),{id:7},[]),e=>e.weekly_retryable===true);
 assert.equal(discarded,0);assert.equal(saved,0);
});
test('exact text requires prepared evidence and a fresh reload before its verified receipt',async()=>{
 const d=dom();assert.equal((await d.send('inspect')).already_matches,false);
 d.titleField.innerText=job.metadata.title;d.descriptionField.innerText=job.metadata.description;d.save.disabled=false;
 assert.equal((await d.send('commit')).ok,false);assert.equal(d.saves(),0);
 assert.equal((await d.send('ready')).ready,true);assert.equal((await d.send('commit')).ok,true);assert.equal(d.saves(),1);
 assert.equal((await d.send('verify')).ok,false);assert.equal((await d.send('settled')).reloaded,false);
 d.load();const receipt=await d.send('verify');assert.equal(receipt.ok,true);assert.equal(receipt.reloaded,true);assert.equal(receipt.visibility,'Public');
 assert.equal((await d.send('commit')).ok,false);assert.equal(d.saves(),1);
});
test('only the worker’s own unsaved fields may be discarded before submission',async()=>{
 const owned=dom({title:job.metadata.title,disabled:false});assert.equal((await owned.send('discard')).discarded,true);assert.equal(owned.undos(),1);
 const manual=dom({title:'Manual edit',disabled:false});assert.equal((await manual.send('discard')).ok,false);assert.equal(manual.undos(),0);
});
test('native thumbnail input is limited to the exact approved video and image file',async()=>{
 const commands=[];const context={chrome:{tabs:{get:async()=>({url:'https://studio.youtube.com/video/'+video+'/edit'})},
  debugger:{attach:async()=>{},detach:async()=>commands.push('detach'),sendCommand:async(_,method,args)=>{
   commands.push([method,args]);if(method==='DOM.getDocument')return {root:{nodeId:1}};
   if(method==='DOM.querySelector')return {nodeId:2};return {};}}}};
 vm.runInNewContext(fs.readFileSync('editor_plugins/storylens-chrome/youtube-weekly.js','utf8'),context);
 const target={...job,thumbnail:{path:'D:/approved.jpg',bytes:100}};
 await context.studioWeeklyThumbnail(7,target,{selector:'input[type="file"][data-storylens-thumbnail="video000001-weekly-thumbnail"]'});
 assert.ok(commands.some(c=>Array.isArray(c)&&c[0]==='DOM.setFileInputFiles'&&c[1].files[0]==='D:/approved.jpg'));
 assert.equal(commands.at(-1),'detach');
 await assert.rejects(()=>context.studioWeeklyThumbnail(7,{...target,thumbnail:{path:'D:/video.mp4'}},{selector:'input[type="file"]'}));
});

test('the full weekly worker saves once, keeps sharing phase during verification and reloads before completion',async()=>{
 for(const stop of [false,true]){
  let saves=0,reloads=0,finished=null,discarded=false;const phases=[];
  const task={...job,week:1,lease:'lease'},tab={id:7};
  const context={setTimeout:fn=>fn(),studioType:async()=>{},chrome:{
   tabs:{get:async()=>({status:'complete',url:'https://studio.youtube.com/video/'+video+'/edit'}),update:async()=>{},reload:async()=>reloads++,sendMessage:async(_,message)=>{
    const a=message.action;if(a==='inspect')return {ok:true,already_matches:false};
    if(a==='field')return {ok:true,control:{selector:'[contenteditable="true"][data-storylens-input="video000001-title"]'}};
    if(a==='commit')saves++;if(a==='discard')discarded=true;
    if(a==='verify')return {ok:true,video_id:video,channel_id:channel,metadata:job.metadata,visibility:'Public',save_disabled:true,reloaded:reloads>0};
    return {ok:true,ready:true};}},scripting:{executeScript:async()=>{}}}};
  vm.runInNewContext(fs.readFileSync('editor_plugins/storylens-chrome/youtube-weekly.js','utf8'),context);
  const api=async(action,data)=>{if(action==='phase'){phases.push(data.status);return {stop:stop&&data.message.startsWith('Saving')}}if(action==='finish')finished=data.result;return {};};
  if(stop){await assert.rejects(()=>context.storylensWeeklyYouTubeTask(task,api,tab,[channel]),/stopped/);assert.equal(saves,0);assert.equal(discarded,true);}
  else{await context.storylensWeeklyYouTubeTask(task,api,tab,[channel]);assert.equal(saves,1);assert.equal(reloads,1);assert.equal(finished.reloaded,true);const first=phases.indexOf('sharing');assert.ok(phases.slice(first).every(p=>p==='sharing'));}
 }
});
