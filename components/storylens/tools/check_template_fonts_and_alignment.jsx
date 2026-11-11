(function(){
 $.evalFile(new File(Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/host.jsx'));
 function write(name,data){var f=new File('D:/Full Drive/remove silence/output/template-fonts/'+name);f.encoding='UTF-8';f.open('w');f.write(hJSON(data));f.close();}
 var used=app.project.usedFonts,fonts=[];
 for(var i=0;i<used.length;i++){var font=used[i].font;fonts.push({name:font.postScriptName,family:font.familyName,missing:font.isSubstitute,count:used[i].usedAt.length});}
 write('native-after-install.json',{version:app.version,project:app.project.file.fsName,fonts:fonts});
 var target=app.project.activeItem;
 if(!(target instanceof CompItem)||target.name!=='rcb final - Template Aliner check')throw Error('Open the labelled review copy first. The original composition was kept.');
 // Scope a realistic one-template check to a genuine imported template; no owner source edits.
 var selected=app.project.selection;for(i=0;i<selected.length;i++)selected[i].selected=false;
 var folder=null;for(i=1;i<=app.project.rootFolder.numItems;i++){var item=app.project.rootFolder.item(i);if(item instanceof FolderItem&&item.name==='Civil War History Slideshow.aep'){folder=item;break;}}
 if(!folder)throw Error('The expected imported template folder is unavailable.');folder.selected=true;
 var result=JSON.parse(storylensPanelTemplateAlign({}));write('native-aliner-result.json',result);
})();
