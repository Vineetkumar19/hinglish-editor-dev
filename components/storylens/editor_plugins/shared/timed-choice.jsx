/* Individual, receipt-bound choice insertion/replacement. Public host APIs only. */
var SLTimedChoice = (function(){
 function fps(value){var p=String(value).split('/');return Number(p[0])/(p.length>1?Number(p[1]):1);}
 function validate(m,host){
  if(m.type!=='timed_choice'||m.version!==1||!/^[a-f0-9]{32}$/.test(m.operation_id)||!/^[a-f0-9]{64}$/.test(m.binding_id)||!/^[a-f0-9]{64}$/.test(m.asset_sha256))throw Error('Reopen this saved timeline choice before inserting it.');
  if(!m.expected||m.expected.host!==host||!new File(m.path).exists)throw Error('Reconnect the editor and restore this saved source before inserting it.');
  var rate=fps(m.fps);if(!(rate>0&&rate<=240)||!(m.end_frame>m.start_frame)||m.start_frame<0||m.source_in<0||!isFinite(m.source_duration))throw Error('This choice has invalid speech timing or source trim.');
  return rate;
 }
 function tag(m){return 'StorylensChoice:'+m.binding_id+':'+m.operation_id+':'+m.asset_sha256;}
 function readTag(comment,binding){var lines=String(comment||'').split(/\r?\n/),prefix='StorylensChoice:'+binding+':',found=null;for(var i=0;i<lines.length;i++)if(lines[i].indexOf(prefix)===0){if(found)throw Error('This timeline binding is ambiguous. Keep one bound item before retrying.');var parts=lines[i].split(':');if(parts.length!==4)throw Error('This timeline binding is unreadable. Reconnect it before replacing media.');found={operation:parts[2],sha:parts[3]};}return found;}
 function writeTag(comment,m){var lines=String(comment||'').split(/\r?\n/),kept=[],prefix='StorylensChoice:'+m.binding_id+':';for(var i=0;i<lines.length;i++)if(lines[i]&&lines[i].indexOf(prefix)!==0)kept.push(lines[i]);kept.push(tag(m));return kept.join('\n');}
 function receipt(m,item,start,end,sourceIn){return {ok:true,operation_id:m.operation_id,binding_id:m.binding_id,host:m.expected.host,project_id:m.expected.project_id,sequence_id:m.expected.sequence_id,item_id:String(item),asset_id:m.asset_id,asset_sha256:m.asset_sha256,path:m.path,start:start,end:end,source_in:sourceIn,message:m.action==='replace'?'Replaced the same timeline item; your placement, trim and effects are kept.':'Added this choice at its spoken keyword timestamp.'};}
 function ae(m){
  var rate=validate(m,'aftereffects'),comp=app.project.activeItem;
  if(storylensProjectId()!==m.expected.project_id)throw Error('The project changed. Reconnect before inserting this choice.');
  if(!(comp instanceof CompItem)||String(comp.id)!==m.expected.sequence_id||Math.abs(comp.frameRate-rate)>1e-5)throw Error('The active composition or frame rate changed. Reconnect before inserting this choice.');
  var matches=[],layer,found,i;
  for(i=1;i<=comp.numLayers;i++){layer=comp.layer(i);found=readTag(layer.comment,m.binding_id);if(found)matches.push({layer:layer,tag:found});}
  if(matches.length>1)throw Error('More than one layer has this binding; replacement is ambiguous.');
  layer=matches.length?matches[0].layer:null;found=matches.length?matches[0].tag:null;
  if(!layer&&m.action==='insert')for(i=1;i<=comp.numLayers;i++){var pending=comp.layer(i);if(pending.source&&pending.source.file&&pending.source.file.fsName===new File(m.path).fsName)throw Error('An unconfirmed layer already uses this private source. Check it before retrying; no duplicate was inserted.');}
  if(layer&&found.operation===m.operation_id){if(found.sha!==m.asset_sha256||!layer.source||!layer.source.file||layer.source.file.fsName!==new File(m.path).fsName)throw Error('The delivered layer source changed. Reconcile it before retrying.');return receipt(m,layer.id,layer.inPoint,layer.outPoint,(layer.inPoint-layer.startTime)*100/layer.stretch);}
  if(m.action==='replace'){
   if(!layer||String(layer.id)!==String(m.expected_item_id)||found.operation!==m.previous_operation_id)throw Error('The original bound layer is missing or changed. Reconnect it; no duplicate was inserted.');
   if(layer.timeRemapEnabled||!(layer.stretch>0))throw Error('This layer has time remapping or reverse playback. Keep its source or use the editor Replace command.');
   if((layer.outPoint-layer.startTime)*100/layer.stretch>Number(m.source_duration)+1e-6)throw Error('Your extended trim exceeds the replacement footage. Choose a longer option or shorten the layer.');
  }else if(m.action!=='insert'||layer)throw Error('An earlier item already owns this slot. Reconcile it before inserting another.');
  if(!layer&&(m.end_frame/rate>comp.duration+1e-6||Number(m.source_in)+(m.end_frame-m.start_frame)/rate>Number(m.source_duration)+1e-6))throw Error('The original speech interval does not fit this composition or source.');
  var footage=storylensFootage(m.path,storylensFolder('Storylens choices'));
  if(!(footage instanceof FootageItem)||footage.width!==comp.width||footage.height!==comp.height)throw Error('This prepared option does not match the composition canvas. Reconnect the matching timeline.');
  app.beginUndoGroup('Storylens timed choice');try{
   if(layer){layer.replaceSource(footage,false);}else{layer=comp.layers.add(footage);layer.startTime=m.start_frame/rate-Number(m.source_in);layer.inPoint=m.start_frame/rate;layer.outPoint=m.end_frame/rate;layer.audioEnabled=false;}
   layer.comment=writeTag(layer.comment,m);
   return receipt(m,layer.id,layer.inPoint,layer.outPoint,(layer.inPoint-layer.startTime)*100/layer.stretch);
  }finally{app.endUndoGroup();}
 }
 function premiere(m){
  var rate=validate(m,'premiere'),project=app.project,sequence=project.activeSequence;
  if(String(project.path||project.name)!==m.expected.project_id||!sequence||String(sequence.sequenceID)!==m.expected.sequence_id||Math.abs(254016000000/Number(sequence.timebase)-rate)>1e-5)throw Error('The active project, sequence or frame rate changed. Reconnect before inserting this choice.');
  var matches=[],items=[],i,j,k,t,c,item,found;
  function collect(bin){for(var n=0;n<bin.children.numItems;n++){var p=bin.children[n];if(p.type===ProjectItemType.BIN)collect(p);else{var mark=readTag(p.name,m.binding_id);if(mark)matches.push({item:p,tag:mark});if(p.getMediaPath&&p.getMediaPath()===new File(m.path).fsName)items.push(p);}}}
  collect(project.rootItem);
  if(matches.length>1||items.length>1)throw Error('More than one project item owns this binding; replacement is ambiguous.');
  item=matches.length?matches[0].item:items.length?items[0]:null;found=matches.length?matches[0].tag:null;
  function uses(source){var rows=[];for(var s=0;s<project.sequences.numSequences;s++){var seq=project.sequences[s],sets=[seq.videoTracks,seq.audioTracks];for(var a=0;a<sets.length;a++)for(var track=0;track<sets[a].numTracks;track++){var clips=sets[a][track].clips;for(var n=0;n<clips.numItems;n++){var clip=clips[n];if(clip.projectItem&&String(clip.projectItem.nodeId)===String(source.nodeId))rows.push({clip:clip,sequence:seq});}}}return rows;}
  var linked=item?uses(item):[],clip=linked.length?linked[0].clip:null;
  if(linked.length>1)throw Error('This private media item is shared by more than one timeline clip. Use a unique source before replacing it.');
  if(clip&&String(linked[0].sequence.sequenceID)!==m.expected.sequence_id)throw Error('The bound clip moved to another sequence. Reconnect before replacing it.');
  function clipId(){return String(clip.nodeId)+'|'+String(item.nodeId);}
  function confirm(){return receipt(m,clipId(),clip.start.seconds,clip.end.seconds,clip.inPoint.seconds);}
  if(clip&&found&&found.operation===m.operation_id){if(found.sha!==m.asset_sha256||item.getMediaPath()!==new File(m.path).fsName)throw Error('The delivered source changed. Reconcile it before retrying.');return confirm();}
  if(m.action==='replace'){
   if(!clip||clipId()!==String(m.expected_item_id)||!found||found.operation!==m.previous_operation_id||item.getMediaPath()!==new File(m.previous_path).fsName)throw Error('The original bound clip or source changed. No new clip was inserted.');
   if(clip.isSpeedReversed()||!(clip.getSpeed()>0)||clip.outPoint.seconds>Number(m.source_duration)+1e-6)throw Error('This replacement cannot cover the current reverse/speed/trim range. Choose a longer option or use the editor Replace command.');
   if(!item.canChangeMediaPath())throw Error('Premiere cannot replace this project item. Your existing clip is kept.');
   var oldStart=clip.start.ticks,oldEnd=clip.end.ticks,oldIn=clip.inPoint.ticks,oldOut=clip.outPoint.ticks;
   if(item.changeMediaPath(new File(m.path).fsName,false)!==0||item.getMediaPath()!==new File(m.path).fsName)throw Error('Premiere did not confirm the source replacement. Retry this same choice to reconcile it.');
   if(clip.start.ticks!==oldStart||clip.end.ticks!==oldEnd||clip.inPoint.ticks!==oldIn||clip.outPoint.ticks!==oldOut)throw Error('Premiere changed a clip boundary during replacement. Check the saved operation before trying another option.');
   item.name=writeTag(item.name,m);return confirm();
  }
  if(m.action!=='insert'||clip)throw Error('An earlier clip already owns this slot. Reconcile it before inserting another.');
  if(sequence.videoTracks.numTracks<2)throw Error('Add a spare video track above your original footage, then retry this same choice.');
  t=sequence.videoTracks[sequence.videoTracks.numTracks-1];
  var start=m.start_frame/rate,end=m.end_frame/rate;
  for(i=0;i<t.clips.numItems;i++){c=t.clips[i];if(c.start.seconds<end-1e-6&&c.end.seconds>start+1e-6)throw Error('The spare video track is occupied at this keyword. Keep it empty or move that clip before inserting.');}
  if(!item){var bin=project.rootItem.createBin('Storylens choice '+m.binding_id);if(!project.importFiles([m.path],true,bin,false))throw Error('Premiere did not confirm this private media import.');matches=[];items=[];collect(project.rootItem);if(items.length!==1)throw Error('The imported private source is ambiguous. Reconcile it before inserting.');item=items[0];}
  item.name=writeTag(item.name,m);
  if(item.setInPoint(Number(m.source_in),1)!==0||item.setOutPoint(Number(m.source_in)+end-start,1)!==0)throw Error('Premiere did not confirm the checked source trim.');
  var position=new Time();position.seconds=start;t.overwriteClip(item,position.ticks);
  linked=uses(item);if(linked.length!==1||String(linked[0].sequence.sequenceID)!==m.expected.sequence_id)throw Error('Premiere has not confirmed exactly one inserted clip. Retry this same choice to reconcile it.');
  clip=linked[0].clip;
  if(Math.abs(clip.start.seconds-start)>1e-5||Math.abs(clip.end.seconds-end)>1e-5||Math.abs(clip.inPoint.seconds-Number(m.source_in))>1e-5)throw Error('Premiere did not confirm the spoken frame and trim. Check this pending operation before trying another option.');
  return confirm();
 }
 return {ae:ae,premiere:premiere,validate:validate,receipt:receipt};
})();
