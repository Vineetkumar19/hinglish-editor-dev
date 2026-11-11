/* Import references to existing template assets; never open/replace/save owner project. */
$.evalFile(new File('D:/Full Drive/remove silence/tools/import_template_library_model.js'));
$.evalFile(new File('D:/Full Drive/remove silence/output/template-library-import/input.js'));
(function(){
 if(typeof SLTemplateLibraryImport!=='undefined'&&SLTemplateLibraryImport.running)throw Error('The template import is already running.');
 var project=app.project;if(!project||!project.file||project.file.fsName!==SL_TEMPLATE_IMPORT_INPUT.project)throw Error('The intended owner project is not open. Nothing was imported.');
 var dest=null,found=0,i;
 for(i=1;i<=project.numItems;i++){var item=project.item(i);if(item instanceof FolderItem&&item.name==='All Project Files'&&item.parentFolder===project.rootFolder){dest=item;found++;}}
 if(found!==1)throw Error('The project needs one top-level All Project Files folder. Nothing was imported.');
 var chosen=StorylensLibraryModel.plan(SL_TEMPLATE_IMPORT_INPUT.rows,SL_TEMPLATE_IMPORT_INPUT.root),markers=[];
 for(i=1;i<=dest.numItems;i++)markers.push(String(dest.item(i).comment||''));
 var queue=StorylensLibraryModel.pending(chosen,markers),active=project.activeItem;
 function json(v){if(v===null||typeof v==='undefined')return 'null';if(typeof v==='string')return '"'+v.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n')+'"';if(typeof v!=='object')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(json(k)+':'+json(v[k]));return '{'+a.join(',')+'}';}
 var win=new Window('palette','Import templates'),line=win.add('statictext',undefined,'Starting template import…'),bar=win.add('progressbar',undefined,0,queue.length||1),stop=win.add('button',undefined,'Stop after current template');line.preferredSize=[440,25];bar.preferredSize=[440,12];
 SLTemplateLibraryImport={running:true,stop:false,index:0,results:[],state:'running',folder_id:dest.id,total:chosen.length,already_present:chosen.length-queue.length};
 var self=SLTemplateLibraryImport;
 self.save=function(){var f=new File(SL_TEMPLATE_IMPORT_INPUT.report);f.encoding='UTF-8';if(!f.open('w'))throw Error('Could not save import progress.');f.write(json({state:self.state,total:self.total,already_present:self.already_present,processed:self.index,results:self.results,folder_id:self.folder_id,project:project.file.fsName,project_items:project.numItems}));f.close();};
 self.finish=function(state){self.state=state;self.running=false;self.save();try{if(active instanceof CompItem)active.openInViewer();dest.selected=true;}catch(_){}win.close();};
 stop.onClick=function(){self.stop=true;line.text='Stopping after the current template…';};win.onClose=function(){if(self.running)self.stop=true;};
 self.tick=function(){
  if(!self.running)return;if(self.stop){self.finish('stopped');return;}if(app.project!==project){self.state='project_changed';self.running=false;self.save();win.close();return;}if(self.index>=queue.length){self.finish('complete');return;}
  var row=queue[self.index],file=new File(row.path),start=project.numItems;line.text=(self.index+1)+' / '+queue.length+' · '+row.folder;bar.value=self.index;win.update();
  app.beginUndoGroup('Import template - '+row.folder);app.beginSuppressDialogs();
  try{if(!file.exists)throw Error('Project file is unavailable.');var imported=project.importFile(new ImportOptions(file));if(!(imported instanceof FolderItem))throw Error('After Effects did not return the imported project folder.');imported.parentFolder=dest;imported.name=row.folder;imported.comment=StorylensLibraryModel.marker(row.path);var missing=0;function check(folder){for(var n=1;n<=folder.numItems;n++){var child=folder.item(n);if(child instanceof FolderItem)check(child);else if(child instanceof FootageItem&&child.footageMissing)missing++;}}check(imported);self.results.push({path:row.path,folder:row.folder,status:'imported',folder_id:imported.id,items_added:project.numItems-start,missing_media:missing});}
  catch(e){self.results.push({path:row.path,folder:row.folder,status:'failed',error:String(e),items_added:project.numItems-start});}
  finally{app.endSuppressDialogs(false);app.endUndoGroup();}
  self.index++;bar.value=self.index;self.save();app.scheduleTask('SLTemplateLibraryImport.tick()',150,false);
 };
 win.show();self.save();app.scheduleTask('SLTemplateLibraryImport.tick()',150,false);
})();
