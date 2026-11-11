function storylens3DContext(){
 var c=app.project&&app.project.activeItem;
 if(!(c instanceof CompItem))return hJSON({error:'Open a composition first.',code:'editor_native'});
 return hJSON({comp_id:String(c.id),project_id:storylensProjectId(),time:c.time});
}
function storylens3DInsert(plan,request){
 if(plan.family!=='3d1')return $.global.StorylensSurfaceTitles.create(plan,request);
 var c=app.project.activeItem;
 if(storylensProjectId()!==request.project_id)throw Error('Return to the project where you started.');
 var marker='Storylens 3D '+request.request_id;
 for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(String(item.comment||'')===marker+' done')return {ok:true,reused:true};if(String(item.comment||'')===marker+' building')throw Error('Undo the previous incomplete title before starting again.');}
 if(!(c instanceof CompItem)||String(c.id)!==request.comp_id)throw Error('Return to the composition where you started.');
 if(c.duration-request.time<.6)throw Error('Move the playhead earlier in the composition.');
 var result=null,layer=null,root=null,previousRenderer=c.renderer;$.global.StorylensSolidTitles.rendererFor(c);
 app.beginUndoGroup('Add 3D1 precomp');
 try{
  result=$.global.StorylensCameraTitles({index:plan.index,format:plan.format,depth:plan.depth,rows:plan.rows,marker:marker,sound_fx:plan.sound_fx,sound_mode:plan.sound_mode,delay:plan.delay,deferPlacement:true,manageUndo:false});
  if(!result.ok)throw Error(result.error||'The camera title was not created.');
  var source=null;for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(String(item.id)===result.compositions[0].id)source=item;if(String(item.id)===result.folder_id)root=item;}
  if(!source||!root)throw Error('The new precomp could not be located.');
  c.renderer=result.renderer;layer=c.layers.add(source);layer.name=source.name;layer.threeDLayer=true;layer.collapseTransformation=true;layer.comment='3D1 Camera Precomp';layer.startTime=request.time;layer.inPoint=request.time;layer.outPoint=Math.min(c.duration,request.time+source.duration);
  var scale=Math.min(c.width/source.width,c.height/source.height)*100;layer.property('ADBE Transform Group').property('ADBE Scale').setValue([scale,scale]);
  root.comment=marker+' done';var previousSelection=c.selectedLayers;for(var si=0;si<previousSelection.length;si++)previousSelection[si].selected=false;layer.selected=true;result.placed=1;result.context={project_id:request.project_id,comp_id:request.comp_id,layer_id:String(layer.id),source_id:String(source.id),time:request.time};
 }catch(e){c.renderer=previousRenderer;if(layer)layer.remove();if(root)root.remove();var parents=[];if(result&&result.parent_ids)for(var j=0;j<result.parent_ids.length;j++)for(var k=1;k<=app.project.numItems;k++){var item=app.project.item(k);if(String(item.id)===result.parent_ids[j])parents.push(item);}$.global.StorylensCaptionFolders.cleanup(parents);throw e;}
 finally{app.endUndoGroup();}
 if(result&&result.ok)try{c.openInViewer();}catch(viewError){result.warnings.push('Return to your composition to use the new title.');}
 return result;
}
