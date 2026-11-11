(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StorylensStageProgress=api;})(typeof window==='object'?window:this,function(){
 'use strict';
 function plan(draft,mode='shorts',count=1){
  mode=draft?.mode||mode;count=Math.max(1,Math.min(40,Number(draft?.count||count)||1));
  const keys=['inspect','speech'];
  if(mode==='highlights')keys.push('highlight-signals','highlight-selection','highlights');
  if(mode==='shorts')keys.push('selection',...Array.from({length:count},(_,i)=>'render:'+(i+1)));
  const extra=[...Object.keys(draft?.stages||{}),draft?.current_stage].filter(k=>k?.startsWith('context:')).sort((a,b)=>Number(a.split(':')[1])-Number(b.split(':')[1]));
  keys.push(...new Set(extra));
  if(/^(?:weekly|discovery):/.test(draft?.current_stage||''))keys.push(draft.current_stage);
  for(const p of mode==='shorts'?['youtube','instagram']:['youtube'])for(let i=1;i<=count;i++)keys.push(`copy:${p}:${i}`);
  return [...new Set([...keys,...Object.keys(draft?.stages||{})])];
 }
 function measure(key,draft,live){
  if(Object.prototype.hasOwnProperty.call(draft?.stages||{},key))return {state:'done',percent:100,text:'100% · 1/1 complete'};
  if(draft?.status==='cancelling'&&draft.current_stage===key)return {state:'active',percent:null,text:'0/1 complete · Cancelling this step'};
  const failed=Boolean(draft?.errors?.[key]),running=draft?.status==='working'&&draft.current_stage===key;
  if(!running&&!failed)return {state:'pending',percent:0,text:draft?.current_stage===key&&draft?.status==='stopped'?'0/1 complete · Stopped':'0% · 0/1 complete · Waiting'};
  const message=live?.stage===key?String(live.message||''):'';
  let match,done,total,unit;
  // These messages are emitted BEFORE each batch/section starts.
  if((key==='speech'&&(match=message.match(/Words and timing\s+(\d+)\/(\d+)/i)))||
     ((key==='highlights'||key.startsWith('render:'))&&(match=message.match(/Rendering saved interval\s+(\d+)\/(\d+)/i)))){
   done=Number(match[1])-1;total=Number(match[2]);unit=key==='speech'?'batches':'parts';
  }else if(key==='highlight-selection'&&(match=message.match(/Finding gaming moments in section\s+(\d+)\/(\d+)/i))){
   const section=Number(match[1]);total=Number(match[2]);done=section-1;
   if(total>0&&done>=0&&section<=total)return {state:failed?'failed':'active',percent:Math.min(99,Math.floor(done/total*100)),text:`${Math.min(99,Math.floor(done/total*100))}% · Section ${section}/${total} · ${total-done} left${failed?' · Stopped':''}`};
  }else if(key==='selection'&&(match=message.match(/Finding hook moments in part\s+(\d+)\/(\d+)/i))){
   done=Number(match[1])-1;total=Number(match[2]);unit='sections';
  }else if(key==='selection'&&(match=message.match(/\((\d+)\/(\d+) selected\)/i))){
   done=Number(match[1]);total=Number(match[2]);unit='clips selected';
  }else if((key==='highlights'||key.startsWith('render:'))&&(match=message.match(/Rendering selected moment\s+(\d+)\/(\d+)/i))){
   done=Number(match[1])-1;total=Number(match[2]);unit='moments';
  }else if(key==='speech'&&(match=message.match(/Alternate CUDA speech:\s*(\d+)\/(\d+)s/i))){
   done=Number(match[1]);total=Number(match[2]);unit='seconds';
  }
  if(total>0&&done>=0&&done<=total){
   const percent=Math.min(99,Math.floor(done/total*100));
   return {state:failed?'failed':'active',percent,text:`${percent}% · ${done}/${total} ${unit} · ${total-done} left${failed?' · Stopped':''}`};
  }
  return {state:failed?'failed':'active',percent:null,text:'0/1 complete · '+(failed?'Needs attention':activity(key,message))};
 }
 function activity(key,message=''){
  if(key.startsWith('weekly:'))return /V8 is preparing/.test(message)?message:'V8 is preparing the weekly SEO packages';
  if(key.startsWith('discovery:'))return 'Reviewing SEO and thumbnail wording';
  if(/Waiting for.*GPU/i.test(message))return 'Waiting for the GPU';
  if(/retrying|correcting the saved issue/i.test(message))return 'Retrying this step';
  if(/source.checked|supported source excerpts/i.test(message))return 'Checking transcript details';
  if(/Reviewing search intent, title options and thumbnail wording/i.test(message))return 'Reviewing SEO and thumbnail wording';
  if(key.startsWith('copy:instagram:'))return 'Writing caption and hashtags';
  if(key.startsWith('copy:youtube:'))return 'Writing title and description';
  if(key.startsWith('context:'))return 'Reading this transcript section';
  if(key.startsWith('render:')||key==='highlights')return 'Creating the video';
  return ({inspect:'Checking your video',speech:'Reading speech and word timings',selection:'Finding moments for Shorts','highlight-signals':'Scanning gameplay and sound','highlight-selection':'Choosing highlight moments'})[key]||'Working on this step';
 }
 return {plan,measure,activity};
});
