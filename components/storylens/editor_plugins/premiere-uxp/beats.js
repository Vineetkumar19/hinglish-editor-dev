let beatPlan=null,beatBusy=false,beatMusicContext=null;
const beatStatus=message=>document.querySelector('#beatStatus').textContent=message;
function beatButtons(busy){beatBusy=busy;document.querySelector('#beatDetect').disabled=busy;document.querySelector('#beatApply').disabled=busy||!beatPlan;document.querySelector('#beatDensity').disabled=busy;document.querySelector('#beatCount').disabled=busy}
function beatTransaction(project,build,label){let ok;project.lockedAccess(()=>{ok=project.executeTransaction(build,label)});if(!ok)throw Error(label+' failed')}
async function beatCheckpoint(project,label){
  if(!project.path||!await project.save())throw Error('Save the Premiere project before using Beat Studio.');
  const fs=require('uxp').storage.localFileSystem,folder=await(await fs.getDataFolder()).createFolder('beats-'+Date.now()+'-'+label);
  const source=await fs.getEntryWithUrl('file:'+project.path.replace(/\\/g,'/'));
  await source.copyTo(folder);const backup=await folder.getEntry(source.name);if(!(await backup.getMetadata()).size)throw Error('Project checkpoint failed');
}
async function beatContext(){
  const project=await ppro.Project.getActiveProject(),sequence=project&&await project.getActiveSequence();if(!sequence)throw Error('Open a sequence and select one music clip on an audio track.');
  const clips=[];for(let t=0;t<await sequence.getAudioTrackCount();t++){const track=await sequence.getAudioTrack(t);for(const clip of await track.getTrackItems(ppro.Constants.TrackItemType.CLIP,false))if(await clip.getIsSelected())clips.push(clip)}
  if(clips.length!==1)throw Error('Select exactly one music clip on an audio track.');const clip=clips[0];
  if(await clip.isSpeedReversed()||Math.abs(await clip.getSpeed()-1)>.00001)throw Error('Use normal-speed music for beat detection.');
  const item=ppro.ClipProjectItem.cast(await clip.getProjectItem());
  return {path:await item.getMediaFilePath(),source_in:(await clip.getInPoint()).seconds,source_out:(await clip.getOutPoint()).seconds,timeline_start:(await clip.getStartTime()).seconds,fps:254016000000/Number(await sequence.getTimebase()),sequence_id:String(sequence.guid)};
}
async function beatSequence(plan){const p=await ppro.Project.getActiveProject(),s=p&&await p.getActiveSequence();if(!s||String(s.guid)!==plan.sequence_id||Math.abs(254016000000/Number(await s.getTimebase())-plan.fps)>.001)throw Error('Sequence changed. Detect the beats again.');return {project:p,sequence:s}}
async function markBeats(plan){
  const {project,sequence}=await beatSequence(plan);await beatCheckpoint(project,'before-markers');
  const markers=await ppro.Markers.getMarkers(sequence),old=await markers.getMarkers();
  const ours=[];for(const marker of old)if(String(await marker.getComments()).startsWith('StorylensBeat:'))ours.push(marker);
  beatTransaction(project,compound=>{for(const marker of ours)compound.addAction(markers.createRemoveMarkerAction(marker));for(let i=0;i<plan.beats.length;i++)compound.addAction(markers.createAddMarkerAction('Beat '+(i+1),'Comment',ppro.TickTime.createWithSeconds(plan.beats[i].frame/plan.fps),ppro.TickTime.createWithSeconds(0),'StorylensBeat:'+plan.id))},'Storylens beat markers');
  await beatCheckpoint(project,'after-markers');
}
document.querySelector('#beatDetect').onclick=async()=>{try{const health=await api('/api/health');if(!health.capabilities||!health.capabilities.includes('beat_markers_v1'))throw Error('Restart the local Storylens editor to enable Beat Studio.');beatPlan=null;beatButtons(true);const context=await beatContext();beatMusicContext=context;let job=await api('/api/beats/analyze',{method:'POST',body:JSON.stringify({...context,host:'premiere',density:document.querySelector('#beatDensity').value,target_count:document.querySelector('#beatCount').value})});beatStatus('Listening locally…');while(job.status==='queued'||job.status==='running'){await new Promise(r=>setTimeout(r,700));job=await api('/api/beats/jobs/'+job.id)}if(job.status!=='complete')throw Error(job.error);if(!job.plan.beats.length)throw Error('No clear beats found; no markers added.');const current=await beatContext();for(const key of ['path','source_in','source_out','timeline_start','sequence_id'])if(String(current[key])!==String(context[key]))throw Error('Music placement changed. Detect again.');await markBeats(job.plan);beatPlan=job.plan;beatStatus(beatPlan.beats.length+' beat markers placed.')}catch(e){beatPlan=null;beatStatus(e.message)}finally{beatButtons(false)}};
document.querySelector('#beatApply').onclick=async()=>{try{
  beatButtons(true);if(JSON.stringify(await beatContext())!==JSON.stringify(beatMusicContext))throw Error('Music placement changed. Detect again.');const plan=await api('/api/beats/effects',{method:'POST',body:JSON.stringify({id:beatPlan.id,host:'premiere',style:document.querySelector('#beatStyle').value,amount:document.querySelector('#beatAmount').value,video_track:document.querySelector('#beatVideoTrack').value})});
  const {project,sequence:original}=await beatSequence(plan);if((plan.video_track||1)>await original.getVideoTrackCount())throw Error('The selected video track does not exist.');await beatCheckpoint(project,'before-effects');
  const ids=new Set((await project.getSequences()).map(s=>String(s.guid)));beatTransaction(project,c=>c.addAction(original.createCloneAction()),'Duplicate for Storylens beats');
  const sequence=(await project.getSequences()).find(s=>!ids.has(String(s.guid)));if(!sequence)throw Error('Could not find the duplicate sequence.');await project.openSequence(sequence);
  let applied=0,skipped=0;
  for(let t=0;t<await sequence.getVideoTrackCount();t++){
    if(t!==(plan.video_track||1)-1)continue;
    const track=await sequence.getVideoTrack(t);if(typeof track.isLocked==='function'&&await track.isLocked())continue;
    for(const clip of await track.getTrackItems(ppro.Constants.TrackItemType.CLIP,false)){
      if(await clip.isSpeedReversed()||Math.abs(await clip.getSpeed()-1)>.00001){skipped++;continue}
      const chain=await clip.getComponentChain();let scale=null;
      for(let c=0;c<await chain.getComponentCount();c++){const comp=await chain.getComponentAtIndex(c),match=await comp.getMatchName();if(match==='ADBE Motion'||match==='AE.ADBE Motion'){scale=await comp.getParam(1);break}}
      if(!scale||!await scale.areKeyframesSupported()||await scale.isTimeVarying()){skipped++;continue}
      const base=(await scale.getStartValue()).value.value,start=(await clip.getStartTime()).seconds,end=(await clip.getEndTime()).seconds,source=(await clip.getInPoint()).seconds,events=[];let previousEnd=-1;
      for(const beat of plan.beats){const sec=beat.frame/plan.fps,half=Math.max(1/plan.fps,plan.duration/2),left=Math.max(start,sec-half),right=Math.min(end-1/plan.fps,sec+half);if(sec<start||sec>=end)continue;if(sec<=left||sec>=right||left<=previousEnd){skipped++;continue}events.push([left,base],[sec,base*(1+plan.amount/100)],[right,base]);previousEnd=right;applied++}
      if(!events.length)continue;
      beatTransaction(project,c=>c.addAction(scale.createSetTimeVaryingAction(true)),'Enable beat animation');
      beatTransaction(project,c=>{for(const [sec,value] of events){const key=scale.createKeyframe(value);key.position=ppro.TickTime.createWithSeconds(source+sec-start);c.addAction(scale.createAddKeyframeAction(key));c.addAction(scale.createSetInterpolationAtKeyframeAction(key.position,plan.style==='smooth'?ppro.Constants.InterpolationMode.BEZIER:ppro.Constants.InterpolationMode.LINEAR,true))}},'Apply Storylens zoom pulses');
    }
  }
  await beatCheckpoint(project,'after-effects');beatStatus(applied+' zoom pulses applied; '+skipped+' events/clips skipped. Original sequence preserved.');beatPlan=null;
}catch(e){beatStatus(e.message+' Original sequence preserved; a partial duplicate may remain.')}finally{beatButtons(false)}};
let lastAutoMusic='';setInterval(async()=>{if(beatBusy||!document.querySelector('#beatAuto').checked)return;try{const signature=JSON.stringify(await beatContext());if(signature!==lastAutoMusic){lastAutoMusic=signature;document.querySelector('#beatDetect').click()}}catch(_){/* Wait for a selected music clip. */}},1800);
for(const id of ['beatDensity','beatCount'])document.querySelector('#'+id).onchange=()=>{beatPlan=null;lastAutoMusic='';beatButtons(false);beatStatus('Beat settings changed. Detect again before applying effects.')};
document.querySelector('#cinematicOpen').onclick=async()=>{try{const result=await require('uxp').shell.openExternal(bridge+'/cinematic.html?host=premiere','Open the local Storylens Cinematic Reels workspace');if(result)throw Error(result)}catch(e){document.querySelector('#cinematicStatus').textContent=e.message}};
document.querySelector('#cinematicImport').onclick=async()=>{const status=document.querySelector('#cinematicStatus');try{const job=await api('/api/cinematic/import-manifest',{method:'POST',body:JSON.stringify({host:'premiere'})}),project=await ppro.Project.getActiveProject();if(!project)throw Error('Open and save a Premiere project first.');await beatCheckpoint(project,'before-cinematic-import');if(!await project.importFiles(job.result.xml_files,true,await project.getInsertionBin(),false))throw Error('Premiere could not import the cinematic reel.');await beatCheckpoint(project,'after-cinematic-import');status.textContent='Cinematic reel imported as a new sequence.'}catch(e){status.textContent=e.message}};
