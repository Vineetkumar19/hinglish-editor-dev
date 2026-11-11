/* Public ExtendScript API only; no QE razor commands or third-party presets. */
function storylensBeatReply(value){
  if(value===null)return 'null';if(typeof value==='string')return hinglishEscape(value);if(typeof value==='number'||typeof value==='boolean')return String(value);
  var parts=[];for(var k in value)if(value.hasOwnProperty(k))parts.push(hinglishEscape(k)+':'+storylensBeatReply(value[k]));return '{'+parts.join(',')+'}';
}
function storylensMusicInfo(){
    var seq=app.project.activeSequence;if(!seq)throw Error('Open a sequence and select one music clip on an audio track.');
    var found=[];for(var t=0;t<seq.audioTracks.numTracks;t++)for(var i=0;i<seq.audioTracks[t].clips.numItems;i++){var c=seq.audioTracks[t].clips[i];if(c.isSelected())found.push(c);}
    if(found.length!==1)throw Error('Select exactly one music clip on an audio track.');
    var clip=found[0];if(clip.isSpeedReversed()||Math.abs(clip.getSpeed()-1)>.00001)throw Error('Beat marking currently needs music at normal speed.');
    return {path:clip.projectItem.getMediaPath(),source_in:clip.inPoint.seconds,source_out:clip.outPoint.seconds,timeline_start:clip.start.seconds,fps:254016000000/Number(seq.timebase),sequence_id:seq.sequenceID};
}
function storylensMusicContext(){try{return storylensBeatReply(storylensMusicInfo());}catch(e){return storylensBeatReply({error:e.toString()});}}
function storylensCinematicCheckpoint(label){
    if(!app.project.path)throw Error('Save the Premiere project before importing your cinematic reel.');
    app.project.save();var source=new File(app.project.path),folder=new Folder(source.parent.fsName+'/Storylens Beat Backups');
    if(!folder.exists&&!folder.create())throw Error('Could not create a project checkpoint folder.');
    var path=folder.fsName+'/cinematic-'+new Date().getTime()+'-'+label+'.prproj';
    if(!source.copy(path)||!new File(path).exists)throw Error('Project checkpoint failed.');return path;
}
function storylensImportCinematic(paths){try{storylensCinematicCheckpoint('before-import');var result=hinglishImportXML(paths);if(result!=='ok')throw Error(result);storylensCinematicCheckpoint('after-import');return storylensBeatReply({message:'Cinematic reel imported as a new sequence. Retimed shot copies and soundtrack remain separate.'});}catch(e){return storylensBeatReply({error:e.toString()});}}
function storylensBeatSequence(plan){var s=app.project.activeSequence;if(!s||String(s.sequenceID)!==String(plan.sequence_id))throw Error('The active sequence changed. Detect the beats again.');if(Math.abs(254016000000/Number(s.timebase)-plan.fps)>.001)throw Error('Sequence frame rate changed. Detect the beats again.');return s;}
function storylensBeatCheckpoint(seq,suffix){
  if(!app.project.path)throw Error('Save your Premiere project before using Beat Studio.');
  var parent=new File(app.project.path).parent,folder=new Folder(parent.fsName+'/Storylens Beat Backups');if(!folder.exists&&!folder.create())throw Error('Could not create project backup folder.');
  var path=folder.fsName+'/beats-'+new Date().getTime()+'-'+suffix+'.prproj';
  seq.exportAsProject(path);if(!new File(path).exists)throw Error('Premiere project checkpoint failed.');return path;
}
function storylensMarkBeats(plan){
  try{
    var seq=storylensBeatSequence(plan);storylensBeatCheckpoint(seq,'before-markers');
    var now=storylensMusicInfo();if(now.path!==plan.path||Math.abs(now.source_in-plan.source_in)>.001||Math.abs(now.source_out-plan.source_out)>.05||Math.abs(now.timeline_start-plan.timeline_start)>.001)throw Error('Music placement changed. Detect the beats again.');
    // Replace only our generated markers. User markers are never removed.
    var marker=seq.markers.getFirstMarker();while(marker){var next=seq.markers.getNextMarker(marker);if(String(marker.comments).indexOf('StorylensBeat:')===0)seq.markers.deleteMarker(marker);marker=next;}
    for(var i=0;i<plan.beats.length;i++){var b=plan.beats[i],m=seq.markers.createMarker(b.frame/plan.fps);m.name='Beat '+(i+1);m.comments='StorylensBeat:'+plan.id+' | '+plan.density+' | strength '+b.strength;}
    var saved=storylensBeatCheckpoint(seq,'after-markers');
    return storylensBeatReply({message:plan.beats.length+' beat markers placed · '+plan.density+' density',checkpoint:saved});
  }catch(e){return storylensBeatReply({error:e.toString()});}
}
function storylensApplyBeatEffects(plan){
  try{
    var original=storylensBeatSequence(plan);if((plan.video_track||1)>original.videoTracks.numTracks)throw Error('The selected video track does not exist.');storylensBeatCheckpoint(original,'before-effects');
    var ids={};for(var i=0;i<app.project.sequences.numSequences;i++)ids[app.project.sequences[i].sequenceID]=true;
    if(!original.clone())throw Error('Could not duplicate the sequence.');
    var seq=null;for(var n=0;n<app.project.sequences.numSequences;n++)if(!ids[app.project.sequences[n].sequenceID])seq=app.project.sequences[n];
    if(!seq)throw Error('Could not locate the duplicate sequence.');
    app.project.openSequence(seq.sequenceID);seq.name=original.name+' - Storylens beats';
    var applied=0,skipped=0;
    for(var t=0;t<seq.videoTracks.numTracks;t++){
      if(t!==(plan.video_track||1)-1)continue;
      if(seq.videoTracks[t].isLocked())continue;
      for(var j=0;j<seq.videoTracks[t].clips.numItems;j++){
        var clip=seq.videoTracks[t].clips[j],scale=null;
        if(clip.isSpeedReversed()||Math.abs(clip.getSpeed()-1)>.00001){skipped++;continue;}
        for(var c=0;c<clip.components.numItems;c++)if(clip.components[c].matchName==='ADBE Motion'||clip.components[c].matchName==='AE.ADBE Motion'){
          // Parameter 1 is the public intrinsic Motion Scale control (not a localized name).
          scale=clip.components[c].properties[1];break;
        }
        if(!scale||!scale.areKeyframesSupported()||scale.isTimeVarying()){skipped++;continue;}
        var base=scale.getValue(),events=[],end=-1;
        for(var k=0;k<plan.beats.length;k++){
          var sec=plan.beats[k].frame/plan.fps;
          if(sec<clip.start.seconds||sec>=clip.end.seconds)continue;
          var half=Math.max(1/plan.fps,plan.duration/2),left=Math.max(clip.start.seconds,sec-half),right=Math.min(clip.end.seconds-1/plan.fps,sec+half);
          if(sec<=left||sec>=right||left<=end){skipped++;continue;}
          events.push([left,base],[sec,base*(1+plan.amount/100)],[right,base]);end=right;applied++;
        }
        if(events.length){scale.setTimeVarying(true);for(var e=0;e<events.length;e++){var time=new Time();time.seconds=clip.inPoint.seconds+events[e][0]-clip.start.seconds;scale.addKey(time);scale.setValueAtKey(time,events[e][1],true);scale.setInterpolationTypeAtKey(time,plan.style==='smooth'?5:0,true);}}
      }
    }
    var checkpoint=storylensBeatCheckpoint(seq,'after-effects');
    return storylensBeatReply({message:applied+' zoom pulses applied on a new sequence; '+skipped+' unsupported, animated or boundary events skipped',checkpoint:checkpoint});
  }catch(e){return storylensBeatReply({error:e.toString()+' Your original sequence is preserved; a partial duplicate may remain.'});}
}
