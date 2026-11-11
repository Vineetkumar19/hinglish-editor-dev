const $=id=>document.getElementById(id),token=document.documentElement.dataset.token;
const resultBar=window.storylensResults.mount($('featureResultBar'),{title:'Your beat markers are ready',meta:'Marker data · JSON / CSV',disabledReason:'These are beat markers. Apply them with Beat Studio inside your editor.',onView:()=>{$('results').scrollIntoView({block:'center',behavior:'smooth'})}});
let plan=null,busy=false,uploadedMusic=null;
async function api(path,body){const response=await window.storylensFetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},body:body?JSON.stringify({...body,host:['premiere','aftereffects'].includes(new URLSearchParams(location.search).get('host'))?new URLSearchParams(location.search).get('host'):'standalone'}):undefined});const data=await window.storylensResponse(response);if(!response.ok)throw Error(data.error||'Request failed');return data}
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function invalidate(){resultBar.setPending();plan=null;$('effects').disabled=true;$('results').hidden=true;$('effectStatus').textContent='Detect the beats first. This action never runs automatically.'}
for(const id of ['music','path','density','count','sourceIn','sourceOut','start','fps'])$(id).addEventListener('change',invalidate);
$('path').addEventListener('input',()=>{$('music').value='';uploadedMusic=null;invalidate()});
$('detect').onclick=async()=>{if(busy)return;busy=true;invalidate();$('detect').disabled=true;try{
  let path=$('path').value.trim(),file=$('music').files[0];
  if(file){if(uploadedMusic?.file===file){path=uploadedMusic.path}else{$('status').textContent='Adding music to your local editor…';const response=await window.storylensFetch('/api/beats/upload?name='+encodeURIComponent(file.name),{method:'POST',headers:{'X-Hinglish-Token':token,'Content-Type':'application/octet-stream'},body:file});const data=await window.storylensResponse(response);if(!response.ok)throw Error(data.error);path=data.path;uploadedMusic={file,path}}}
  if(!path)throw Error('Choose a music file first.');
  const body={path,source_in:Number($('sourceIn').value),timeline_start:Number($('start').value),fps:Number($('fps').value),density:$('density').value,target_count:$('count').value};if($('sourceOut').value)body.source_out=Number($('sourceOut').value);
  let job=await api('/api/beats/analyze',body);$('status').textContent='Listening locally. Other editing jobs finish first.';
  while(['queued','running'].includes(job.status)){await new Promise(resolve=>setTimeout(resolve,700));job=await api('/api/beats/jobs/'+job.id)}
  if(job.status!=='complete')throw window.storylensJobError(job);plan=job.plan;window.storylensBeatPlan=plan;resultBar.setResult({folder:job.folder});$('results').hidden=false;$('effects').disabled=!plan.beats.length;
  $('status').textContent=plan.beats.length?plan.beats.length+' markers ready. '+plan.notice:'No clear musical attacks found. No markers generated.';
  $('stats').textContent=`Detected counts: Light ${plan.counts.light} · Medium ${plan.counts.medium} · Strong ${plan.counts.strong}. Selected: ${plan.beats.length}.`;
  const c=$('map').getContext('2d');c.clearRect(0,0,1000,110);c.strokeStyle='#8ed5b5';for(const b of plan.beats){const x=(b.timeline_seconds-plan.timeline_start)/plan.duration*980+10;c.beginPath();c.moveTo(x,100);c.lineTo(x,90-b.strength*75);c.stroke()}
}catch(error){$('status').textContent=window.storylensError(error)}finally{busy=false;$('detect').disabled=false}};
$('json').onclick=()=>download('storylens-beats.json',JSON.stringify(plan,null,2),'application/json');
$('csv').onclick=()=>download('storylens-beats.csv','Name,Timeline seconds,Frame,Strength\r\n'+plan.beats.map((b,i)=>`Beat ${i+1},${b.timeline_seconds},${b.frame},${b.strength}`).join('\r\n'),'text/csv');
$('effects').onclick=async()=>{try{const result=await api('/api/beats/effects',{id:plan.id,style:$('style').value,amount:Number($('amount').value)});download('storylens-effects.json',JSON.stringify(result,null,2),'application/json');$('effectStatus').textContent='Effect plan exported. Use the editor panel to apply it natively; no video has been modified here.'}catch(error){$('effectStatus').textContent=window.storylensError(error)}};
