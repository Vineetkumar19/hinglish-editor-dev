(function(){var base='D:/Full Drive/remove silence/',report={ok:false};function write(){var f=new File(base+'output/template-import-performance/valid-preview-defer.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('template-import-performance')<0||StorylensTemplateImportJob.running)throw Error('Idle isolated benchmark required.');
 var prior=StorylensTemplateImportJob,partial=[],ids={},i,j;if(prior.imported!==0||prior.index!==1)throw Error('Expected isolated failed-source check.');
 for(i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(!prior.knownItems[item.id]){partial.push(item);ids[item.id]=true;}}if(partial.length!==260)throw Error('Partial count changed.');
 for(i=0;i<partial.length;i++){var users=partial[i].usedIn||[];for(j=0;j<users.length;j++)if(!ids[users[j].id])throw Error('Successful content now uses partial objects.');}
 var pending=partial.slice(0);while(pending.length){var did=false;for(i=pending.length-1;i>=0;i--){if(pending[i] instanceof FolderItem&&pending[i].numItems)continue;pending[i].remove();pending.splice(i,1);did=true;}if(!did)throw Error('Cannot safely clear partial hierarchy.');}
 $.evalFile(new File(base+'editor_plugins/shared/template-import-model.js'));$.evalFile(new File(base+'editor_plugins/shared/aftereffects-template-import.jsx'));
 var result=JSON.parse(storylensPanelTemplateImport({action:'start'}));if(!result.ok)throw Error(result.error);var job=StorylensTemplateImportJob,chosen=null;
 for(i=0;i<job.queue.length;i++){var candidate=job.queue[i],file=new File(candidate.path);if(candidate.folder!=='Historical Slideshow'&&file.length<6000000){chosen=candidate;break;}}
 if(!chosen)for(i=0;i<job.queue.length;i++)if(job.queue[i].folder!=='Historical Slideshow'){chosen=job.queue[i];break;}
 if(!chosen){job.stop=true;throw Error('No eligible separate candidate.');}job.queue=[chosen];var tick=job.tick;
 report.phase='importing';report.path=chosen.path;report.started=new Date().getTime();report.rendering_before=app.disableRendering;report.partial_removed=260;write();job.tick=function(){tick();report.elapsed_ms=new Date().getTime()-report.started;report.phase=job.state;report.imported=job.imported;report.results=job.results;report.ok=!job.running&&job.imported===1;report.rendering_restored=app.disableRendering===report.rendering_before;
 if(!job.running){if(SLImportPerformance.historyExisted)app.settings.saveSetting('Storylens','templateImportHistory',SLImportPerformance.history);else if(app.settings.haveSetting('Storylens','templateImportHistory'))app.settings.deleteSetting('Storylens','templateImportHistory');report.history_restored=true;}write();};
}catch(e){report.error=String(e);report.line=e.line;report.phase='failed';write();}})();
