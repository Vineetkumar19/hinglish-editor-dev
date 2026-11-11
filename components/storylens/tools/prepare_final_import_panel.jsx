/* Restore only the isolated import benchmark for final real-panel validation. */
(function(){var base='D:/Full Drive/remove silence/',r={ok:false};try{
 if(!app.project.file||app.project.file.fsName.indexOf('template-import-performance')<0||app.project.numItems>10)throw Error('Idle small disposable benchmark required.');
 var f=new File(base+'output/template-import-performance/native-library-review.aep');if(!f.exists)throw Error('Saved benchmark unavailable.');
 app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);app.open(f);
 $.evalFile(new File(base+'editor_plugins/after-effects-cep/jsx/host.jsx'));
 StorylensTemplateImportJob=null;StorylensTemplateAlignLastTarget=null;
 var c=null;for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(item instanceof CompItem&&item.name==='Storylens import and alignment check'){c=item;break;}}
 if(!c){for(i=1;i<=app.project.numItems;i++){item=app.project.item(i);if(item instanceof CompItem&&item.duration>750&&item.duration<754){c=item;break;}}}
 if(!c)throw Error('Benchmark target not found.');c.openInViewer();r.ok=true;r.path=app.project.file.fsName;r.items=app.project.numItems;r.comp_id=c.id;r.comp_name=c.name;
}catch(e){r.error=String(e);r.line=e.line;}var out=new File(base+'output/template-import-performance/panel-ready.json');out.open('w');out.write(JSON.stringify(r));out.close();})();
