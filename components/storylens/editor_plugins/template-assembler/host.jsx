#include "model.js"
/* Native Adobe operations. Never close, replace or save the owner's open project. */
if(typeof SLTA==='undefined')SLTA={cache:{},replies:{},pending:{}};
SLTA.quote=function(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029')+'"';};
SLTA.json=function(v){if(v===null||typeof v==='undefined')return 'null';if(typeof v==='string')return SLTA.quote(v);if(typeof v==='number')return isFinite(v)?String(v):'null';if(typeof v==='boolean')return String(v);var a=[],i;if(v instanceof Array){for(i=0;i<v.length;i++)a.push(SLTA.json(v[i]));return '['+a.join(',')+']';}for(i in v)if(v.hasOwnProperty(i))a.push(SLTA.quote(i)+':'+SLTA.json(v[i]));return '{'+a.join(',')+'}';};
SLTA.error=function(e){return SLTA.json({error:true,code:e.code||'template_native',details:String(e.message||e)});};
SLTA.item=function(id){for(var i=1;i<=app.project.numItems;i++)if(app.project.item(i).id===Number(id))return app.project.item(i);return null;};
SLTA.ae=function(){return typeof CompItem!=='undefined';};
SLTA.catalogDir=function(create){var folder=new Folder(Folder.myDocuments.fsName+'/Storylens');if(create&&!folder.exists)folder.create();folder=new Folder(folder.fsName+'/template-assemblies');if(create&&!folder.exists)folder.create();return folder;};
SLTA.catalogKey=function(path){var s=String(path).replace(/\\/g,'/').toLowerCase(),h=0;for(var i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))>>>0;return h.toString(16)+'.json';};
SLTA.writeCatalogue=function(result){try{var source=new File(result.path);result.sourceBytes=source.length;result.sourceModified=source.modified.getTime();var folder=SLTA.catalogDir(true),f=new File(folder.fsName+'/'+SLTA.catalogKey(result.path));f.encoding='UTF-8';if(!f.open('w'))throw new Error('Cannot write composition catalogue');f.write(SLTA.json(result));f.close();}catch(e){result.catalogWarning='Composition details could not be cached for Premiere: '+String(e);}};
SLTA.inspect=function(p){
  var file=new File(p.path),folder,key=file.fsName+'|'+(file.modified?file.modified.getTime():0),result,comps=[],missing=[],items=[],before=app.project?app.project.numItems:0,undo=false,suppress=false;
  try{
    if(!file.exists||!(/\.aepx?$/i.test(file.name)))throw new Error('The selected After Effects project is unavailable.');
    if(!file.length){var empty=new Error('This AEP file is empty: '+file.fsName+'. Choose a complete project file.');empty.code='template_settings';throw empty;}
    if(!app.project)app.newProject();
    var cached=SLTA.cache[key];
    if(cached&&SLTA.item(cached.folderId)&&SLTA.item(cached.folderId).comment===cached.token){SLTA.writeCatalogue(cached.result);return SLTA.json(cached.result);}
    app.beginUndoGroup('Storylens — inspect template');undo=true;app.beginSuppressDialogs();suppress=true;
    var options=new ImportOptions(file);folder=app.project.importFile(options);
    if(!(folder instanceof FolderItem))throw new Error('After Effects did not import a project folder.');
    var token='Storylens Template Assembler '+new Date().getTime();folder.comment=token;
    function walk(f,path){for(var i=1;i<=f.numItems;i++){var item=f.item(i);items.push(item);if(item instanceof FolderItem)walk(item,path+'/'+item.name);else if(item instanceof CompItem){var queued=false;for(var q=1;q<=app.project.renderQueue.numItems;q++)if(app.project.renderQueue.item(q).comp===item)queued=true;comps.push({id:item.id,name:item.name,folder:path,duration:item.duration,fps:item.frameRate,width:item.width,height:item.height,pixelAspect:item.pixelAspect,workAreaStart:item.workAreaStart,workAreaDuration:item.workAreaDuration,usedBy:item.usedIn.length,renderQueued:queued});}else if(item instanceof FootageItem&&item.footageMissing)missing.push(item.name);}}
    walk(folder,folder.name);
    if(!comps.length)throw new Error('This project has no compositions.');
    result={path:file.fsName,name:File.decode(file.name),folderId:folder.id,comps:comps,missingFootage:missing};
    SLTA.writeCatalogue(result);SLTA.cache[key]={folderId:folder.id,token:token,result:result};return SLTA.json(result);
  }catch(e){return SLTA.error(e);}finally{if(suppress)try{app.endSuppressDialogs(false);}catch(_){}if(undo)try{app.endUndoGroup();}catch(_){} }
};
SLTA.validateRows=function(p){
  var rows=[],i,c,r;
  for(i=0;i<p.rows.length;i++){
    r=p.rows[i];c=SLTA.item(r.comp.id);
    if(!(c instanceof CompItem)){var e=new Error('Template '+(i+1)+' is no longer in the open project. Read compositions again.');e.code='template_stale';throw e;}
    var parent=c.parentFolder,inside=false;while(parent&&parent!==app.project.rootFolder){if(parent.id===r.folderId){inside=true;break;}parent=parent.parentFolder;}
    if(!inside){var x=new Error('Template '+(i+1)+' belongs to a different imported project. Read compositions again.');x.code='template_stale';throw x;}
    rows.push({path:r.path,folderId:r.folderId,comp:{id:c.id,name:c.name,duration:c.duration,fps:c.frameRate,width:c.width,height:c.height,pixelAspect:c.pixelAspect,workAreaStart:c.workAreaStart,workAreaDuration:c.workAreaDuration}});
  }return rows;
};
SLTA.buildAE=function(p){
  var master=null,folder=null,undo=false;
  try{
    p.rows=SLTA.validateRows(p);var plan=SLTemplateModel.plan(p.rows,p.options),i,s,layer,source;
    app.beginUndoGroup('Storylens — assemble ordered templates');
    undo=true;
    folder=app.project.items.addFolder('Storylens Template Assembly '+new Date().getTime());
    master=app.project.items.addComp(p.name||'Storylens — Template Assembly',plan.width,plan.height,plan.pixelAspect,plan.duration,plan.fps);master.parentFolder=folder;
    for(i=0;i<plan.segments.length;i++){
      s=plan.segments[i];source=SLTA.item(p.rows[s.rowIndex].comp.id);layer=master.layers.add(source);layer.moveToEnd();
      layer.name=('0'+(s.rowIndex+1)).slice(-2)+' · '+source.name+(s.cycle>1?' · repeat '+s.cycle:'');
      layer.startTime=s.startFrame/plan.fps-s.sourceIn;layer.inPoint=s.startFrame/plan.fps;layer.outPoint=s.endFrame/plan.fps;
      var scale=Math.min(plan.width/source.width,plan.height/source.height)*100;layer.property('ADBE Transform Group').property('ADBE Scale').setValue([scale,scale]);
      layer.comment='Source: '+p.rows[s.rowIndex].path+'\nOrdered template '+(s.rowIndex+1)+', cycle '+s.cycle;
    }
    master.workAreaStart=0;master.workAreaDuration=master.duration;master.resolutionFactor=[4,4];master.openInViewer();
    var receipt=[];for(i=1;i<=master.numLayers;i++){layer=master.layer(i);receipt.push({name:layer.name,sourceId:layer.source.id,start:layer.inPoint,end:layer.outPoint});}
    return SLTA.json({ok:true,host:'After Effects',name:master.name,compId:master.id,plan:plan,layers:receipt,saved:false});
  }catch(e){return SLTA.error(e);}finally{if(undo)try{app.endUndoGroup();}catch(_){} }
};
SLTA.buildPremiere=function(p){
  try{
    if(!app.project||!app.project.rootItem)throw new Error('Open a Premiere project before building.');
    var plan=SLTemplateModel.plan(p.rows,p.options),bin=app.project.rootItem.createBin('Storylens Templates '+new Date().getTime()),items={},i,s,r,sub,item,seq,time,settings,actual;
    for(i=0;i<plan.segments.length;i++){
      s=plan.segments[i];if(items[s.rowIndex])continue;r=p.rows[s.rowIndex];
      if(!new File(r.path).exists)throw new Error('Source project is missing: '+r.path);
      var sourceFile=new File(r.path);if(Number(r.sourceBytes)!==sourceFile.length||Math.abs(Number(r.sourceModified)-sourceFile.modified.getTime())>1500){var changed=new Error('The source project changed after its composition details were read: '+r.path+'. Read it again in After Effects.');changed.code='template_inspection_required';throw changed;}
      var duplicates=0;for(var z=0;z<r.comps.length;z++)if(r.comps[z].name===r.comp.name)duplicates++;
      if(duplicates>1){var er=new Error('Premiere imports by composition name. '+r.comp.name+' occurs more than once in '+r.name+'. Choose a uniquely named comp or rename it in a source copy.');er.code='template_choice';throw er;}
      sub=bin.createBin(('0'+(s.rowIndex+1)).slice(-2)+' '+r.name);
      app.project.importAEComps(r.path,[r.comp.name],sub);
      item=null;for(var j=0;j<sub.children.numItems;j++)if(sub.children[j].name===r.comp.name)item=sub.children[j];
      if(!item&&sub.children.numItems===1)item=sub.children[0];
      if(!item)throw new Error('Dynamic Link did not return '+r.comp.name+'. Check matching AE/Premiere versions and close Adobe dialogs.');item.setScaleToFrameSize();items[s.rowIndex]=item;
    }
    s=plan.segments[0];item=items[s.rowIndex];item.setInPoint(s.sourceIn,4);item.setOutPoint(s.sourceIn+s.frames/plan.fps,4);
    seq=app.project.createNewSequenceFromClips(p.name||'Storylens — Template Assembly',[item],bin);
    if(!seq)throw new Error('Premiere could not create the template sequence.');
    settings=seq.getSettings();time=new Time();time.seconds=1/plan.fps;settings.videoFrameRate=time;settings.videoFrameWidth=plan.width;settings.videoFrameHeight=plan.height;seq.setSettings(settings);
    actual=254016000000/Number(seq.timebase);
    if(Math.abs(actual-plan.fps)>.001)throw new Error('The new sequence uses '+actual.toFixed(3)+' fps instead of '+plan.fps+'. Match the first composition frame rate and retry. The incomplete sequence is kept separately.');
    for(i=1;i<plan.segments.length;i++){s=plan.segments[i];item=items[s.rowIndex];item.setInPoint(s.sourceIn,4);item.setOutPoint(s.sourceIn+s.frames/plan.fps,4);time=new Time();time.seconds=s.startFrame/plan.fps;seq.insertClip(item,time,0,0);}
    var clips=seq.videoTracks[0].clips,receipt=[];
    if(clips.numItems!==plan.segments.length)throw new Error('Premiere did not insert every planned composition. Inspect the new sequence; do not retry blindly.');
    for(i=0;i<clips.numItems;i++){s=plan.segments[i];if(Math.abs(clips[i].start.seconds-s.startFrame/plan.fps)>.51/plan.fps||Math.abs(clips[i].end.seconds-s.endFrame/plan.fps)>.51/plan.fps)throw new Error('Premiere timing differs at template '+(i+1)+'. The new sequence is kept for inspection.');receipt.push({name:clips[i].name,start:clips[i].start.seconds,end:clips[i].end.seconds});}
    app.project.openSequence(seq.sequenceID);return SLTA.json({ok:true,host:'Premiere Pro',name:seq.name,sequenceId:seq.sequenceID,plan:plan,clips:receipt,saved:false});
  }catch(e){return SLTA.error(e);}
};
SLTA.dispatch=function(p){
  try{
    if(p.action==='info')return SLTA.json({host:SLTA.ae()?'After Effects':'Premiere Pro',version:app.version,ae:SLTA.ae(),catalogFolder:SLTA.catalogDir(false).fsName});
    if(p.action==='saveList'){var save=File.saveDialog('Save Storylens template order','JSON:*.json');return SLTA.json({path:save?save.fsName:null});}
    if(p.action==='loadList'){var load=File.openDialog('Load Storylens template order','JSON:*.json');return SLTA.json({path:load?load.fsName:null});}
    if(p.action==='pick'){var files=File.openDialog('Choose After Effects projects','After Effects projects:*.aep;*.aepx',true),a=[];if(files)for(var i=0;i<files.length;i++)a.push(files[i].fsName);return SLTA.json({paths:a});}
    if(p.action==='folder'){var f=Folder.selectDialog('Choose your template library');return SLTA.json({path:f?f.fsName:null});}
    if(p.action==='inspect'&&SLTA.ae())return SLTA.inspect(p);
    if(p.action==='build')return SLTA.ae()?SLTA.buildAE(p):SLTA.buildPremiere(p);
    if(p.action==='inspect'){var needed=new Error('Read these templates in After Effects first, then close its interface and use the cached composition list in Premiere. The panel does not start After Effects automatically.');needed.code='template_inspection_required';throw needed;}
    throw new Error('Choose an available Template Assembler action.');
  }catch(e){return SLTA.error(e);}
};
SLTA.poll=function(id){if(SLTA.replies[id]){var r=SLTA.replies[id];delete SLTA.replies[id];return r;}return SLTA.json({pending:id});};
