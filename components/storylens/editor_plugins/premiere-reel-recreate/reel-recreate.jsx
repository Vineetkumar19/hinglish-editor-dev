/* Native Premiere counterpart of Storylens Reel Recreate. No After Effects process. */
var StorylensPremiereReel=(function(){
 var TICKS=254016000000;
 function json(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return '"'+String(v).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n')+'"';if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(json(k)+':'+json(v[k]));return '{'+a.join(',')+'}';}
 function norm(p){return new File(p).fsName.toLowerCase();}
 function time(s){var t=new Time();t.seconds=s;return t;}
 function write(b,name,data){var f=new File(b.receipt_dir+'/'+name);f.encoding='UTF-8';if(!f.open('w'))throw Error('Cannot save the reel receipt.');f.write(json(data));f.close();}
 function stage(b,name,extra){write(b,'premiere-progress.json',{stage:name,details:extra||null});}
 function seq(name){for(var i=0;i<app.project.sequences.numSequences;i++){var s=app.project.sequences[i];if(s.name===name)return s;}return null;}
 function bin(parent,name){for(var i=0;i<parent.children.numItems;i++){var c=parent.children[i];if(c.type===ProjectItemType.BIN&&c.name===name)return c;}return parent.createBin(name);}
 function findPath(parent,path){for(var i=0;i<parent.children.numItems;i++){var c=parent.children[i];if(c.type===ProjectItemType.BIN){var n=findPath(c,path);if(n)return n;}else{var p=c.getMediaPath();if(p&&norm(p)===norm(path))return c;}}return null;}
 function media(parent,path){var item=findPath(app.project.rootItem,path);if(item)return item;if(!new File(path).exists)throw Error('Saved media is missing: '+path);if(!app.project.importFiles([path],true,parent,false))throw Error('Premiere did not import '+new File(path).name);item=findPath(app.project.rootItem,path);if(!item)throw Error('The imported source could not be found.');return item;}
 function adjustment(parent){for(var i=0;i<parent.children.numItems;i++){var c=parent.children[i];if(c.type===ProjectItemType.BIN){var n=adjustment(c);if(n)return n;}else if(c.isAdjustmentLayer&&c.isAdjustmentLayer())return c;}return null;}
 function move(item,parent){if(item.moveBin)item.moveBin(parent);}
 function place(track,item,start,end,name){
  for(var i=0;i<track.clips.numItems;i++){var old=track.clips[i];if(old.name===name&&Math.abs(old.start.seconds-start)<.02){if(Math.abs(old.end.seconds-end)>.04)throw Error(name+' was manually trimmed; it was preserved.');return old;}if(old.start.seconds<end-.001&&old.end.seconds>start+.001)throw Error('A clip already occupies '+start.toFixed(2)+' seconds. It was preserved.');}
  item.setInPoint(0,4);item.setOutPoint(end-start,4);
  track.overwriteClip(item,start);
  var clip=null;for(i=0;i<track.clips.numItems;i++){var candidate=track.clips[i];if(candidate.projectItem.nodeId===item.nodeId&&Math.abs(candidate.start.seconds-start)<.04)clip=candidate;}
  if(!clip)throw Error('Premiere did not confirm insertion of '+name+'. Check the timeline before retrying.');
  clip.name=name;clip.inPoint=time(0);clip.outPoint=time(end-start);clip.end=time(end);
  if(Math.abs(clip.start.seconds-start)>.04||Math.abs(clip.end.seconds-end)>.04)throw Error('Premiere did not retain the planned timing for '+name);return clip;
 }
 function marks(s,id,beats){var owner='StorylensReel:'+id+':Beat:';for(var i=0;i<beats.length;i++){var found=false,m=s.markers.getFirstMarker();while(m){if(m.comments===owner+i){found=true;break;}m=s.markers.getNextMarker(m);}if(!found){m=s.markers.createMarker(beats[i].timeline_seconds);m.name='Beat '+(i+1);m.comments=owner+i;}}}
 function soundtrackOnly(main,b,sound){
  // Premiere inserts linked silent audio when a sequence is placed on a video track.
  // Unlink only our generated nests, remove those audio instances, then place music last.
  var owned={},remove=[],nestedAudio=0,t,i,c,p,selected=main.getSelection();
  for(t=0;t<3;t++)for(i=0;i<main.videoTracks[t].clips.numItems;i++){c=main.videoTracks[t].clips[i];if(/^(Footage [0-9]+ - EMPTY|Lyric [0-9]+)( - [a-f0-9]{8})?$/.test(c.name))owned[c.projectItem.nodeId]=true;}
  for(t=0;t<main.audioTracks.numTracks;t++)for(i=0;i<main.audioTracks[t].clips.numItems;i++){
   c=main.audioTracks[t].clips[i];p=c.projectItem.getMediaPath();
   if(owned[c.projectItem.nodeId]){remove.push(c);nestedAudio++;}
   else if(c.name==='Reel soundtrack'||(p&&norm(p)===norm(b.source)))remove.push(c);
   else throw Error('An audio edit outside this reel was preserved. Review it before retrying.');
  }
  if(!nestedAudio&&remove.length){c=remove[0];p=c.projectItem.getMediaPath();if(remove.length===1&&main.audioTracks[0].clips.numItems===1&&p&&norm(p)===norm(b.soundtrack)&&Math.abs(c.start.seconds)<.001&&Math.abs(c.end.seconds-b.duration)<.04&&Math.abs(c.inPoint.seconds)<.001)return;throw Error('The soundtrack was changed after preparation; that edit was preserved.');}
  for(i=0;i<selected.length;i++)selected[i].setSelected(false,false);
  for(i=0;i<remove.length;i++)remove[i].setSelected(true,false);
  if(remove.length){app.project.openSequence(main.sequenceID);main.unlinkSelection();for(i=remove.length-1;i>=0;i--)remove[i].remove(false,false);}
  var music=media(sound,b.soundtrack);place(main.audioTracks[0],music,0,b.duration,'Reel soundtrack');
  for(t=0;t<main.audioTracks.numTracks;t++)if(main.audioTracks[t].clips.numItems!==(t===0?1:0))throw Error('Premiere has not confirmed one clean soundtrack. Check audio before exporting.');
 }
 function audit(b){var s=seq(b.sequence);if(!s)throw Error('The prepared reel timeline is not present.');var video=[],audio=[];
  for(var t=0;t<s.videoTracks.numTracks;t++){var clips=[];for(var i=0;i<s.videoTracks[t].clips.numItems;i++){var c=s.videoTracks[t].clips[i];clips.push({name:c.name,start:c.start.seconds,end:c.end.seconds,source:c.projectItem.name,adjustment:c.isAdjustmentLayer?c.isAdjustmentLayer():false});}video.push({track:t+1,clips:clips});}
  for(t=0;t<s.audioTracks.numTracks;t++){clips=[];for(i=0;i<s.audioTracks[t].clips.numItems;i++){c=s.audioTracks[t].clips[i];clips.push({name:c.name,start:c.start.seconds,end:c.end.seconds,source:c.projectItem.getMediaPath()});}audio.push({track:t+1,clips:clips});}
  var count=0,m=s.markers.getFirstMarker();while(m){if(String(m.comments).indexOf('StorylensReel:'+b.id+':Beat:')===0)count++;m=s.markers.getNextMarker(m);}
  return {ok:true,project:app.project.path,sequence:s.name,sequence_id:String(s.sequenceID),fps:TICKS/Number(s.timebase),video:video,audio:audio,beat_markers:count,stage_two:'paused'};
 }
 function build(b){
  if(!b||b.version!==1||!/^[a-f0-9]{32}$/.test(b.id)||!b.sections||b.sections.length>1000||!b.cues||b.cues.length>1000)throw Error('Choose a valid saved Reel Recreate preparation.');
  if(!app.project.path)throw Error('Save the Premiere project before adding the reel.');
  var adj=adjustment(app.project.rootItem);if(!adj)throw Error('Create one Adjustment Layer with File > New > Adjustment Layer, then press Add again. The reel has not been changed.');
  var main=seq(b.sequence);
  if(!main){var destination=bin(app.project.rootItem,'Reel Recreate - '+b.id.substr(0,8));if(!app.project.importFiles([b.project],true,destination,false))throw Error('Premiere could not import the prepared reel project.');main=seq(b.sequence);}
  if(!main||main.videoTracks.numTracks!==5)throw Error('Premiere has not confirmed the prepared reel sequence. Check the Project panel before retrying.');
  var done=main.markers.getFirstMarker();while(done){if(done.comments==='StorylensReel:'+b.id+':Complete'){var soundBin=bin(bin(app.project.rootItem,'Reel Recreate - '+b.id.substr(0,8)),'Sound');soundtrackOnly(main,b,soundBin);app.project.openSequence(main.sequenceID);app.project.save();var checked=audit(b);checked.message='Stage one is ready: footage nests, Caption 3 lyrics, beat adjustments, grade layer and original soundtrack. Stage two stays paused.';write(b,'premiere-native-result.json',checked);stage(b,'Stage one is ready');return checked;}done=main.markers.getNextMarker(done);}
  var top=bin(app.project.rootItem,'Reel Recreate - '+b.id.substr(0,8)),slots=bin(top,'Media slots'),lyrics=bin(top,'Captions'),sound=bin(top,'Sound'),templates=bin(top,'Templates');
  stage(b,'Importing native Caption 3 graphics');
  var captions=seq(b.caption_sequence);if(!captions){if(!app.project.importFiles([b.caption_source_project],true,lyrics,false))throw Error('Premiere could not import the editable caption project.');captions=seq(b.caption_sequence);if(!captions)throw Error('Premiere has not confirmed the caption sequence. Check the Project panel.');}
  move(captions.projectItem,templates);
  // Replace only the initial source soundtrack of this generated starter.
  for(var at=0;at<main.audioTracks.numTracks;at++){var tr=main.audioTracks[at];for(var ai=tr.clips.numItems-1;ai>=0;ai--){var a=tr.clips[ai],p=a.projectItem.getMediaPath();if(p&&norm(p)===norm(b.source))a.remove(false,false);else if(a.name!=='Reel soundtrack')throw Error('An existing audio edit was preserved. Use a fresh prepared starter to build this reel.');}}
  var transparent=media(templates,b.placeholder),empty=seq('RR_EMPTY_TEMPLATE_'+b.id.substr(0,8));
  if(!empty){empty=app.project.createNewSequenceFromClips('RR_EMPTY_TEMPLATE_'+b.id.substr(0,8),[transparent],templates);if(!empty)throw Error('Premiere could not create a replacement-slot template.');empty.setSettings(main.getSettings());}
  stage(b,'Creating footage nests',{total:b.sections.length});
  for(var i=0;i<b.sections.length;i++){
   var section=b.sections[i],name='Footage '+('000'+(i+1)).slice(-3)+' - EMPTY'+(b.name_suffix||''),nested=seq(name);
   if(!nested){empty.setInPoint(0);empty.setOutPoint(section.end-section.start);nested=empty.createSubsequence(true);if(!nested)throw Error('Premiere could not create '+name);nested.name=name;move(nested.projectItem,slots);}
   place(main.videoTracks[0],nested.projectItem,section.start,section.end,name);
   if(i%10===0)stage(b,'Creating footage nests',{created:i+1,total:b.sections.length});
  }
  stage(b,'Creating editable lyric nests',{total:b.cues.length});
  var lyricEnds=[-1,-1];
  for(i=0;i<b.cues.length;i++){
   var cue=b.cues[i],name='Lyric '+('000'+(i+1)).slice(-3)+(b.name_suffix||''),nested=seq(name);
   if(!nested){captions.setInPoint(cue.start);captions.setOutPoint(cue.end);nested=captions.createSubsequence(true);if(!nested)throw Error('Premiere could not create '+name);nested.name=name;move(nested.projectItem,lyrics);}
   var lyricLane=lyricEnds[0]<=cue.start+.0001?0:1;
   if(lyricEnds[lyricLane]>cue.start+.0001)throw Error('More than two caption groups overlap. Their timing was preserved for review.');
   place(main.videoTracks[1+lyricLane],nested.projectItem,cue.start,cue.end,name);lyricEnds[lyricLane]=cue.end;
  }
  stage(b,'Placing short beat adjustment clips');
  var frames=Math.round(b.duration*b.fps);
  for(i=0;i<b.beats.length;i++){
   var beat=b.beats[i].frame,left=Math.max(0,beat-3,i?Math.ceil((beat+b.beats[i-1].frame)/2):0),right=Math.min(frames,beat+3,i+1<b.beats.length?Math.floor((beat+b.beats[i+1].frame)/2):frames);
   place(main.videoTracks[3],adj,left/b.fps,Math.max(left+1,right)/b.fps,'FX BEAT '+('000'+(i+1)).slice(-3)+' - DROP EFFECT HERE');
  }
  place(main.videoTracks[4],adj,0,b.duration,'COLOR GRADE - DROP YOUR PRESET HERE');marks(main,b.id,b.beats);
  stage(b,'Importing original sound choices',{total:b.sounds.length});
  var options=bin(top,'SFX OPTIONS - NOT PLACED');
  for(i=0;i<b.sounds.length;i++){var row=b.sounds[i];media(bin(options,row.group),row.file);}
  stage(b,'Keeping one original soundtrack');soundtrackOnly(main,b,sound);
  main.setInPoint(0);main.setOutPoint(b.duration);main.setPlayerPosition(String(Math.round(36.4*TICKS)));app.project.openSequence(main.sequenceID);
  var marker=main.markers.createMarker(0);marker.name='Storylens stage one';marker.comments='StorylensReel:'+b.id+':Complete';
  app.project.save();var result=audit(b);result.message='Created '+b.sections.length+' footage nests, '+b.cues.length+' lyric nests, '+b.beats.length+' beat markers and adjustment clips. Stage two stays paused.';write(b,'premiere-native-result.json',result);stage(b,'Stage one is ready');return result;
 }
 return {build:function(b){try{return json(build(b));}catch(e){try{stage(b,'Stopped — saved project is preserved',{error:String(e)});}catch(ignore){}return json({error:String(e)});}},audit:function(b){try{var result=audit(b);write(b,'premiere-native-audit.json',result);return json(result);}catch(e){return json({error:String(e)});}}};
})();
