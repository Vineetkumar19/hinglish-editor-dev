(function(){
 $.evalFile(new File(Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/host.jsx'));
 function read(path){var f=new File(path);f.open('r');var value=JSON.parse(f.read());f.close();return value;}
 function write(name,data){var f=new File('D:/Full Drive/remove silence/output/template-fonts/'+name);f.encoding='UTF-8';f.open('w');f.write(hJSON(data));f.close();}
 var before=read('D:/Full Drive/remove silence/output/template-aliner-evidence/native-before.json');
 var question=read('D:/Full Drive/remove silence/output/template-fonts/native-aliner-result.json');
 var target=app.project.activeItem;if(!(target instanceof CompItem)||target.id!==before.test_comp_id)throw Error('The review composition changed.');
 var choices={};choices['16144']='12264';
 var result=JSON.parse(storylensPanelTemplateAlign({choices:choices,expected:question.expected}));
 var repeat=JSON.parse(storylensPanelTemplateAlign({})),layers=[],owner=null;
 for(var i=1;i<=app.project.numItems;i++)if(app.project.item(i).id===before.original_comp_id)owner=app.project.item(i);
 for(i=1;i<=target.numLayers;i++){var l=target.layer(i);layers.push({name:l.name,source_id:l.source?l.source.id:null,start:l.startTime,inPoint:l.inPoint,outPoint:l.outPoint,audio:l.audioEnabled,comment:l.comment});}
 var ownerLayers=[];for(i=1;i<=owner.numLayers;i++){l=owner.layer(i);ownerLayers.push({index:i,name:l.name,source_id:l.source?l.source.id:null,start:l.startTime,inPoint:l.inPoint,outPoint:l.outPoint,audio:l.audioEnabled,enabled:l.enabled});}
 var all=[];for(i=1;i<=app.project.numItems;i++)if(app.project.item(i) instanceof CompItem)all.push(app.project.item(i));
 write('native-verification.json',{alignment:result,repeat_attempt:repeat,test_layers:layers,owner_duration:owner.duration,owner_layers:ownerLayers,all_project_fonts:storylensTemplateFontReport(all),saved:false});
 target.time=2;target.openInViewer();
})();
