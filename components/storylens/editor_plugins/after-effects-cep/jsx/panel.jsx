/* Public AE scripting API. All generated edits are new compositions or explicit assets. */
var storylensPanelProject=null,storylensPanelUnsavedId='unsaved-'+new Date().getTime();
function storylensProjectId(){var project=app.project,same=false;try{same=storylensPanelProject===project;}catch(_){}if(!same){storylensPanelProject=project;storylensPanelUnsavedId='unsaved-'+new Date().getTime();}return project.file?project.file.fsName:storylensPanelUnsavedId;}
function storylensCurrentComp(){var comp=app.project.activeItem;if(!(comp instanceof CompItem))throw Error('Open the composition you want to use first.');return comp;}
function storylensExpected(manifest){var expected=manifest.expected;if(expected&&expected.project_id&&expected.project_id!==storylensProjectId())throw Error('The project changed. Reconnect the current timeline before importing.');if(expected&&expected.sequence_id&&String(storylensCurrentComp().id)!==String(expected.sequence_id))throw Error('The active composition changed. Reconnect before adding this result.');}
function storylensPanelContext(){try{var comp=storylensCurrentComp(),clips=[],unsupported=[],i,layer,source;
 for(i=1;i<=comp.numLayers;i++){layer=comp.layer(i);if(!layer.enabled&&!layer.audioEnabled)continue;source=layer.source;
  if(!(source instanceof FootageItem)||!source.file||source.mainSource.isStill){unsupported.push(layer.name+': use straight video footage');continue;}
  if(layer.timeRemapEnabled||layer.stretch!==100)unsupported.push(layer.name+': time remapping or speed');
  if(layer.property('ADBE Effect Parade').numProperties)unsupported.push(layer.name+': native effects');
  var transform=layer.property('ADBE Transform Group'),scale=transform.property('ADBE Scale'),position=transform.property('ADBE Position');
  if(scale.numKeys||position.numKeys||transform.property('ADBE Rotate Z').numKeys)unsupported.push(layer.name+': animated transform');
  var anchor=transform.property('ADBE Anchor Point').value,sv=scale.value,pv=position.value;
  if(layer.threeDLayer||Math.abs(sv[0]-100)>.001||Math.abs(sv[1]-100)>.001||Math.abs(pv[0]-comp.width/2)>.001||Math.abs(pv[1]-comp.height/2)>.001||Math.abs(anchor[0]-source.width/2)>.001||Math.abs(anchor[1]-source.height/2)>.001||transform.property('ADBE Rotate Z').value!==0||transform.property('ADBE Opacity').value!==100||layer.property('ADBE Mask Parade').numProperties)unsupported.push(layer.name+': transformed or masked footage');
  clips.push({path:source.file.fsName,start:Math.max(0,layer.inPoint),end:Math.min(comp.duration,layer.outPoint),source_in:Math.max(0,layer.inPoint-layer.startTime),kind:source.hasVideo?'video':'audio',track:0,stretch:layer.stretch});
 }
 return hJSON({host:'aftereffects',project_id:storylensProjectId(),sequence_id:String(comp.id),name:comp.name,width:comp.width,height:comp.height,fps:comp.frameRate,duration:comp.duration,clips:clips,unsupported:unsupported});
}catch(e){return hJSON({error:e.toString()});}}
function storylensPanelSelectedMedia(){return hinglishSelectedMedia();}
function storylensPanelProjectContext(){try{if(!app.project)throw Error('Open an After Effects project first.');return hJSON({host:'aftereffects',project_id:storylensProjectId(),project_path:app.project.file?app.project.file.fsName:'',sequence_id:'_project_',name:app.project.file?app.project.file.name:'Untitled project'});}catch(e){return hJSON({error:e.toString()});}}
function storylensPanelMusic(){try{var comp=storylensCurrentComp(),layers=comp.selectedLayers;if(layers.length!==1||!layers[0].source||!layers[0].source.file||!layers[0].source.hasAudio)throw Error('Select one music layer in the active composition.');var layer=layers[0];return hJSON({path:layer.source.file.fsName,source_in:layer.inPoint-layer.startTime,source_out:layer.outPoint-layer.startTime,timeline_start:layer.inPoint,fps:comp.frameRate,sequence_id:String(comp.id)});}catch(e){return hJSON({error:e.toString()});}}
function storylensFolder(name,parent){var items=parent?parent.items:app.project.items;for(var i=1;i<=items.length;i++){var item=items[i];if(item instanceof FolderItem&&item.name===name)return item;}var folder=app.project.items.addFolder(name);if(parent)folder.parentFolder=parent;return folder;}
function storylensFootage(path,folder){var file=new File(path);if(!file.exists)throw Error('Downloaded media is missing. Open its output folder and relink it.');for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(item instanceof FootageItem&&item.file&&item.file.fsName===file.fsName)return item;}var footage=app.project.importFile(new ImportOptions(file));footage.parentFolder=folder;return footage;}
function storylensColor(value){if(value instanceof Array)return value;var text=String(value||'#ffffff').replace('#','');return [parseInt(text.substr(0,2),16)/255,parseInt(text.substr(2,2),16)/255,parseInt(text.substr(4,2),16)/255];}
function storylensAEMotion(layer,clip,manifest){
 var transform=layer.property('ADBE Transform Group'),motion=clip.motion||{},value;
 if(motion.scale){value=Number(motion.scale.value);transform.property('ADBE Scale').setValue([value,value]);}
 if(motion.center){value=motion.center.value;transform.property('ADBE Position').setValue([manifest.width*(.5+value[0]),manifest.height*(.5+value[1])]);}
 if(motion.rotation)transform.property('ADBE Rotate Z').setValue(Number(motion.rotation.value));
 if(motion.opacity)transform.property('ADBE Opacity').setValue(Number(motion.opacity.value));
 if(motion.level){value=Number(motion.level.value);value=value>0?Math.max(-192,20*Math.log(value)/Math.LN10):-192;layer.property('ADBE Audio Group').property('ADBE Audio Levels').setValue([value,value]);}
}
function storylensFontName(word){
 if(word.font_name)return word.font_name;
 if(!word.font_path)throw Error('This caption has no saved font. Reopen its saved caption project before importing.');
 var parts=String(word.font_path).split(String.fromCharCode(92)).join('/').split('/');
 return parts[parts.length-1].replace(/\.[^.]+$/,'');
}
function storylensTracking(word){var size=Number(word.size_px),spacing=Number(word.tracking||0);if(!isFinite(size)||size<=0||!isFinite(spacing))throw Error('A caption has an invalid font size or spacing. Review its saved style and retry.');return Math.round(spacing*1000);}
function storylensAEWords(manifest){
 var original=storylensCurrentComp(),comp=original.duplicate();comp.name=original.name+' - Storylens Captions';
 var captions=storylensFolder('Auto Captions',app.project.rootFolder),standard=storylensFolder('Standard',captions),style=storylensFolder(manifest.name||'Captions',standard);comp.parentFolder=style;
 for(var i=0;i<manifest.words.length;i++){var word=manifest.words[i],layer=comp.layers.addText(word.text),documentProperty=layer.property('ADBE Text Properties').property('ADBE Text Document'),documentValue=documentProperty.value;
  documentValue.fontSize=word.size_px;documentValue.font=storylensFontName(word);documentValue.applyFill=!word.outline;documentValue.fillColor=storylensColor(word.color);documentValue.applyStroke=Boolean(word.outline||word.stroke_width);if(documentValue.applyStroke){documentValue.strokeColor=storylensColor(word.stroke_color||word.color);documentValue.strokeWidth=word.stroke_width||1;}
  documentValue.tracking=storylensTracking(word);documentValue.justification=ParagraphJustification.LEFT_JUSTIFY;documentProperty.setValue(documentValue);
  layer.name=word.text;layer.inPoint=word.start;layer.outPoint=word.end;
  var rect=layer.sourceRectAtTime(word.start,false),transform=layer.property('ADBE Transform Group');transform.property('ADBE Anchor Point').setValue([rect.left+rect.width/2,rect.top+rect.height/2]);
  var animation=word.animation||[],position=transform.property('ADBE Position'),scale=transform.property('ADBE Scale'),opacity=transform.property('ADBE Opacity');
  for(var k=0;k<animation.length;k++){var key=animation[k],time=word.start+key.time;position.setValueAtTime(time,[key.x,key.y]);scale.setValueAtTime(time,[100*key.sx,100*key.sy]);opacity.setValueAtTime(time,100*key.alpha);}
 }
 if(manifest.decorations){var folder=storylensFolder('Storylens caption artwork',style),art=storylensFootage(manifest.decorations,folder);comp.layers.add(art);}
 comp.openInViewer();return {ok:true,message:'Created '+comp.name+' with '+manifest.words.length+' editable word layers.',composition_id:String(comp.id)};
}
function storylensRecreate(manifest){
 if(!manifest||manifest.version!==1||!manifest.caption||!manifest.sections||!manifest.audio)throw Error('Prepare the reel again before importing.');
 var revision=String(manifest.revision_id||'');if(revision&&!/^[0-9a-f]{32}$/.test(revision))throw Error('This reel revision is invalid. Update captions and style again.');
 var width=Number(manifest.width),height=Number(manifest.height),duration=Number(manifest.duration),fps=Number(manifest.fps);
 if(!(width>0&&height>0&&duration>0&&duration<=3600&&fps>0&&manifest.sections.length<=1000))throw Error('The reel timeline has invalid dimensions or duration.');
 var words=manifest.caption.words||[];if(!words.length||words.length>5000)throw Error('The saved reel has no usable captions or too many text layers. Review the captions and retry.');
 if(!new File(manifest.audio).exists)throw Error('The reel soundtrack is missing. Reconnect the source MP4 and retry.');
 for(var v=0;v<words.length;v++){var candidate=words[v];if(!candidate.text||!storylensFontName(candidate)||!isFinite(Number(candidate.start))||!isFinite(Number(candidate.end))||Number(candidate.start)<0||Number(candidate.end)>duration+.05||Number(candidate.end)<=Number(candidate.start))throw Error('A saved caption has invalid text or timing. Review the caption project and retry.');storylensTracking(candidate);var motion=candidate.animation||[];for(var m=0;m<motion.length;m++){var keyframe=motion[m];if(!isFinite(Number(keyframe.time))||!isFinite(Number(keyframe.x))||!isFinite(Number(keyframe.y))||!isFinite(Number(keyframe.alpha))||!isFinite(Number(keyframe.sx===undefined?1:keyframe.sx))||!isFinite(Number(keyframe.sy===undefined?1:keyframe.sy)))throw Error('A saved caption has invalid motion. Review its style and retry.');}}
 for(v=0;v<manifest.sections.length;v++){var segment=manifest.sections[v];if(!isFinite(Number(segment.start))||!isFinite(Number(segment.end))||Number(segment.start)<0||Number(segment.end)>duration+.05||Number(segment.end)<=Number(segment.start))throw Error('A beat section has invalid timing. Prepare the reel again.');}
 var identity='StorylensReel:'+String(manifest.id)+(revision?':'+revision:'');for(v=1;v<=app.project.numItems;v++){var existing=app.project.item(v);if(existing instanceof CompItem&&existing.comment===identity){existing.openInViewer();return {ok:true,message:'This caption version is already in the project. Opened its existing composition.',composition_id:String(existing.id),already_present:true};}}
 var known={};for(v=1;v<=app.project.numItems;v++)known[String(app.project.item(v).id)]=true;
 try{
 var top=storylensFolder('Reel Recreate',app.project.rootFolder),folder=app.project.items.addFolder(String(manifest.id).substr(0,12)+(revision?' - R'+String(manifest.revision_number||'?'):' - Original')+' - '+new Date().getTime());folder.parentFolder=top;
 var comp=app.project.items.addComp('Reel Recreate - '+String(manifest.id).substr(0,8)+(revision?' - R'+String(manifest.revision_number||'?')+' '+String(manifest.caption.style||'Captions'):' - Original'),width,height,1,duration,fps);comp.parentFolder=folder;
 var mediaFolder=storylensFolder('Media slots',folder),captionFolder=storylensFolder('Captions',folder),soundFolder=storylensFolder('Sound',folder);
 var audio=storylensFootage(manifest.audio,soundFolder),music=comp.layers.add(audio);music.name='Reel soundtrack';music.startTime=0;music.inPoint=0;music.outPoint=Math.min(duration,audio.duration);music.enabled=false;music.audioEnabled=true;
 var marks=manifest.beats||[];for(var b=0;b<marks.length;b++){var t=Number(marks[b].timeline_seconds);if(t>=0&&t<duration){var label='Beat '+(b+1);music.property('ADBE Marker').setValueAtTime(t,new MarkerValue(label));comp.markerProperty.setValueAtTime(t,new MarkerValue(label));}}
 for(var s=manifest.sections.length-1;s>=0;s--){var section=manifest.sections[s],span=Number(section.end)-Number(section.start);if(!(span>0))continue;
  var slot=app.project.items.addComp(section.name,width,height,1,span,fps);slot.parentFolder=mediaFolder;
  var placeholder=slot.layers.addSolid([.08,.10,.13],'Replace with your video or photo',width,height,1,span);placeholder.enabled=false;
  var placed=comp.layers.add(slot);placed.name=section.name+' - replace media inside';placed.startTime=Number(section.start);placed.inPoint=Number(section.start);placed.outPoint=Number(section.end);
 }
 var byCue={};for(var i=0;i<words.length;i++){var word=words[i],key=String(word.cue);if(!byCue[key])byCue[key]=[];byCue[key].push(word);}
 var keys=[];for(var k in byCue)if(byCue.hasOwnProperty(k))keys.push(k);keys.sort(function(a,b){return Number(a)-Number(b);});
 for(var ci=keys.length-1;ci>=0;ci--){var group=byCue[keys[ci]],begin=duration,end=0;for(i=0;i<group.length;i++){begin=Math.min(begin,Number(group[i].start));end=Math.max(end,Number(group[i].end));}if(!(end>begin))continue;
  var textComp=app.project.items.addComp('Caption '+('000'+(Number(keys[ci])+1)).slice(-3),width,height,1,end-begin,fps);textComp.parentFolder=captionFolder;
  for(i=0;i<group.length;i++){word=group[i];var text=textComp.layers.addText(word.text),property=text.property('ADBE Text Properties').property('ADBE Text Document'),doc=property.value;
   doc.font=storylensFontName(word);doc.fontSize=Number(word.size_px);doc.applyFill=!word.outline;doc.fillColor=storylensColor(word.color);doc.applyStroke=Boolean(word.outline||word.stroke_width);if(doc.applyStroke){doc.strokeColor=storylensColor(word.stroke_color||word.color);doc.strokeWidth=Number(word.stroke_width||1);}doc.tracking=storylensTracking(word);doc.justification=ParagraphJustification.LEFT_JUSTIFY;property.setValue(doc);
   text.name=word.text;text.inPoint=Math.max(0,Number(word.start)-begin);text.outPoint=Math.min(end-begin,Number(word.end)-begin);
   var rect=text.sourceRectAtTime(0,false),transform=text.property('ADBE Transform Group');transform.property('ADBE Anchor Point').setValue([rect.left+rect.width/2,rect.top+rect.height/2]);
   var animation=word.animation||[],position=transform.property('ADBE Position'),scale=transform.property('ADBE Scale'),opacity=transform.property('ADBE Opacity');
   for(var j=0;j<animation.length;j++){var a=animation[j],time=Number(word.start)-begin+Number(a.time);if(time<0||time>end-begin)continue;position.setValueAtTime(time,[Number(a.x),Number(a.y)]);scale.setValueAtTime(time,[100*Number(a.sx||1),100*Number(a.sy||1)]);opacity.setValueAtTime(time,100*Number(a.alpha));}
  }
  var captionLayer=comp.layers.add(textComp);captionLayer.name=textComp.name+' - move together';captionLayer.startTime=begin;captionLayer.inPoint=begin;captionLayer.outPoint=end;
 }
 comp.comment=identity;comp.openInViewer();return {ok:true,message:'Created '+manifest.sections.length+' media slots, '+keys.length+' caption precomps and '+marks.length+' beat markers.',composition_id:String(comp.id)};
 }catch(problem){var cleanup=[];for(var pass=0;pass<3;pass++){for(var index=app.project.numItems;index>=1;index--){var item=app.project.item(index);if(!known[String(item.id)])try{item.remove()}catch(removeError){cleanup.push(String(removeError));}}}if(cleanup.length)throw Error(String(problem)+'; some new items could not be removed: '+cleanup[0]);throw problem;}
}
function storylensPanelImport(manifest){var comp=null;if(manifest.type==='photos'){try{if(manifest.panel_project_id&&manifest.panel_project_id!==storylensProjectId())throw Error('The project changed. Reconnect before importing photos.');return hJSON(storylensPhotoImportAE(manifest));}catch(e){return hJSON({error:e.toString()});}}app.beginUndoGroup('Storylens result');try{storylensExpected(manifest);
 if(manifest.type==='reel_recreate')return hJSON(storylensRecreate(manifest));
 if(manifest.type==='captions')return hJSON(storylensAEWords(manifest));
 if(manifest.type==='layers'||manifest.type==='cuts'){
  comp=app.project.items.addComp(manifest.name,manifest.width,manifest.height,1,manifest.duration,manifest.fps);var folder=storylensFolder(manifest.name),cache={},hasAudio=false,i,c,footage,layer;
  comp.parentFolder=folder;for(i=0;i<manifest.clips.length;i++)if(manifest.clips[i].kind==='audio')hasAudio=true;
  for(i=manifest.clips.length-1;i>=0;i--){c=manifest.clips[i];footage=cache[c.path]||storylensFootage(c.path,folder);cache[c.path]=footage;layer=comp.layers.add(footage);layer.startTime=c.start-c.source_in;layer.inPoint=c.start;layer.outPoint=c.end;if(c.kind==='audio'){layer.enabled=false;layer.audioEnabled=true;}else layer.audioEnabled=!hasAudio;
   storylensAEMotion(layer,c,manifest);
  }
  if(manifest.keyword_folders){var soundBin=storylensFolder('Sound Design',folder);for(var g=0;g<manifest.keyword_folders.length;g++){var group=manifest.keyword_folders[g],keywordBin=storylensFolder(group.name,soundBin);for(var f=0;f<group.files.length;f++)storylensFootage(group.files[f].path,keywordBin);}}
  comp.openInViewer();return hJSON({ok:true,message:'Created '+comp.name+' with '+manifest.clips.length+' separate media layers.',composition_id:String(comp.id)});
 }
 if(manifest.type!=='assets'&&manifest.type!=='rendered')throw Error('Choose a supported Storylens import.');
 var paths=manifest.paths||[],images=true;for(var p=0;p<paths.length;p++)if(!/\.(png|jpg|jpeg|webp)$/i.test(paths[p]))images=false;
 var folder=storylensFolder(manifest.name||'Storylens media',images?storylensFolder('Images'):null),imported=[];try{comp=storylensCurrentComp();}catch(_){}
 for(var j=0;j<paths.length;j++){var footage=storylensFootage(paths[j],folder);imported.push(footage.name);if(!images&&manifest.insert&&comp){var layer=comp.layers.add(footage);layer.startTime=comp.time;layer.inPoint=comp.time;layer.outPoint=Math.min(comp.duration,comp.time+footage.duration);}}
 return hJSON({ok:true,message:'Imported '+paths.length+' file(s) into '+folder.name+(comp&&!images?' and the current composition.':'.'),imported:imported});
}catch(e){return hJSON({error:e.toString()});}finally{app.endUndoGroup();}}
function storylensPanelMarkBeats(plan){app.beginUndoGroup('Storylens beat markers');try{var comp=storylensCurrentComp();if(plan.sequence_id&&String(comp.id)!==String(plan.sequence_id))throw Error('The active composition changed. Detect the music again.');for(var i=0;i<plan.beats.length;i++){var beat=plan.beats[i],time=Number(beat.timeline_seconds);if(!isFinite(time))time=Number(plan.timeline_start||0)+Number(beat.frame)/Number(plan.fps);if(time>=0&&time<=comp.duration)comp.markerProperty.setValueAtTime(time,new MarkerValue('Storylens beat '+(i+1)));}return hJSON({ok:true,message:'Added '+plan.beats.length+' beat markers.'});}catch(e){return hJSON({error:e.toString()});}finally{app.endUndoGroup();}}
function storylensPanelBeatEffects(){return hJSON({error:'Beat markers are supported here. Apply Smart Zoom for speech-aware motion; beat-effect keyframes require separate validation.'});}
