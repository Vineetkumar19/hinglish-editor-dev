/* Isolated native first-paste measurement; keeps the owner's saved recovery. */
(function(){var base='D:/Full Drive/remove silence/',out=base+'output/copy-paste-evidence/scroll-speed/',report={ok:false},made=[],owner=null,selection=[],original=null,before=null,undoDone=false,settings=null;
function write(){var f=new File(out+'branch-native-result.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Recovery project required.');
 $.evalFile(new File(base+'editor_plugins/copy-paste/model.js'));$.evalFile(new File(base+'editor_plugins/copy-paste/framing-model.js'));$.evalFile(new File(base+'editor_plugins/copy-paste/framing.jsx'));$.evalFile(new File(base+'editor_plugins/copy-paste/host.jsx'));
 owner=app.project.itemByID(24516);original=app.project.itemByID(59502);if(!owner||!original||original.name.indexOf('Color_Edit')!==0)throw Error('Prepared native 3D template is unavailable.');
 settings={clipboard:SLCopyPaste.clipboard,history:(SLCopyPaste.history||[]).slice(0),targetRef:SLCopyPaste.targetRef};selection=app.project.selection||[];before=app.project.numItems;
 var baseline=SLCopyPaste.json(SLCopyPaste.graph(original,true)),folder=app.project.items.addFolder('ZZ Storylens branch performance check');made.push(folder);
 var image=app.project.importFile(new ImportOptions(new File(out+'small-check.png')));image.parentFolder=folder;made.push(image);
 var comp=folder.items.addComp('ZZ branch paste check',original.width,original.height,original.pixelAspect,6,original.frameRate);made.push(comp);var layer=comp.layers.add(original);layer.selected=true;comp.openInViewer();
 var selected=app.project.selection||[];for(var i=0;i<selected.length;i++)selected[i].selected=false;image.selected=true;
 report.phase='pasting';write();var started=new Date().getTime();var copied=JSON.parse(storylensPanelCopyPaste({action:'copy'}));if(!copied.copied)throw Error(copied.error);var pasted=JSON.parse(storylensPanelCopyPaste({action:'paste'}));report.paste_ms=new Date().getTime()-started;report.receipt=pasted;if(!pasted.ok)throw Error(pasted.error);
 comp.saveFrameToPng(2,new File(out+'branch-real-3d-paste.png'));
 report.original_unchanged=SLCopyPaste.json(SLCopyPaste.graph(original,true))===baseline;if(!report.original_unchanged)throw Error('Original changed; keep fixture for review.');
 var undone=JSON.parse(storylensPanelCopyPaste({action:'undo'}));report.undo=undone;if(!undone.undone)throw Error('Own paste was not undone; keep fixture.');undoDone=true;
 if(layer.source!==original||layer.comment)throw Error('Fixture source was not restored.');
 if(app.project.numItems!==before+made.length)throw Error('Unexpected new objects; keep fixture for review.');owner.openInViewer();folder.remove();made=[];
 if(app.project.numItems!==before)throw Error('Fixture count did not return to baseline.');report.ok=true;report.phase='complete';
}catch(e){report.error=String(e);report.line=e.line;}finally{
 if(settings){SLCopyPaste.clipboard=settings.clipboard;SLCopyPaste.history=settings.history;SLCopyPaste.targetRef=settings.targetRef;}
 if(owner&&(!made.length||undoDone)){owner.openInViewer();var current=app.project.selection||[];for(var i=0;i<current.length;i++)current[i].selected=false;for(i=0;i<selection.length;i++)try{selection[i].selected=true;}catch(_){}}
 report.items_after=app.project.numItems;report.items_before=before;write();}
})();
