"""Prepare a guarded native AE script from basic timeline XML, without rendering.

Run the generated .jsx with AE File > Scripts > Run Script File. Existing owner
projects are never closed or overwritten. Only this bridge's managed test/native
project can be saved before creating the new editable composition.
"""
import argparse
import json
from pathlib import Path
if __package__:
    from .to_capcut import parse_xml
else:
    from to_capcut import parse_xml


def prepare(xml,folder,title,diagnostic=False,managed_prefix=None):
    folder=folder.resolve();folder.mkdir(parents=True,exist_ok=True)
    spec,lanes,issues=parse_xml(xml)
    if issues and not diagnostic:
        (folder/'appearance-gaps.json').write_text(json.dumps(issues,indent=2),encoding='utf8')
        raise ValueError('This edit needs appearance conversion before AE; original sources preserved.')
    plan={'title':title,'timeline':spec,'lanes':lanes,'appearance_gaps':issues,
          'output_project':str(folder/(title+'.aep')),'receipt':str(folder/'ae-native-receipt.json'),
          'managed_prefix':str(managed_prefix or Path(__file__).resolve().parents[2]/'output/editor-link-20261104')}
    js='var plan='+json.dumps(plan,ensure_ascii=True)+';\n'+r'''
(function(){
 var result={status:'needs_review',source:'timeline XML',rendered:false};
 try{
  var output=File(plan.output_project);
  if(output.exists)throw Error('The destination AEP already exists. Inspect the saved project before repeating this script.');
  if(app.project.file){
   var current=app.project.file.fsName.toLowerCase(),prefix=Folder(plan.managed_prefix).fsName.toLowerCase();
   if(current.indexOf(prefix+'\\')!==0)throw Error('An unrelated AE project is open. It was preserved.');
   app.project.save();
  }else if(app.project.numItems)throw Error('An unsaved AE project is open. It was preserved.');
  app.newProject();app.beginUndoGroup('Storylens editable editor handoff');
  var s=plan.timeline,comp=app.project.items.addComp(plan.title,s.width,s.height,1,s.duration/1000000,s.fps),assets={};
  function asset(path){
   if(assets[path])return assets[path];
   var f=File(path);if(!f.exists)throw Error('Missing media: '+path);
   var o=new ImportOptions(f);assets[path]=app.project.importFile(o);return assets[path];
  }
  function place(row,audio){
   var footage=asset(row.path),l=comp.layers.add(footage);
   l.name=row.name;l.startTime=(row.start-row.source_in)/1000000;
   l.inPoint=row.start/1000000;l.outPoint=(row.start+row.duration)/1000000;
   if(footage.hasAudio){
    l.audioEnabled=audio;
    if(audio){var g=row.gain===undefined?1:row.gain;
     if(g<=0)l.audioEnabled=false;
     else {var db=20*Math.log(g)/Math.LN10;l.property('ADBE Audio Group').property('ADBE Audio Levels').setValue([db,db]);}
    }
   }
   return {name:l.name,start:l.inPoint,end:l.outPoint,source:footage.file.fsName};
  }
  result.layers=[];
  for(var a=0;a<s.audio_layers.length;a++)result.layers.push(place(s.audio_layers[a],true));
  // Lower source video tracks are added first, so the higher tracks appear on top.
  var order=[];for(var v=0;v<s.clips.length;v++)order.push(v);
  order.sort(function(a,b){return plan.lanes[a]-plan.lanes[b];});
  for(var v=0;v<order.length;v++)result.layers.push(place(s.clips[order[v]],false));
  app.endUndoGroup();comp.openInViewer();comp.time=Math.min(1,comp.duration/2);
  app.project.save(output);
  result.status='native_editable_composition_saved';result.project=output.fsName;
  result.comp=comp.name;result.layer_count=comp.numLayers;result.fps=comp.frameRate;
  result.duration=comp.duration;result.appearance_gaps=plan.appearance_gaps;
 }catch(e){result.error=String(e);}
 var receipt=File(plan.receipt);receipt.encoding='UTF-8';receipt.open('w');receipt.write(JSON.stringify(result));receipt.close();
})();
'''
    target=folder/'import-in-after-effects.jsx';target.write_text(js,encoding='utf8')
    (folder/'ae-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
    return {'status':'native_script_prepared','script':str(target),'project':plan['output_project'],
            'video_clips':len(spec['clips']),'audio_clips':len(spec['audio_layers']),
            'appearance_gaps':issues,'live_application_verified':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--xml',type=Path,required=True);p.add_argument('--folder',type=Path,required=True);p.add_argument('--title',required=True);p.add_argument('--diagnostic',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(a.xml,a.folder,a.title,a.diagnostic)))
