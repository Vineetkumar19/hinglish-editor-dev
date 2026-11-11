/* Same twenty previously readable sources, fresh isolated project, full timing. */
(function(){var base='D:/Full Drive/remove silence/',root='D:/Editing/AE documentry style editing templates/LatestTemplete',report={ok:false,phase:'preparing'};
function read(name){var f=new File(base+'output/template-import-performance/'+name);f.open('r');var data=JSON.parse(f.read());f.close();return data;}
function write(){var f=new File(base+'output/template-import-performance/budget-native-import.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('template-import-performance')<0||StorylensTemplateImportJob.running)throw Error('Idle isolated performance project required.');
 var first=read('native-import.json'),extra=read('valid-preview-defer.json'),queue=[],i;for(i=0;i<first.results.length;i++)if(first.results[i].status==='imported'&&first.results[i].path)queue.push({path:first.results[i].path,folder:first.results[i].name,modified:0});
 if(!extra.ok)throw Error('Validated replacement required.');queue.push({path:extra.path,folder:extra.results[extra.results.length-1].name,modified:0});
 $.evalFile(new File(base+'editor_plugins/shared/template-import-model.js'));
 if(queue.length!==20||StorylensLibraryModel.plan(queue,root).length!==20)throw Error('Twenty unique approved-library sources required.');
 for(i=0;i<queue.length;i++)if(!(new File(queue[i].path)).exists)throw Error('A source moved.');
 report.previous_project=app.project.file.fsName;report.phase='saving-previous-benchmark';write();app.project.save();report.previous_saved=true;write();app.newProject();
 var media=app.project.importFile(new ImportOptions(new File('D:/Editing/documentry edit/low size final/mi.mp4'))),comp=app.project.items.addComp('Storylens budget import and alignment check',1920,1080,1,752.366666666667,30),raw=comp.layers.add(media);comp.resolutionFactor=[4,4];comp.openInViewer();
 var projectFile=new File(base+'output/template-import-performance/budget-library-review.aep');if(projectFile.exists)throw Error('Budget benchmark already exists; preserve it.');app.project.save(projectFile);
 SLImportPerformance={comp:comp,raw:raw,source:media,before:app.project.numItems,historyExisted:app.settings.haveSetting('Storylens','templateImportHistory'),history:''};if(SLImportPerformance.historyExisted)SLImportPerformance.history=app.settings.getSetting('Storylens','templateImportHistory');
 $.evalFile(new File(base+'editor_plugins/shared/aftereffects-template-import.jsx'));
 report.started=new Date().getTime();var result=JSON.parse(storylensPanelTemplateImport({action:'start',low_memory:true}));if(!result.ok)throw Error(result.error);var job=StorylensTemplateImportJob;job.queue=queue;var tick=job.tick;report.phase='importing';report.comp_id=comp.id;report.baseline_successful_loading_ms=318917;write();
 job.tick=function(){report.current=job.queue[job.index]?job.queue[job.index].folder:null;write();tick();report.elapsed_ms=new Date().getTime()-report.started;report.processed=job.index;report.imported=job.imported;report.items=app.project.numItems;report.cache_purges=job.cachePurges;report.results=job.results;report.phase=job.running?'importing':job.state;report.ok=!job.running&&job.state==='complete'&&job.imported===20;
 if(!job.running){if(SLImportPerformance.historyExisted)app.settings.saveSetting('Storylens','templateImportHistory',SLImportPerformance.history);else if(app.settings.haveSetting('Storylens','templateImportHistory'))app.settings.deleteSetting('Storylens','templateImportHistory');report.history_restored=true;comp.openInViewer();}write();};
}catch(e){report.error=String(e);report.line=e.line;report.phase='failed';write();}})();
