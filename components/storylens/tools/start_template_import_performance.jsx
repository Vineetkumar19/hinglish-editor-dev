(function(){var base='D:/Full Drive/remove silence/',report={ok:false,phase:'preparing'};
function write(){var f=new File(base+'output/template-import-performance/native-import.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('template-import-performance')<0||app.project.numItems!==3||typeof SLImportPerformance==='undefined')throw Error('Prepared empty performance project required.');
 $.evalFile(new File(base+'editor_plugins/shared/template-import-model.js'));$.evalFile(new File(base+'editor_plugins/shared/aftereffects-template-import.jsx'));
 report.started=new Date().getTime();var result=JSON.parse(storylensPanelTemplateImport({action:'start'}));report.initial=result;if(!result.ok||result.total!==20)throw Error(result.error||'Invalid batch');
 var job=StorylensTemplateImportJob,originalTick=job.tick;report.phase='importing';report.comp_id=SLImportPerformance.comp.id;write();
 job.tick=function(){var self=StorylensTemplateImportJob,before=self.index,started=new Date().getTime();report.current=self.queue[before]?self.queue[before].folder:null;write();originalTick();self=StorylensTemplateImportJob;
  if(self.results.length&&self.index>before)self.results[self.results.length-1].benchmark_ms=new Date().getTime()-started;
  report.processed=self.index;report.imported=self.imported;report.elapsed_ms=new Date().getTime()-report.started;report.items=app.project.numItems;report.results=self.results;report.phase=self.running?'importing':self.state;report.ok=!self.running&&self.state==='complete'&&self.imported===20;
  if(!self.running){if(SLImportPerformance.historyExisted)app.settings.saveSetting('Storylens','templateImportHistory',SLImportPerformance.history);else if(app.settings.haveSetting('Storylens','templateImportHistory'))app.settings.deleteSetting('Storylens','templateImportHistory');report.history_restored=true;SLImportPerformance.comp.openInViewer();}write();
 };
}catch(e){report.error=String(e);report.line=e.line;report.phase='failed';write();}})();
