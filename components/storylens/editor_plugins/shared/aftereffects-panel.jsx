/* Public AE scripting API. All generated edits are new compositions or explicit assets. */
if(typeof storylensPanelProject==='undefined')storylensPanelProject=null;
if(typeof storylensPanelUnsavedId==='undefined')storylensPanelUnsavedId='unsaved-'+new Date().getTime();
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
 if(manifest.curation_action)return storylensCurationNative(manifest);
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
function storylensPanelImport(manifest){if(manifest.type==='reel_recreate'&&manifest.curation_action){try{storylensExpected(manifest);return hJSON(storylensRecreate(manifest));}catch(e){return hJSON({error:e.toString()});}}var comp=null;if(manifest.type==='photos'){try{if(manifest.panel_project_id&&manifest.panel_project_id!==storylensProjectId())throw Error('The project changed. Reconnect before importing photos.');return hJSON(storylensPhotoImportAE(manifest));}catch(e){return hJSON({error:e.toString()});}}app.beginUndoGroup('Storylens result');try{storylensExpected(manifest);
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

/* Source-bound adapter for inspected Reel Recreate media holders. */
function storylensCurationItem(id){
 for(var i=1;i<=app.project.numItems;i++)if(String(app.project.item(i).id)===String(id))return app.project.item(i);
 throw Error('The inspected composition is no longer present. Inspect the template again.');
}
function storylensCurationProperties(group){
 storylensCurationBudget();
 var rows=[];
 for(var i=1;i<=group.numProperties;i++){
  var p=group.property(i),r={matchName:p.matchName,name:p.name};
  if(p.numProperties)r.children=storylensCurationProperties(p);
  else {
   r.keys=p.numKeys||0;
   if(p.canSetExpression){r.expression=p.expression||'';r.expressionEnabled=p.expressionEnabled;r.expressionError=p.expressionError||'';}
   if(p.propertyValueType!==PropertyValueType.NO_VALUE&&p.propertyValueType!==PropertyValueType.CUSTOM_VALUE){
    try{var v=p.valueAtTime(0,true);if(v instanceof Array||typeof v==='number'||typeof v==='string'||typeof v==='boolean')r.value=v;
     else if(v&&typeof v.text!=='undefined')r.value={text:v.text,font:v.font,fontSize:v.fontSize,tracking:v.tracking,fillColor:v.fillColor};
     else if(v&&typeof v.vertices!=='undefined')r.value={vertices:v.vertices,inTangents:v.inTangents,outTangents:v.outTangents,closed:v.closed};
    }catch(_){}
   }
   if(r.keys){r.keyframes=[];for(var k=1;k<=r.keys;k++){var key={time:p.keyTime(k)};try{var kv=p.keyValue(k);if(kv instanceof Array||typeof kv==='number'||typeof kv==='string'||typeof kv==='boolean')key.value=kv;else if(kv&&typeof kv.text!=='undefined')key.value={text:kv.text,font:kv.font,fontSize:kv.fontSize,tracking:kv.tracking};else if(kv&&typeof kv.comment!=='undefined')key.value={comment:kv.comment,duration:kv.duration};key.inType=String(p.keyInInterpolationType(k));key.outType=String(p.keyOutInterpolationType(k));}catch(_){}r.keyframes.push(key);}}
  }
  rows.push(r);
 }
 return rows;
}
function storylensCurationInspect(comp){
 if(!(comp instanceof CompItem))throw Error('Select a real Reel Recreate composition.');
 var seen={},comps=[],slots=[],issues=[],effects={},fonts={};
 var availableEffects={};try{var installedEffects=app.effects;for(var z=0;z<installedEffects.length;z++)availableEffects[installedEffects[z].matchName]=true;}catch(_){issues.push('Effect availability could not be inspected.');}
 function propertyChecks(group){
  for(var i=1;i<=group.numProperties;i++){var p=group.property(i);
   if(p.canSetExpression&&p.expression){
    if(/\bcomp\s*\(/.test(p.expression))issues.push('External or name-based composition expression needs a specialized adapter: '+p.name);
    if(p.expressionError)issues.push('Expression error: '+p.expressionError);
   }
   if(p.numProperties)propertyChecks(p);
  }
 }
 function walk(c,path){
  if(seen[String(c.id)])return;seen[String(c.id)]=true;
  var cr={id:String(c.id),name:c.name,path:path,width:c.width,height:c.height,fps:c.frameRate,duration:c.duration,layers:[]};comps.push(cr);
  for(var i=1;i<=c.numLayers;i++){
   storylensCurationBudget('comp '+c.id+' layer '+i+' / '+c.numLayers);
   var layer=c.layer(i),source=layer.source;
   var lr={id:String(layer.id),index:i,name:layer.name,inPoint:layer.inPoint,outPoint:layer.outPoint,startTime:layer.startTime,stretch:layer.stretch,enabled:layer.enabled,audioEnabled:layer.audioEnabled,locked:layer.locked,source_id:source?String(source.id):null,properties:storylensCurationProperties(layer)};cr.layers.push(lr);
   propertyChecks(layer);
   var fx=layer.property('ADBE Effect Parade');if(fx)for(var f=1;f<=fx.numProperties;f++){var match=fx.property(f).matchName;effects[match]=true;if(!availableEffects[match])issues.push('Required effect is unavailable: '+match);}
   var tp=layer.property('ADBE Text Properties');if(tp){var doc=tp.property('ADBE Text Document').valueAtTime(0,true);fonts[doc.font]=true;try{var matches=app.fonts.getFontsByPostScriptName(doc.font),realFont=false;for(var fi=0;fi<matches.length;fi++)if(!matches[fi].isSubstitute)realFont=true;if(!realFont)issues.push('Required font is unavailable: '+doc.font);}catch(_){issues.push('Cannot verify font availability: '+doc.font);}}
   if(source instanceof CompItem)walk(source,path.concat([{comp_id:String(c.id),layer_id:String(layer.id),source_id:String(source.id)}]));
   else if(source instanceof FootageItem){
    if(source.footageMissing)issues.push('Missing footage: '+source.name);
    if(layer.name==='Replace with your video or photo'){
     if(layer.timeRemapEnabled||layer.stretch!==100)issues.push('Retimed media holder needs an explicit time map: '+layer.name);
     slots.push({slot_id:String(c.id)+':'+String(layer.id),comp_id:String(c.id),comp_path:path,layer_locator:{layer_id:String(layer.id),source_id:String(source.id),name:layer.name},duration_frames:Math.round((layer.outPoint-layer.inPoint)*c.frameRate),fps:c.frameRate,canvas:[source.width,source.height],in_point:layer.inPoint,out_point:layer.outPoint,start_time:layer.startTime,fit_policy:'contain',audio_policy:'preserve_template_audio'});
    }
   }
  }
 }
 walk(comp,[]);var fontNames=[],effectNames=[];for(var name in fonts)if(fonts.hasOwnProperty(name))fontNames.push(name);for(name in effects)if(effects.hasOwnProperty(name))effectNames.push(name);
 return {adapter_version:1,root_comp_id:String(comp.id),project_id:storylensProjectId(),project_path:app.project.file?app.project.file.fsName:'',compositions:comps,slots:slots,fonts:fontNames,effects:effectNames,unsupported:issues,supported:issues.length===0&&slots.length>0};
}
function storylensCurationNative(p){
 storylensCurationStarted=(new Date()).getTime();storylensCurationTrace=p.diagnostic_path||'';
 storylensCurationBudget('starting '+p.curation_action);
 if(p.curation_action==='catalog'){
  var choices=[];for(var ci=1;ci<=app.project.numItems;ci++){var item=app.project.item(ci);if(item instanceof CompItem)choices.push({id:String(item.id),name:item.name,fps:item.frameRate,duration:item.duration});}
  return {project_path:app.project.file?app.project.file.fsName:'',compositions:choices};
 }
 if(p.project_path&&(!app.project.file||app.project.file.fsName!==new File(p.project_path).fsName))throw Error('The connected project changed. Reload the composition list.');
 if(p.open_template){
  var openFile=new File(p.open_template);
  if(!openFile.exists)throw Error('The saved acceptance template is missing.');
  if(!app.project.file||app.project.file.fsName!==openFile.fsName){
   if(app.project.numItems!==0)throw Error('Open the intended template without replacing another project.');
   app.open(openFile);
  }
 }
 var root=storylensCurationItem(p.root_comp_id);
 if(p.curation_action==='intro_variants')return storylensCurationIntroVariants(p,root);
 if(p.curation_action==='render'){
  if(!(root instanceof CompItem)||!app.project.file||app.project.file.fsName!==new File(p.project_path).fsName)throw Error('Open the exact populated project before rendering.');
  var output=new File(p.output_path);if(output.exists)throw Error('The render already exists; inspect it rather than overwrite.');
  var oldStart=root.workAreaStart,oldDuration=root.workAreaDuration;
  try{root.workAreaStart=0;root.workAreaDuration=root.duration;root.openInViewer();return {render_json:hinglishExportActiveSequence(output.fsName),composition_id:String(root.id),frame_count:Math.round(root.duration*root.frameRate)};}
  finally{root.workAreaStart=oldStart;root.workAreaDuration=oldDuration;}
 }
 var before=storylensCurationInspect(root);
 storylensCurationBudget('inspection complete');
 if(p.curation_action==='inspect'){
  if(p.save_path){var sourceFile=new File(p.save_path);if(sourceFile.exists&&(!app.project.file||sourceFile.fsName!==app.project.file.fsName))throw Error('Choose a new template snapshot path.');app.project.save(sourceFile);before=storylensCurationInspect(root);}
  var encoded=storylensCurationJSON(before,[],{count:0});
  storylensCurationBudget('serialized '+encoded.length+' bytes');
  if(!p.manifest_path)throw Error('Provide a local inspected manifest destination.');
  var mf=new File(p.manifest_path);mf.encoding='UTF-8';if(!mf.open('w'))throw Error('Cannot save the inspected manifest.');mf.write(encoded);mf.close();
  return {manifest_path:mf.fsName,root_comp_id:before.root_comp_id,project_id:before.project_id,project_path:before.project_path,slot_count:before.slots.length,composition_count:before.compositions.length,fonts:before.fonts,effects:before.effects,supported:before.supported,unsupported:before.unsupported};
 }
 if(p.curation_action!=='populate')throw Error('Choose template inspection or isolated population.');
 if(!before.supported)throw Error('Unsupported template: '+before.unsupported.join('; '));
 if(!app.project.file||app.project.file.fsName!==new File(p.template_path).fsName)throw Error('The inspected template project changed.');
 var expectedFile=new File(p.expected_manifest_path);if(!expectedFile.exists||!expectedFile.open('r'))throw Error('The inspected template manifest is missing.');var expectedText=expectedFile.read();expectedFile.close();
 if(expectedText!==storylensCurationJSON(before,[],{count:0}))throw Error('Template dependencies changed after inspection. Inspect again.');
 var destination=new File(p.output_path);if(destination.exists)throw Error('The revision project already exists. Recover its receipt instead of overwriting it.');
 var assignments=p.assignments||[],bySlot={},i,k,map={},created=[],originalSnapshot=storylensCurationJSON(before.compositions,[],{count:0});
 if(assignments.length!==before.slots.length)throw Error('Assign every inspected slot explicitly.');
 for(i=0;i<assignments.length;i++){var a=assignments[i];if(bySlot[a.slot_id])throw Error('A slot was assigned twice.');bySlot[a.slot_id]=a;if(!new File(a.path).exists)throw Error('Candidate media is missing.');if(a.fit!=='contain'&&a.fit!=='cover')throw Error('Choose contain or cover explicitly.');}
 // Validate every assignment before creating anything.
 for(i=0;i<before.slots.length;i++){var slot=before.slots[i],a=bySlot[slot.slot_id];if(!a)throw Error('A slot assignment is missing.');if(a.duration*slot.fps+0.01<slot.duration_frames)throw Error('Candidate is shorter than the native slot; no freeze/loop was applied.');}
 var undoOpen=false;try{
  app.beginUndoGroup('Storylens Curation');undoOpen=true;
  var bin=app.project.items.addFolder('Curation '+p.revision_id);created.push(bin);
  for(i=0;i<before.compositions.length;i++){var original=storylensCurationItem(before.compositions[i].id),copy=original.duplicate();copy.name=original.name+' ['+p.revision_id+']';copy.parentFolder=bin;map[String(original.id)]=copy;created.push(copy);}
  for(k in map)if(map.hasOwnProperty(k)){var c=map[k];for(i=1;i<=c.numLayers;i++){var layer=c.layer(i),source=layer.source;if(source&&map[String(source.id)]){var locked=layer.locked,name=layer.name;layer.locked=false;layer.replaceSource(map[String(source.id)],false);layer.name=name;layer.locked=locked;}}}
  var filled=[];
  for(i=0;i<before.slots.length;i++){
   var slot=before.slots[i],a=bySlot[slot.slot_id],originalComp=storylensCurationItem(slot.comp_id),originalLayer=null;
   for(k=1;k<=originalComp.numLayers;k++)if(String(originalComp.layer(k).id)===slot.layer_locator.layer_id)originalLayer=originalComp.layer(k);
   if(!originalLayer||String(originalLayer.source.id)!==slot.layer_locator.source_id)throw Error('The exact holder identity changed.');
   var target=map[slot.comp_id].layer(originalLayer.index),file=app.project.importFile(new ImportOptions(new File(a.path)));created.push(file);file.parentFolder=bin;
   var duration=slot.duration_frames/slot.fps;if(file.duration+0.01<duration)throw Error('Decoded candidate is shorter than the slot.');
   var wrapper=app.project.items.addComp('Media '+slot.slot_id+' ['+p.revision_id+']',slot.canvas[0],slot.canvas[1],1,Math.max(duration,originalLayer.outPoint),slot.fps);created.push(wrapper);wrapper.parentFolder=bin;
   var media=wrapper.layers.add(file),scale=100*(a.fit==='cover'?Math.max(wrapper.width/file.width,wrapper.height/file.height):Math.min(wrapper.width/file.width,wrapper.height/file.height));media.property('ADBE Transform Group').property('ADBE Scale').setValue([scale,scale]);media.audioEnabled=false;
   var locked=target.locked,name=target.name;target.locked=false;target.replaceSource(wrapper,false);target.name=name;target.enabled=true;target.locked=locked;
   filled.push({slot_id:slot.slot_id,candidate_id:a.candidate_id,source_hash:a.source_hash,media_path:a.path,fit:a.fit,wrapper_id:String(wrapper.id),cloned_comp_id:String(map[slot.comp_id].id),layer_id:String(target.id)});
  }
  if(storylensCurationJSON(storylensCurationInspect(root).compositions,[],{count:0})!==originalSnapshot)throw Error('An original template dependency changed during population.');
  var master=map[String(root.id)];master.comment='StorylensCuration:'+p.revision_id;master.openInViewer();app.endUndoGroup();undoOpen=false;app.project.save(destination);
  return {ok:true,project_path:destination.fsName,composition_id:String(master.id),original_comp_id:String(root.id),original_dependencies_unchanged:true,mutable_compositions_cloned:before.compositions.length,filled:filled,frame_count:Math.round(master.duration*master.frameRate),fps:master.frameRate,canvas:[master.width,master.height],native_render_status:'pending'};
 }catch(error){if(undoOpen){try{app.endUndoGroup();}catch(_){}undoOpen=false;}for(var pass=0;pass<3;pass++)for(i=created.length-1;i>=0;i--)try{created[i].remove();}catch(_){}throw error;}
}
function storylensCurationBudget(message){
 if((new Date()).getTime()-storylensCurationStarted>45000)throw Error('Template inspection exceeded 45 seconds. Preserve the project and review the diagnostic progress.');
 if(message&&storylensCurationTrace){var f=new File(storylensCurationTrace);f.encoding='UTF-8';if(f.open('w')){f.write(message);f.close();}}
}
function storylensCurationJSON(v,parents,counter){
 counter.count++;if(counter.count%1000===0)storylensCurationBudget('serializing node '+counter.count);
 if(counter.count>250000||parents.length>64)throw Error('Template snapshot exceeds its bounded serialization budget.');
 if(v===null||typeof v==='undefined')return 'null';
 if(typeof v==='string')return hString(v);
 if(typeof v==='boolean')return v?'true':'false';
 if(typeof v==='number')return isFinite(v)?String(v):'null';
 for(var j=0;j<parents.length;j++)if(parents[j]===v)throw Error('A circular native value cannot be serialized.');
 var chain=parents.concat([v]),parts=[],i;
 if(v instanceof Array){for(i=0;i<v.length;i++)parts.push(storylensCurationJSON(v[i],chain,counter));return '['+parts.join(',')+']';}
 for(i in v)if(v.hasOwnProperty(i)){if(typeof v[i]==='function')throw Error('A native object escaped the plain-data snapshot.');parts.push(hString(i)+':'+storylensCurationJSON(v[i],chain,counter));}
 return '{'+parts.join(',')+'}';
}

function storylensDedicatedIntroSlot(body){
 var slot=null,eps=0.001;
 for(var i=1;i<=body.numLayers;i++){
  var layer=body.layer(i);
  if(layer.comment!=='storylens:dedicated-intro-slot')continue;
  if(slot)throw Error('Keep one explicitly marked dedicated intro slot.');
  var source=layer.source;
  if(!(source instanceof CompItem)||!layer.enabled||layer.timeRemapEnabled||layer.stretch!==100||
    Math.abs(layer.startTime)>eps||Math.abs(layer.inPoint)>eps||Math.abs(layer.outPoint-5)>eps||
    Math.abs(source.duration-5)>eps||body.duration<=5||source.frameRate!==body.frameRate||
    source.width!==body.width||source.height!==body.height||Math.abs(source.pixelAspect-body.pixelAspect)>eps){
   throw Error('The marked intro slot must be an enabled, unretimed, full-size five-second precomp at the start.');
  }
  slot={index:i,layer_id:String(layer.id)};
 }
 return slot;
}

/* Editable intro comparisons. Existing body is reused without property edits. */
function storylensCurationIntroVariants(p,body){
 if(!(body instanceof CompItem)||!app.project.file||app.project.file.fsName!==new File(p.project_path).fsName)throw Error('Open the exact saved body project.');
 var destination=new File(p.output_path);if(destination.exists)throw Error('This native revision already exists; recover its receipt.');
 var plans=p.plans||[];if(plans.length!==3)throw Error('Provide exactly three reviewed cinematic introductions.');
 var dedicated=storylensDedicatedIntroSlot(body);
 if(dedicated){
  var dedicatedManifest=storylensCurationInspect(body.layer(dedicated.index).source);
  if(dedicatedManifest.slots.length)throw Error('The dedicated intro must not contain a replaceable story-media slot.');
 }
 var mode=dedicated?'dedicated_slot':'prepend';
 var before=storylensCurationJSON(storylensCurationInspect(body).compositions,[],{count:0}),created=[],results=[];
 for(var n=0;n<plans.length;n++){
  var plan=plans[n],total=0;
  if(plan.fps!==body.frameRate||plan.frame_count!==Math.round(5*body.frameRate))throw Error('Intro and body frame rates must match, with exactly five seconds.');
  for(var j=0;j<plan.source_spans.length;j++){
   var span=plan.source_spans[j],source=p.sources[span.source_id];
   if(!source||!new File(source.path).exists||span.start<0||span.end<=span.start||span.frames/plan.fps>span.end-span.start+1/plan.fps)throw Error('Intro source span is invalid.');
   total+=span.frames;
  }
  if(total!==plan.frame_count)throw Error('Intro frames must exactly fill five seconds.');
 }
 var undoOpen=false;try{
  app.beginUndoGroup('Storylens Intro Comparisons');undoOpen=true;
  var bin=app.project.items.addFolder('Intro comparisons '+p.revision_id);created.push(bin);
  for(n=0;n<plans.length;n++){
   var plan=plans[n],intro=app.project.items.addComp('Intro_'+plan.variant+' ['+p.revision_id+']',body.width,body.height,body.pixelAspect,5,body.frameRate);created.push(intro);intro.parentFolder=bin;
   var cursor=0,trace=[];
   for(j=0;j<plan.source_spans.length;j++){
    var span=plan.source_spans[j],source=p.sources[span.source_id],file=app.project.importFile(new ImportOptions(new File(source.path)));created.push(file);file.parentFolder=bin;
    if(file.duration+1/plan.fps<span.end)throw Error('Actual source media is shorter than the reviewed span.');
    var layer=intro.layers.add(file),start=cursor/plan.fps,end=(cursor+span.frames)/plan.fps;
    layer.startTime=start-span.start;layer.inPoint=start;layer.outPoint=end;
    var scale=100*Math.min(intro.width/file.width,intro.height/file.height);layer.property('ADBE Transform Group').property('ADBE Scale').setValue([scale,scale]);
    layer.comment='candidate='+span.candidate_id+'; source_sha256='+source.hash+'; source_in='+span.start;
    trace.push({layer_id:String(layer.id),candidate_id:span.candidate_id,source_hash:source.hash,start_frame:cursor,end_frame:cursor+span.frames,source_in:span.start});cursor+=span.frames;
   }
   var name='Trial_'+plan.variant+' ['+p.revision_id+']';
   var trial=dedicated?body.duplicate():app.project.items.addComp(name,body.width,body.height,body.pixelAspect,5+body.duration,body.frameRate);
   created.push(trial);trial.name=name;trial.parentFolder=bin;
   if(dedicated){
    var holder=trial.layer(dedicated.index);
    if(holder.comment!=='storylens:dedicated-intro-slot')throw Error('The duplicate did not retain the dedicated slot identity.');
    var wasLocked=holder.locked;holder.locked=false;
    holder.replaceSource(intro,false);
    holder.locked=wasLocked;
   }else{
    var first=trial.layers.add(intro);first.inPoint=0;first.outPoint=5;
    var second=trial.layers.add(body);second.startTime=5;second.inPoint=5;second.outPoint=5+body.duration;
   }
   results.push({variant:plan.variant,intro_comp_id:String(intro.id),trial_comp_id:String(trial.id),body_comp_id:String(body.id),intro_frames:Math.round(intro.duration*intro.frameRate),trial_frames:Math.round(trial.duration*trial.frameRate),source_layers:trace,assembly_mode:mode,dedicated_slot_layer_id:dedicated?dedicated.layer_id:null});
  }
  if(before!==storylensCurationJSON(storylensCurationInspect(body).compositions,[],{count:0}))throw Error('The existing body changed during intro assembly.');
  storylensCurationItem(results[0].trial_comp_id).openInViewer();app.endUndoGroup();undoOpen=false;app.project.save(destination);
  return {ok:true,project_path:destination.fsName,body_comp_id:String(body.id),body_dependencies_unchanged:true,assembly_mode:mode,variants:results,render_status:'pending',sound_recipe_status:'not_applied',approval_state:'preview'};
 }catch(error){if(undoOpen){try{app.endUndoGroup();}catch(_){}undoOpen=false;}for(var pass=0;pass<3;pass++)for(var k=created.length-1;k>=0;k--)try{created[k].remove();}catch(_){}throw error;}
}
