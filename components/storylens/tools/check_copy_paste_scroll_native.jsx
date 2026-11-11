/* Reversible tiny native fixture. Never saves or touches the owner's template layers. */
(function(){
 var root='D:/Full Drive/remove silence',out=root+'/output/copy-paste-evidence/scroll-speed/',control=new File(out+'native-action.json'),report={},operation='';
 try{
  control.open('r');operation=JSON.parse(control.read()).action;control.close();
  if(operation==='setup'||operation==='setup3d'){
   if(typeof SLScrollCheck!=='undefined'&&SLScrollCheck)throw Error('A fixture already exists.');
   var oldComp=null,oldSelection=app.project.selection||[];
   for(var i=1;i<=app.project.numItems;i++){var p=app.project.item(i);if(p instanceof CompItem&&p.name==='rcb final')oldComp=p;}
   if(!oldComp)throw Error('The owner composition is not open in this project.');
   var state={project:app.project,before:app.project.numItems,owner:oldComp,selection:oldSelection,clipboard:typeof SLCopyPaste!=='undefined'?SLCopyPaste.clipboard:null,history:typeof SLCopyPaste!=='undefined'?(SLCopyPaste.history||[]).slice(0):[],targetRef:typeof SLCopyPaste!=='undefined'?SLCopyPaste.targetRef:null,created:[]};
   SLScrollCheck=state;state.folder=app.project.items.addFolder('ZZ Storylens scroll check');state.folder.comment='Storylens owned scroll-speed fixture';state.created.push(state.folder);
   var imageCount=operation==='setup3d'?3:200;
   for(var j=1;j<=imageCount;j++){var image=app.project.importFile(new ImportOptions(new File(out+'small-check.png')));image.name='Image '+('000'+j).slice(-3);image.parentFolder=state.folder;state.created.push(image);if(j===imageCount)state.image=image;}
   state.holder=state.folder.items.addComp('Photo 1',640,360,1,3,30);state.created.push(state.holder);state.holder.layers.add(state.image);
   state.holder2=state.folder.items.addComp('Photo 2',640,360,1,3,30);state.created.push(state.holder2);state.holder2.layers.add(state.image);
   state.template=state.folder.items.addComp('Fixture template',640,360,1,6,30);state.created.push(state.template);state.template.layers.add(state.holder);var second=state.template.layers.add(state.holder2);second.startTime=3;second.outPoint=6;
   state.comp=state.folder.items.addComp('ZZ Storylens paste check',640,360,1,6,30);state.created.push(state.comp);state.layer=state.comp.layers.add(state.template);state.layer.selected=true;
   if(operation==='setup3d'){
    state.layer.threeDLayer=true;state.layer.property('ADBE Transform Group').property('ADBE Orientation').setValueAtTime(0,[0,-8,0]);state.layer.property('ADBE Transform Group').property('ADBE Orientation').setValueAtTime(6,[0,8,0]);
    var camera=state.comp.layers.addCamera('Fixture Camera',[320,180]);camera.selected=false;state.layer.selected=true;
    var mask=state.holder.layer(1).property('ADBE Mask Parade').addProperty('ADBE Mask Atom'),shape=new Shape();shape.vertices=[[40,30],[600,30],[600,330],[40,330]];shape.inTangents=[[0,0],[0,0],[0,0],[0,0]];shape.outTangents=[[0,0],[0,0],[0,0],[0,0]];shape.closed=true;mask.property('ADBE Mask Shape').setValue(shape);mask.maskMode=MaskMode.ADD;
   }
   state.comp.openInViewer();var selected=app.project.selection||[];for(i=0;i<selected.length;i++)selected[i].selected=false;state.image.selected=true;
   report={ok:true,action:operation,items_before:state.before,items_after:app.project.numItems,fixture_folder:state.folder.id,image:state.image.id,comp:state.comp.id,layer:state.layer.id,native_id_lookup:typeof app.project.itemByID};
  }else if(operation==='inventory'){
   var s=SLScrollCheck;if(!s||s.project!==app.project)throw Error('Fixture project changed.');report={ok:true,templates:[]};
   for(var ri=1;ri<=s.owner.numLayers;ri++){var layer=s.owner.layer(ri),source=layer.source;if(!(source instanceof CompItem))continue;try{var graph=SLCopyPaste.graph(source,true),scan=SLCopyPasteModel.scan(SLCopyPaste.graph(source),source.id),three=0,masks=0,count=0;
    for(var id in graph)if(graph.hasOwnProperty(id)){count++;var item=SLCopyPaste.item(id);for(var li=1;li<=item.numLayers;li++){var leaf=item.layer(li);if(leaf.threeDLayer)three++;var mp=leaf.property('ADBE Mask Parade');if(mp)masks+=mp.numProperties;}}
    report.templates.push({name:source.name,id:source.id,comps:count,slots:scan.slots.length,three_d:three,masks:masks});
   }catch(error){report.templates.push({name:source.name,error:String(error)});}}
  }else if(operation==='switchReal'){
   var s=SLScrollCheck;if(!s||s.project!==app.project||s.layer.source!==s.template||s.layer.comment)throw Error('Undo the fixture paste before switching.');
   var chosen=null;for(var ri=1;ri<=s.owner.numLayers;ri++){var source=s.owner.layer(ri).source;if(source instanceof CompItem&&source.name==='Color_Edit')chosen=source;}
   if(!chosen)throw Error('The chosen real template is unavailable.');
   if(s.comp.numLayers===2&&s.comp.layer(1) instanceof CameraLayer)s.comp.layer(1).remove();
   s.layer.threeDLayer=false;s.layer.replaceSource(chosen,false);s.template=chosen;s.comp.width=chosen.width;s.comp.height=chosen.height;s.layer.property('ADBE Transform Group').property('ADBE Anchor Point').setValue([chosen.width/2,chosen.height/2]);s.layer.property('ADBE Transform Group').property('ADBE Position').setValue([chosen.width/2,chosen.height/2]);s.layer.selected=true;
   s.comp.openInViewer();var selected=app.project.selection||[];for(var k=0;k<selected.length;k++)selected[k].selected=false;s.image.selected=true;
   report={ok:true,action:operation,template:chosen.name,source:chosen.id,items:app.project.numItems};
  }else if(operation==='receipt'){
   var s=SLScrollCheck;if(!s||s.project!==app.project)throw Error('Fixture project changed.');
   var data={ok:true,action:operation,items:app.project.numItems,revision:app.project.revision,root_id:s.layer.source.id,original_root:s.template.id,comment:String(s.layer.comment),history:typeof SLCopyPaste!=='undefined'?(SLCopyPaste.history||[]).length:0};
   if(typeof SLCopyPaste!=='undefined'){var t={comp:s.comp,layer:s.layer,root:s.layer.source};data.next=SLCopyPaste.read(t).next;data.performance=SLCopyPaste.lastPerformance;data.framing=SLCopyPaste.lastFraming;data.projection=SLCopyPaste.lastProjection;}
   report=data;
  }else if(operation==='cleanup'){
   var s=SLScrollCheck;if(!s||s.project!==app.project)throw Error('Fixture project changed.');
   if(s.layer.source!==s.template||s.layer.comment)throw Error('Undo the fixture paste before cleanup.');
   if(app.project.numItems!==s.before+s.created.length)throw Error('Unexpected objects exist; keep fixture for review.');
   var selected=app.project.selection||[];for(var k=0;k<selected.length;k++)selected[k].selected=false;
   s.owner.openInViewer();for(k=0;k<s.selection.length;k++)try{s.selection[k].selected=true;}catch(_){}
   s.folder.remove();
   if(typeof SLCopyPaste!=='undefined'){SLCopyPaste.clipboard=s.clipboard;SLCopyPaste.history=s.history;SLCopyPaste.targetRef=s.targetRef;}
   report={ok:true,action:operation,items_after:app.project.numItems,items_before:s.before,owner:s.owner.name};SLScrollCheck=null;
  }else throw Error('Unknown test action');
 }catch(e){report={ok:false,action:operation,error:String(e),line:e.line};}
 var file=new File(out+'native-'+operation+'.json');file.encoding='UTF-8';if(file.open('w')){file.write(JSON.stringify(report));file.close();}
})();
