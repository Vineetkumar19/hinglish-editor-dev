(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,n=m.number,c=m.choice;
 m.register({id:'layers',name:'Layer Utilities'},[
 {number:73,id:'anchor',name:'Anchor Grid',help:'Move a 2D layer’s anchor without moving its visible content. Scale and rotation must be static.',settings:[c('position','Anchor','center',['top-left','top','top-right','left','center','right','bottom-left','bottom','bottom-right'])]},
 {number:74,id:'align',name:'Align & Distribute',help:'Align visible 2D bounds at the playhead. Distribution spaces centres evenly.',settings:[c('mode','Action','center-x',['left','center-x','right','top','center-y','bottom','distribute-x','distribute-y']),c('reference','Reference','composition',['composition','selection']),n('margin','Margin (px)',20,0,2000,1)]},
 {number:75,id:'fit-fill',name:'Fit / Fill',help:'Fit static unparented 2D content to the frame, preserving aspect ratio and centering its visible bounds.',settings:[c('mode','Sizing','fit',['fit','fill']),n('margin','Margin (px)',0,0,2000,1)]},
 {number:76,id:'precompose',name:'Smart Precompose',help:'Move selected layers into an editable precomp. Full duration preserves composition timing; trimmed duration shifts its internal start.',settings:[{id:'name',label:'Name',type:'text',value:'Precomp',maxLength:100},c('duration','Duration','full',['full','trimmed'])]},
 {number:77,id:'parent-null',name:'Parent to Null',help:'Create one control null for selected layers that share a parent and dimensionality.',settings:[{id:'name',label:'Control name',type:'text',value:'Group control',maxLength:100}]},
 {number:78,id:'resize-content',name:'Resize to Content',help:'Resize this 2D composition to selected visible bounds at the current frame. Check the rest of the animation afterward.',settings:[n('padding','Padding (px)',20,0,2000,1)]}
 ]);
})(typeof $!=='undefined'&&$.global?$.global:this);
