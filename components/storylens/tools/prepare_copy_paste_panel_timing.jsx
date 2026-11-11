(function(){var base='D:/Full Drive/remove silence/',report={ok:false};try{
 if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery RAM check')<0)throw Error('Recovery required.');
 var master=app.project.itemByID(24516),target=null;for(var i=1;i<=master.numLayers;i++)if(master.layer(i).id===65708)target=master.layer(i);
 if(!target||target.source.id!==147530||SLCopyPasteModel.state(target.comment))throw Error('Expected unchanged private template.');
 if(typeof SLPastePanelTiming!=='undefined'&&SLPastePanelTiming)throw Error('UI fixture already exists.');
 var folder=app.project.items.addFolder('ZZ Storylens 200 photos check');folder.comment='Storylens owned paste timing fixture';
 SLPastePanelTiming={folder:folder,created:[folder],before:app.project.numItems-1,comp:master,layer:target,source:target.source,comment:String(target.comment)};
 var image=null;for(i=1;i<=200;i++){image=app.project.importFile(new ImportOptions(new File(base+'output/copy-paste-evidence/scroll-speed/small-check.png')));image.parentFolder=folder;image.name='Image '+('000'+i).slice(-3);SLPastePanelTiming.created.push(image);}
 master.openInViewer();for(i=1;i<=master.numLayers;i++)master.layer(i).selected=false;target.selected=true;
 var selected=app.project.selection||[];for(i=0;i<selected.length;i++)selected[i].selected=false;image.selected=true;
 report={ok:true,folder:folder.id,image:image.id,count:200,items:app.project.numItems};
}catch(e){report.error=String(e);report.line=e.line;}var f=new File(base+'output/copy-paste-evidence/scroll-speed/panel-ready.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();})();
