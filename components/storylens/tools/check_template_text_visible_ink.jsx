/* Native differential render: owned text only, always restored, no source edits. */
(function(){var base='D:/Full Drive/remove silence/',out=base+'output/template-text-repair/',report={ok:false,frames:[]},master=null,oldTime=0,oldResolution=null;
function read(p){var f=new File(out+p);f.encoding='UTF-8';f.open('r');var s=f.read();f.close();return JSON.parse(s);}
function save(){var f=new File(out+'visible-ink-progress.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Recovery project required.');var nativeResult=read('scene-heading-native-progress.json');if(nativeResult.phase!=='complete')throw Error('Finish the native update first.');
 master=app.project.itemByID(Number(nativeResult.composition_id));oldTime=master.time;oldResolution=master.resolutionFactor;master.resolutionFactor=[2,2];var checks=read('scene-heading-review-frames.json'),indices=[3,20,24];
 for(var n=0;n<indices.length;n++){var index=indices[n],check=checks[index],top=null;for(var i=1;i<=master.numLayers;i++)if(String(master.layer(i).id)===check.template)top=master.layer(i);if(!top)throw Error('Placed template changed.');
  var c=top.source,parts=check.path.split('/'),layer=null;for(i=0;i<parts.length;i++){layer=c.layer(Number(parts[i]));if(i<parts.length-1)c=layer.source;}if(c.name.indexOf('[SLTT ')<0)throw Error('Only a private title may be checked.');
  var expected=null;for(i=0;i<nativeResult.audit.headings.length;i++){var h=nativeResult.audit.headings[i];if(h.template_layer_id===check.template&&h.text_id===check.path)expected=h;}if(!expected||!expected.runs.length)throw Error('Heading timing changed.');var run=expected.runs[0];
  for(var sample=1;sample<=3;sample++){var time=run.start+(run.end-run.start)*sample/4,prefix='ink-'+index+'-'+sample,on=new File(out+prefix+'-on.png'),off=new File(out+prefix+'-off.png'),enabled=layer.enabled,lock=layer.locked;
   report.current={heading:index,text:check.text,sample:sample};save();master.time=time;
   try{master.saveFrameToPng(time,on);layer.locked=false;layer.enabled=false;master.saveFrameToPng(time,off);}finally{layer.enabled=enabled;layer.locked=lock;}
   report.frames.push({heading:index,text:check.text,time:time,on:on.fsName,off:off.fsName});save();
  }
 }report.ok=true;report.current=null;
}catch(e){report.error=String(e);}finally{if(master&&oldResolution){master.resolutionFactor=oldResolution;master.time=oldTime;}save();}
})();
