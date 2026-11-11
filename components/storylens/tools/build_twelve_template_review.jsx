(function(){
 $.evalFile(new File(Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/host.jsx'));
 function find(id){for(var i=1;i<=app.project.numItems;i++)if(app.project.item(i).id===id)return app.project.item(i);return null;}
 var owner=find(24516);if(!(owner instanceof CompItem)||owner.name!=='rcb final')throw Error('The expected original video composition was not found.');
 var folderIds=[16144,17468,19230,20116,22606,1,9895,7005,13727,12278,3772,15488];
 var choices={'16144':'16189','17468':'17471','19230':'20033','20116':'20119','22606':'24501','1':'2778','9895':'9896','7005':'7007','13727':'14388','12278':'13441','3772':'4712','15488':'15490'};
 var original={id:owner.id,duration:owner.duration,numLayers:owner.numLayers,audio:owner.layer(1).audioEnabled};
 app.beginUndoGroup('Prepare complete template review');
 var review=owner.duplicate();review.name='rcb final - 12 Templates Review';review.parentFolder=owner.parentFolder;review.resolutionFactor=[4,4];review.openInViewer();
 app.endUndoGroup();
 var result=JSON.parse(storylensPanelTemplateAlign({choices:choices,expected:{project_id:storylensProjectId(),composition_id:String(review.id),folder_ids:folderIds}}));
 var layers=[];for(var k=1;k<=review.numLayers;k++){var layer=review.layer(k);layers.push({name:layer.name,source_id:layer.source?layer.source.id:null,start:layer.startTime,inPoint:layer.inPoint,outPoint:layer.outPoint,audio:layer.audioEnabled,scale:layer.property('ADBE Transform Group').property('ADBE Scale').value});}
 var receipt={result:result,review_comp_id:review.id,original_before:original,original_after:{id:owner.id,duration:owner.duration,numLayers:owner.numLayers,audio:owner.layer(1).audioEnabled},layers:layers,source_folders:folderIds,saved:false,applied_to_original:false};
 var out=new File('D:/Full Drive/remove silence/output/template-aliner-evidence/twelve-template-review.json');out.encoding='UTF-8';out.open('w');out.write(hJSON(receipt));out.close();
 review.time=2;review.openInViewer();
})();
