/* One native frame at a time in the owner-authorized recovery project. */
(function(){
 var root='D:/Full Drive/remove silence',out=root+'/output/template-text-repair/',report={ok:false,frames:[]},comp=null,oldResolution=null,oldTime=0;
 function read(path){var f=new File(path);f.encoding='UTF-8';if(!f.open('r'))throw Error('Review input missing');var s=f.read();f.close();return JSON.parse(s);}
 function save(){var f=new File(out+'scene-heading-frame-progress.json');f.encoding='UTF-8';if(f.open('w')){f.write(JSON.stringify(report));f.close();}}
 try{
  if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Use the recovery project.');
  var nativeResult=read(out+'scene-heading-native-progress.json');if(nativeResult.phase!=='complete'&&nativeResult.phase!=='needs_review')throw Error('Finish the native heading audit first.');
  var checks=read(out+'scene-heading-review-frames.json');comp=app.project.itemByID(Number(nativeResult.composition_id));oldResolution=comp.resolutionFactor;oldTime=comp.time;comp.resolutionFactor=[2,2];
  for(var i=0;i<checks.length;i++){
   var check=checks[i];report.current=check;save();comp.time=check.time;comp.openInViewer();comp.saveFrameToPng(check.time,new File(out+check.file));report.frames.push(check);save();
  }
  report.ok=true;report.current=null;
 }catch(e){report.error=String(e);}finally{if(comp&&oldResolution){comp.resolutionFactor=oldResolution;comp.time=oldTime;}save();}
})();
