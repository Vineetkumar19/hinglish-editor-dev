// Isolated Studio DOM and Chrome APIs; never connects to a real browser.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture({dayFirst=false,wrongTime=false,wrongDate=false,wrongZone=false,preview=false,dashboard=false,visibility='Private',allowReschedule=false,publishAt='2030-10-20T12:30:00+00:00',wireJob=null,saveNeverSettles=false,privateCleanup=false,visibilityArrow=false,visibilityDelay=0}={}){
 let listener,opened=false,expanded=visibility==='Scheduled',calendar=false,commits=0,pendingSave=0,pendingVisibility='Scheduled',privateSelected=false;
 const channel='UC'+'g'.repeat(22),job={channel_id:channel,video_id:'new00000001',
  publish_at:publishAt,allow_reschedule:allowReschedule,action:preview?'youtube_schedule_preview':'youtube_schedule'};
 if(wireJob){Object.assign(job,wireJob);publishAt=job.publish_at||publishAt;}
 const el=(innerText='',click=()=>{})=>{const attrs={};return {innerText,textContent:innerText,click,attrs,
  getBoundingClientRect:()=>({x:10,y:20,width:100,height:30}),getAttribute:name=>attrs[name]??null,
  setAttribute:(name,value)=>{attrs[name]=value},contains:()=>false,querySelector:()=>null,querySelectorAll:()=>[]};};
 const first=el(),second=el(),home=el();home.href=`https://studio.youtube.com/channel/${channel}`;
 const label=el(visibility,()=>{throw Error('Synthetic visibility clicks are ignored by current Studio')});
 const privateLabel=el(visibility);
 const arrow=el();label.querySelectorAll=s=>s==='ytcp-icon-button.edit-triangle-icon[role="button"]'&&visibilityArrow?[arrow]:s==='.label-span'?[privateLabel]:[];
 const cell=el(visibilityDelay?'':visibility,()=>{throw Error('Incorrect outer-cell click')});
 cell.querySelectorAll=s=>s==='.icon-text-edit-triangle-wrap.editable'?[label]:[];
 const row=el();row.querySelectorAll=s=>s==='[role="cell"]'?[cell]:[];
 const link=el();link.href=`/video/${job.video_id}/edit`;link.closest=()=>row;
 const expand=el('',()=>{expanded=true});
 const p=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'numeric'}).formatToParts(new Date(publishAt)).map(p=>[p.type,p.value]));
 const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
 const date=el(wrongDate?'Oct 21, 2030':`${months[Number(p.month)-1]} ${Number(p.day)}, ${p.year}`);
 if(dayFirst)date.innerText=`${Number(p.day)} ${months[Number(p.month)-1]} ${p.year}`;
 const dateSpan=el(date.innerText,()=>{calendar=true});date.querySelector=()=>dateSpan;
 const time=el();time.type='text';time.value=wrongTime?'17:00':new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Kolkata',hour:'numeric',minute:'2-digit'}).format(new Date(publishAt));
 const dateInput=el();dateInput.type='text';dateInput.value=date.innerText;
 const cancel=el('Cancel',()=>{opened=false});
 const submit=el('Schedule',()=>{commits++;pendingSave=3});
 const submitOuter=el('Schedule');submitOuter.contains=e=>e===submit;
 const privateRadio=el('Private');privateRadio.getAttribute=name=>name==='name'?'PRIVATE':name==='aria-checked'?String(privateSelected):null;
 const save=el('Save',()=>{commits++;pendingSave=3;pendingVisibility='Private'});
 const zone=el(wrongZone?'GMT+0000':'Default set to local time zone (GMT+0530)');
 zone.getAttribute=name=>name==='aria-label'?zone.innerText:null;
 const dialog=el();dialog.querySelector=s=>s==='#first-container'?first:s==='#second-container'?second:null;
 dialog.querySelectorAll=s=>s==='button,[role="button"]'?(privateCleanup?[cancel,save]:[cancel,submitOuter,submit]):
  s==='[role="radio"],tp-yt-paper-radio-button'&&privateCleanup?[privateRadio]:
  s==='#second-container-expand-button'&&!expanded?[expand]:s==='#datepicker-trigger'&&expanded?[date]:
  s==='input'&&expanded?[time]:s==='[aria-label],[title],tp-yt-paper-tooltip'?[zone]:[];
 const popup=el();popup.getBoundingClientRect=()=>({width:0,height:0});popup.querySelector=()=>opened?dialog:null;
 const document={body:{innerText:''},querySelectorAll:s=>s==='a#home-button'?[home]:s==='a'?[link]:
  s==='ytcp-video-visibility-edit-popup'?[popup]:s==='#second-container-expand-button'&&opened&&!expanded?[expand]:
  s==='input'?(calendar?[time,dateInput]:[time]):[]};
 const chrome={runtime:{id:'fixture',onMessage:{addListener:fn=>{listener=fn}}}};
 const context=vm.createContext({window:{},document,chrome,location:{origin:'https://studio.youtube.com',pathname:`/channel/${channel}`+(dashboard?'':'/videos/short')},URL,Intl,Date,setTimeout:fn=>{if(visibilityDelay&&!--visibilityDelay)cell.innerText=visibility;if(pendingSave&&!saveNeverSettles&&!--pendingSave){opened=false;cell.innerText=pendingVisibility}fn()}});
 vm.runInContext(fs.readFileSync('editor_plugins/storylens-chrome/youtube-dom.js','utf8'),context);
 const call=action=>new Promise(resolve=>listener({source:'storylens-youtube',action,job},{id:'fixture'},resolve));
 const runWorker=async()=>{
  let focused=null;const finishes=[];job.id=job.id||'task';job.lease=job.lease||'lease';
  chrome.permissions={contains:async()=>true};chrome.storage={local:{get:async()=>({}),set:async()=>{}}};
  chrome.tabs={update:async()=>{},query:async()=>[{id:1,url:`https://studio.youtube.com/channel/${channel}/videos/short`}],
   get:async()=>({id:1,url:`https://studio.youtube.com/channel/${channel}/videos/short`,status:'complete'}),
   sendMessage:async(id,message)=>call(message.action)};
  chrome.scripting={executeScript:async()=>{}};
  chrome.debugger={attach:async()=>{},detach:async()=>{},sendCommand:async(target,method,params)=>{
   if(method==='DOM.getDocument')return {root:{nodeId:1}};
   if(method==='DOM.querySelector')return {nodeId:params.selector===`input[data-storylens-input="${dateInput.attrs['data-storylens-input']}"]`?2:3};
   if(method==='DOM.getBoxModel')return {model:{width:100,height:30,content:[10,20,110,20,110,50,10,50]}};
   if(method==='Input.dispatchMouseEvent'&&params.type==='mouseReleased'){if(opened&&privateCleanup)privateSelected=true;opened=true;return {}};
   if(method==='DOM.focus'){focused=calendar?dateInput:params.nodeId===2?dateInput:time;return {}};
   if(method==='Input.insertText'){assert.ok(focused);focused.value=params.text;return {}};
   if(method==='Input.dispatchKeyEvent'&&params.type==='keyDown'&&params.key==='Enter'&&params.text==='\r'){
    date.innerText=dateInput.value;calendar=false;
   }
   return {};
  }};
  context.api=async(action,body)=>{if(action==='phase')return {stop:false};if(action==='finish')finishes.push(body.result);return {}};
  context.job=job;vm.runInContext(fs.readFileSync('editor_plugins/storylens-chrome/youtube.js','utf8'),context);
  await vm.runInContext('storylensYouTubeTask(job,api)',context);return finishes;
 };
 return {call,runWorker,nativeOpen:()=>{opened=true},closeCalendar:()=>{calendar=false},commits:()=>commits,opened:()=>opened,markedArrow:()=>arrow.attrs['data-storylens-click'],markedPrivateLabel:()=>privateLabel.attrs['data-storylens-click']};
}

module.exports={fixture};
