/* Three actual refreshes in the isolated imported-library project. */
(function(){var base='D:/Full Drive/remove silence/',r={ok:false,runs:[]};function write(){var f=new File(base+'output/template-import-performance/native-alignment.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(r));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('template-import-performance')<0||typeof SLImportPerformance==='undefined'||StorylensTemplateImportJob.running)throw Error('Completed isolated import required.');
 $.evalFile(new File(base+'editor_plugins/template-assembler/model.js'));$.evalFile(new File(base+'editor_plugins/shared/template-aliner-model.js'));$.evalFile(new File(base+'editor_plugins/shared/aftereffects-template-aliner.jsx'));
 var s=SLImportPerformance,c=s.comp,original={id:s.raw.id,source:s.raw.source.id,start:s.raw.startTime,inPoint:s.raw.inPoint,outPoint:s.raw.outPoint,audio:s.raw.audioEnabled,enabled:s.raw.enabled},openings={},sequences={};
 for(var pass=0;pass<3;pass++){
  c.openInViewer();r.phase='aligning';r.pass=pass+1;write();var start=new Date().getTime(),result=JSON.parse(storylensPanelTemplateAlign({}));var row={ms:new Date().getTime()-start,result:result};r.runs.push(row);if(!result.ok)throw Error(result.error||'Alignment stopped.');
  var sequence=[],end=0,seen={},tagged=0;for(var i=0;i<result.placements.length;i++){var p=result.placements[i];if(Math.abs(p.start-end)>.0001||seen[p.folder])throw Error('Gap or repeated template.');seen[p.folder]=true;sequence.push(p.folder);end=p.end;}
  for(i=1;i<=c.numLayers;i++){var layer=c.layer(i);if(String(layer.comment).indexOf('Storylens Template Aliner v1 | folder=')===0){tagged++;if(layer.audioEnabled)throw Error('Template audio enabled.');}}
  if(tagged!==result.placements.length)throw Error('Stale generated layers remain.');
  if(s.raw.id!==original.id||s.raw.source.id!==original.source||s.raw.startTime!==original.start||s.raw.inPoint!==original.inPoint||s.raw.outPoint!==original.outPoint||s.raw.audioEnabled!==original.audio||s.raw.enabled!==original.enabled)throw Error('Original source changed.');
  row.sequence=sequence;row.layers=tagged;row.raw_unchanged=true;row.full_animations=result.full_template_animations;row.covered=end;sequences[sequence.join('|')]=true;openings[sequence[0]]=true;write();
 }
 var unique=0;for(var key in sequences)if(sequences.hasOwnProperty(key))unique++;if(unique!==3)throw Error('Refresh repeated an arrangement.');
 r.ok=true;r.phase='complete';r.unique_arrangements=unique;r.original_unchanged=true;r.comp_id=c.id;
}catch(e){r.error=String(e);r.line=e.line;r.phase='failed';}write();})();
