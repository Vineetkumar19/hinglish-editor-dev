/* Isolated real library import, at most twenty; no owner project or source edits. */
(function(){var base='D:/Full Drive/remove silence/',folder=new Folder(base+'output/template-import-performance'),report={ok:false,phase:'preparing'};folder.create();
function write(){var file=new File(folder.fsName+'/native-import.json');file.encoding='UTF-8';file.open('w');file.write(JSON.stringify(report));file.close();}
try{
 if(app.project.file||app.project.numItems)throw Error('Start in a fresh empty AE project. Owner project must be saved and closed.');
 $.evalFile(new File(Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/host.jsx'));
 $.evalFile(new File(base+'editor_plugins/shared/template-import-model.js'));$.evalFile(new File(base+'editor_plugins/shared/aftereffects-template-import.jsx'));
 var media=app.project.importFile(new ImportOptions(new File('D:/Editing/documentry edit/low size final/mi.mp4')));
 var comp=app.project.items.addComp('Storylens import and alignment performance check',1920,1080,1,752.366666666667,30);var raw=comp.layers.add(media);comp.resolutionFactor=[4,4];comp.openInViewer();
 var file=new File(folder.fsName+'/native-library-review.aep');if(file.exists)throw Error('Benchmark project already exists; preserve it.');app.project.save(file);
 SLImportPerformance={comp:comp,raw:raw,source:media,before:app.project.numItems,historyExisted:app.settings.haveSetting('Storylens','templateImportHistory'),history:''};
 if(SLImportPerformance.historyExisted)SLImportPerformance.history=app.settings.getSetting('Storylens','templateImportHistory');
 report.started=new Date().getTime();write();var result=JSON.parse(storylensPanelTemplateImport({action:'start'}));if(!result.ok||result.total>20)throw Error(result.error||'Invalid import batch');
 var job=StorylensTemplateImportJob,originalTick=job.tick;report.initial=result;report.phase='importing';report.comp_id=comp.id;write();
 job.tick=function(){var before=this.index,started=new Date().getTime();originalTick();var self=StorylensTemplateImportJob;
  if(self.results.length&&self.index>before)self.results[self.results.length-1].benchmark_ms=new Date().getTime()-started;
  report.processed=self.index;report.imported=self.imported;report.elapsed_ms=new Date().getTime()-report.started;report.items=app.project.numItems;report.results=self.results;report.phase=self.running?'importing':self.state;report.ok=!self.running&&self.state==='complete'&&self.imported===20;
  if(!self.running){
   if(SLImportPerformance.historyExisted)app.settings.saveSetting('Storylens','templateImportHistory',SLImportPerformance.history);else if(app.settings.haveSetting('Storylens','templateImportHistory'))app.settings.deleteSetting('Storylens','templateImportHistory');
   report.history_restored=true;comp.openInViewer();
  }write();
 };
}catch(e){report.error=String(e);report.line=e.line;report.phase='failed';write();}
})();
