/* Select one surface placement/plane and one solved 3D track null. */
(function(){
    var undo=false;
    try{
        var c=app.project&&app.project.activeItem;if(!(c instanceof CompItem))throw Error('Open the shot composition first.');
        var layers=c.selectedLayers,placement=null,track=null;
        if(layers.length!==2)throw Error('Select one surface precomp (or an older placement null) and one 3D track null.');
        for(var i=0;i<layers.length;i++){
            var l=layers[i],candidate=/^3D[23] Surface (Placement|Precomp)$/.test(String(l.comment||''))?l:l.parent&&/^3D[23] Surface Placement$/.test(String(l.parent.comment||''))?l.parent:null;
            if(candidate){if(placement)throw Error('Select only one surface precomp.');placement=candidate;}
            else if(l.nullLayer&&l.threeDLayer)track=l;
        }
        if(!placement||!track)throw Error('Select one surface precomp and one solved 3D track null.');
        var parent=track,depth=0;while(parent){if(parent===placement||depth++>100)throw Error('Choose an independent track null.');parent=parent.parent;}
        var tr=placement.property('ADBE Transform Group'),position=tr.property('ADBE Position'),orientation=tr.property('ADBE Orientation');
        var channels=['ADBE Position','ADBE Orientation','ADBE Scale','ADBE Rotate X','ADBE Rotate Y','ADBE Rotate Z'];
        if(placement.locked||position.dimensionsSeparated)throw Error('Unlock a fresh, unanimated surface placement before attaching it.');
        for(var ch=0;ch<channels.length;ch++){var property=tr.property(channels[ch]);if(property.numKeys||property.expressionEnabled)throw Error('This placement has manual motion. Use a fresh surface precomp to preserve it.');}
        app.beginUndoGroup('Attach surface title to track null');undo=true;
        placement.threeDLayer=true;placement.parent=track;position.setValue([0,0,0]);orientation.setValue([0,0,0]);tr.property('ADBE Scale').setValue([100,100,100]);
        tr.property('ADBE Rotate X').setValue(0);tr.property('ADBE Rotate Y').setValue(0);tr.property('ADBE Rotate Z').setValue(0);
    }catch(e){alert('Surface title: '+String(e));}finally{if(undo)app.endUndoGroup();}
})();
