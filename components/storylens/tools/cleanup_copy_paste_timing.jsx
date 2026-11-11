/* Remove only uniquely identified owned fixtures after confirming the paste Undo. */
(function(){var base='D:/Full Drive/remove silence/',r={ok:false};try{
 var s=SLPastePanelTiming,original=SLPasteTiming;if(!s||!original||app.project.file.fsName.indexOf('Storylens recovery RAM check')<0)throw Error('Recovery timing context required.');
 if(s.layer.source!==s.source||String(s.layer.comment)!==s.comment||SLCopyPaste.json(SLCopyPaste.graph(s.source,true))!==original.graph)throw Error('Undo the timing paste before cleanup.');
 if(SLCopyPaste.json(SLCopyPaste.graph(app.project.itemByID(59502),true))!==original.source)throw Error('Source audit changed; preserve the session.');
 var ids={},comps=[],branchFolder=app.project.itemByID(149553),items=[],i,j;
 if(!branchFolder||branchFolder.name!=='ZZ Storylens branch performance check'||s.folder.name!=='ZZ Storylens 200 photos check')throw Error('Owned fixture names changed.');
 ids[branchFolder.id]=true;ids[149554]=true;ids[149555]=true;
 for(i=0;i<s.created.length;i++)ids[s.created[i].id]=true;
 for(i=1;i<=app.project.numItems;i++){var c=app.project.item(i);if(c instanceof CompItem&&(/\[Copy Paste 149567\]$/.test(c.name)||String(c.comment)==='Storylens Copy Paste media v1|source=149554'))ids[c.id]=true;}
 for(i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(!ids[item.id])continue;items.push(item);if(item instanceof CompItem)comps.push(item);if(item.usedIn){var users=item.usedIn;for(j=0;j<users.length;j++)if(!ids[users[j].id])throw Error('An owner composition now uses a fixture; preserve it.');}}
 if(items.length!==259||app.project.numItems-items.length!==8522)throw Error('Unexpected fixture count; preserve it.');
 s.comp.openInViewer();for(i=comps.length-1;i>=0;i--)comps[i].remove();s.folder.remove();branchFolder.remove();
 r={ok:app.project.numItems===8522,items:app.project.numItems,removed:items.length,source_unchanged:true,owner_paste_restored:true};SLPastePanelTiming=null;SLPasteTiming=null;
}catch(e){r.error=String(e);r.line=e.line;}var f=new File(base+'output/copy-paste-evidence/scroll-speed/cleanup-native.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(r));f.close();})();
