"""Editable sound handoff, retaining the source picture and independent stems."""
import json
from pathlib import Path


def capcut_spec(plan_path):
    from hinglish_app.capcut_adapter import timeline_spec
    from .xml_export import _seconds,lanes
    plan=json.loads(Path(plan_path).read_text('utf-8'))
    spec=timeline_spec(plan['timeline_xml'])
    stems=plan.get('stems') or {}
    stems=stems.get('editor',stems)
    audio=[]
    def add(path,start,duration,label,lane):
        if not Path(path).is_file():
            raise ValueError('A saved sound layer is missing. Reopen Sound Design and Save & remix before exporting.')
        audio.append(dict(path=str(Path(path).resolve()),start=round(start*1e6),source_in=0,
                          duration=round(duration*1e6),name=label,lane=lane))
    if stems.get('voice'):add(stems['voice'],0.,_seconds(stems['voice']),stems.get('voice_label','Dialogue'),'voice')
    if stems.get('music'):add(stems['music'],0.,_seconds(stems['music']),'Background music','music')
    for lane,effect in lanes(stems.get('effects',[]))[0]:
        add(effect['path'],effect['start'],effect['length'],
            'SFX '+effect['category']+' · '+effect.get('role',''),f'effects-{lane}')
    spec.update(sound=True,mute_source_audio=bool(stems.get('voice')),audio_layers=audio)
    return spec


def aftereffects_script(plan_path, destination):
    """AE imports the same independent rendered stems used by Premiere/CapCut.

    Levels/ducking are baked into individual stems; AE audioLevels stays at 0 dB
    so nothing is attenuated twice. Every layer remains moveable and trimmable.
    """
    plan_path=Path(plan_path)
    plan=json.loads(plan_path.read_text('utf-8'))
    spec=capcut_spec(plan_path)
    spec['name']='Storylens Sound Design'
    from .keyword_folders import package
    options=package(plan_path)
    spec['keyword_folders']=options['folders'] if options else []
    spec['options']=list(dict.fromkeys(c['asset']['path'] for e in plan.get('human_review',{}).get('events',[])
                                      for c in e['candidates']))
    script=r'''(function(){
app.beginUndoGroup("Storylens Sound Design");
try {
  if(!app.project) app.newProject();
  var spec=__SPEC__, folder=app.project.items.addFolder(spec.name), cache={};
  var optionsFolder=app.project.items.addFolder("Sound Design"); optionsFolder.parentFolder=folder;
  function footage(path,parent){
    if(cache[path]) return cache[path];
    var file=new File(path); if(!file.exists) throw new Error("Missing sound/video: "+path);
    var item=app.project.importFile(new ImportOptions(file)); item.parentFolder=parent||folder; cache[path]=item; return item;
  }
  var comp=app.project.items.addComp(spec.name,spec.width,spec.height,1,spec.duration/1000000,spec.fps);
  comp.parentFolder=folder;
  function put(row,audio){
    var layer=comp.layers.add(footage(row.path));
    layer.name=row.name||(audio?"Sound effect":"Source video");
    layer.startTime=(row.start-(row.source_in||0))/1000000;
    layer.inPoint=row.start/1000000; layer.outPoint=(row.start+row.duration)/1000000;
    if(audio){layer.audioEnabled=true;layer.property("ADBE Audio Group").property("ADBE Audio Levels").setValue([0,0]);}
    else {layer.audioEnabled=!spec.mute_source_audio;}
  }
  for(var i=0;i<spec.clips.length;i++) put(spec.clips[i],false);
  for(var j=0;j<spec.audio_layers.length;j++) put(spec.audio_layers[j],true);
  for(var k=0;k<spec.keyword_folders.length;k++) {
    var group=spec.keyword_folders[k], bin=app.project.items.addFolder(group.name); bin.parentFolder=optionsFolder;
    for(var f=0;f<group.files.length;f++) footage(group.files[f].path,bin);
  }
  // Legacy Sound options - not on timeline remains available for older plans.
  if(!spec.keyword_folders.length) for(var k=0;k<spec.options.length;k++) footage(spec.options[k],optionsFolder);
  comp.openInViewer();
} catch(error){alert("Storylens sound import stopped: "+error.toString());}
finally {app.endUndoGroup();}
})();'''
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(script.replace('__SPEC__',json.dumps(spec,ensure_ascii=True)),encoding='utf-8')
    return str(destination.resolve())
