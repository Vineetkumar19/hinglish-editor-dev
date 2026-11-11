(function(){var base='D:/Full Drive/remove silence/',report={ok:false};function write(){var f=new File(base+'output/template-import-performance/low-memory-source-check.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('template-import-performance')<0||StorylensTemplateImportJob.running)throw Error('Idle isolated benchmark required.');
 $.evalFile(new File(base+'editor_plugins/shared/template-import-model.js'));$.evalFile(new File(base+'editor_plugins/shared/aftereffects-template-import.jsx'));
 var start=new Date().getTime(),result=JSON.parse(storylensPanelTemplateImport({action:'start'}));if(!result.ok)throw Error(result.error);var job=StorylensTemplateImportJob;
 job.queue=[{path:'D:/Editing/AE documentry style editing templates/LatestTemplete/Historical Slideshow/Historical Slideshow.aep',folder:'Historical Slideshow',modified:0}];
 var tick=job.tick;report.phase='importing';report.started=start;report.rendering_before=app.disableRendering;write();job.tick=function(){tick();report.elapsed_ms=new Date().getTime()-start;report.phase=job.state;report.imported=job.imported;report.results=job.results;report.ok=!job.running&&job.imported===1;report.rendering_restored=app.disableRendering===report.rendering_before;
 if(!job.running){if(SLImportPerformance.historyExisted)app.settings.saveSetting('Storylens','templateImportHistory',SLImportPerformance.history);else if(app.settings.haveSetting('Storylens','templateImportHistory'))app.settings.deleteSetting('Storylens','templateImportHistory');report.history_restored=true;}write();};
}catch(e){report.error=String(e);report.line=e.line;report.phase='failed';write();}})();
