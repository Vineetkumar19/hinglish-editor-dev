/* Single reversible paste into the authorized recovery's private 3D instance. */
(function(){var base='D:/Full Drive/remove silence/',report={ok:false};
function write(){var f=new File(base+'output/copy-paste-evidence/scroll-speed/first-private.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery RAM check')<0)throw Error('RAM recovery required.');
 $.evalFile(new File(base+'editor_plugins/copy-paste/model.js'));$.evalFile(new File(base+'editor_plugins/copy-paste/framing-model.js'));$.evalFile(new File(base+'editor_plugins/copy-paste/framing.jsx'));$.evalFile(new File(base+'editor_plugins/copy-paste/host.jsx'));SLCopyPaste.checkProject();
 var comp=app.project.itemByID(24516),layer=null;for(var i=1;i<=comp.numLayers;i++)if(comp.layer(i).id===65708)layer=comp.layer(i);
 if(!layer||layer.source.id!==147530||SLCopyPasteModel.state(layer.comment))throw Error('The prepared first-paste instance changed.');
 var image=app.project.itemByID(149554);if(!(image instanceof FootageItem)||!image.file.exists)throw Error('Test picture unavailable.');
 SLPasteTiming={comp:comp,layer:layer,root:layer.source,comment:String(layer.comment),rootComment:String(layer.source.comment),items:app.project.numItems,graph:SLCopyPaste.json(SLCopyPaste.graph(layer.source,true)),source:SLCopyPaste.json(SLCopyPaste.graph(app.project.itemByID(59502),true)),clipboard:SLCopyPaste.clipboard,history:(SLCopyPaste.history||[]).slice(0),targetRef:SLCopyPaste.targetRef};
 comp.openInViewer();for(i=1;i<=comp.numLayers;i++)comp.layer(i).selected=false;layer.selected=true;SLCopyPaste.clipboard={id:image.id,name:image.name,file:image.file.fsName};
 report.phase='pasting';report.before=app.project.numItems;write();var start=new Date().getTime();var result=JSON.parse(storylensPanelCopyPaste({action:'paste'}));report.paste_ms=new Date().getTime()-start;report.ok=result.ok===true;report.receipt=result;report.after=app.project.numItems;report.phase=report.ok?'complete':'failed';
}catch(e){report.error=String(e);report.line=e.line;report.phase='failed';}write();})();
