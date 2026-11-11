(function(){
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/template-assembler/host.jsx'));
 var output=new File('D:/Full Drive/remove silence/output/template-assembler-evidence/native-ae-final.json'),result={};
 try{
  var c=SLTA.item(6321);if(!(c instanceof CompItem))throw new Error('The test assembly is not in the current project.');
  c.name='Storylens - 10 minute template check';
  var layers=[],previous=0;
  for(var i=1;i<=c.numLayers;i++){var l=c.layer(i);if(Math.abs(l.inPoint-previous)>1e-5)throw new Error('Gap or overlap at placement '+i);layers.push({source:l.source.name,start:l.inPoint,end:l.outPoint,scale:l.property('ADBE Transform Group').property('ADBE Scale').value});previous=l.outPoint;}
  if(Math.abs(c.duration-600)>1e-6||Math.abs(previous-600)>1e-6)throw new Error('The composition does not finish at 10 minutes.');
  var rows=SLTA.ui.rows();for(var j=0;j<rows.length;j++)SLTA.writeCatalogue(rows[j]);
  result={ok:true,compId:c.id,name:c.name,duration:c.duration,fps:c.frameRate,frames:Math.round(c.duration*c.frameRate),layers:layers,sourceProject:app.project.file?app.project.file.fsName:null,sourceProjectSaved:false,compositionCatalog:SLTA.catalogDir(false).fsName};
  c.openInViewer();
 }catch(e){result={error:true,details:String(e)};}
 output.encoding='UTF-8';output.open('w');output.write(SLTA.json(result));output.close();
})();
