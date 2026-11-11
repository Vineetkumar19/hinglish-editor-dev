/* Preserve evidence; remove only partial objects in this disposable benchmark. */
(function(){var r={ok:false},base='D:/Full Drive/remove silence/';try{
 if(!app.project.file||app.project.file.fsName.indexOf('template-import-performance')<0)throw Error('Isolated benchmark required.');
 var job=StorylensTemplateImportJob;if(!job||job.running||job.index!==19||job.imported!==18||job.queue.length!==20)throw Error('Expected stopped import required.');
 var partial=[],ids={},i,j;for(i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(!job.knownItems[item.id]){partial.push(item);ids[item.id]=true;}}
 if(partial.length!==260)throw Error('Unexpected partial-item count.');
 for(i=0;i<partial.length;i++){var users=partial[i].usedIn||[];for(j=0;j<users.length;j++)if(!ids[users[j].id])throw Error('Successful content uses partial objects; preserve them.');}
 var pending=partial.slice(0);while(pending.length){var did=false;for(i=pending.length-1;i>=0;i--){var item=pending[i];if(item instanceof FolderItem&&item.numItems)continue;item.remove();pending.splice(i,1);did=true;}if(!did)throw Error('Partial hierarchy could not be safely cleared.');}
 var finalOnly=job.queue[19];job.queue=job.queue.slice(0,19).concat([finalOnly]);job.state='running';job.running=true;job.stop=false;job.revision=app.project.revision;
 app.scheduleTask('StorylensTemplateImportJob.tick()',200,false);r={ok:true,partial_removed:partial.length,resumed_only_last_original_candidate:true};
}catch(e){r.error=String(e);r.line=e.line;}var f=new File(base+'output/template-import-performance/partial-recovery.json');f.open('w');f.write(JSON.stringify(r));f.close();})();
