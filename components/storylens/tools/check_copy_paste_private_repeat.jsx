/* Reuse the already-owned scratch template; never edit the owner's timeline. */
(function(){var base='D:/Full Drive/remove silence/',out={ok:false},settings=null,selection=app.project.selection||[],owner=null;
function write(){var f=new File(base+'output/copy-paste-evidence/scroll-speed/private-repeat.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(out));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Recovery required.');
 $.evalFile(new File(base+'editor_plugins/copy-paste/model.js'));$.evalFile(new File(base+'editor_plugins/copy-paste/framing-model.js'));$.evalFile(new File(base+'editor_plugins/copy-paste/framing.jsx'));$.evalFile(new File(base+'editor_plugins/copy-paste/host.jsx'));SLCopyPaste.checkProject();
 var c=app.project.itemByID(149555);owner=app.project.itemByID(24516);if(!c||c.name!=='ZZ branch paste check')throw Error('Owned fixture unavailable.');
 var l=c.layer(1);if(l.id!==149567||String(l.comment).indexOf('[Storylens Copy Paste v1|')<0)throw Error('Fixture changed.');
 var image=null;for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(item instanceof FootageItem&&item.file&&item.file.fsName.replace(/\\/g,'/')===base+'output/copy-paste-evidence/scroll-speed/small-check.png'){image=item;break;}}
 if(!image)throw Error('Fixture picture unavailable.');
 settings={clipboard:SLCopyPaste.clipboard,history:(SLCopyPaste.history||[]).slice(0),targetRef:SLCopyPaste.targetRef};
 SLCopyPaste.clipboard={id:image.id,name:image.name,file:image.file.fsName};c.openInViewer();l.selected=true;
 out.before=app.project.numItems;out.phase='pasting';out.start=new Date().getTime();write();
 var result=JSON.parse(storylensPanelCopyPaste({action:'paste'}));out.paste_ms=new Date().getTime()-out.start;out.receipt=result;out.ok=result.ok===true;out.phase=out.ok?'complete':'failed';out.after=app.project.numItems;
}catch(e){out.error=String(e);out.line=e.line;out.phase='failed';}finally{
 if(settings){SLCopyPaste.clipboard=settings.clipboard;SLCopyPaste.history=settings.history;SLCopyPaste.targetRef=settings.targetRef;}
 if(owner)owner.openInViewer();write();}
})();
