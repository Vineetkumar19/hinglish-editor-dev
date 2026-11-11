(function(){
 var root='D:/Full Drive/remove silence',seen={},comps=[];
 $.evalFile(new File(root+'/editor_plugins/template-text/model.js'));
 $.evalFile(new File(root+'/editor_plugins/template-text/host.jsx'));
 function val(l,n){try{return l.property('ADBE Transform Group').property(n).value;}catch(_){return null;}}
 function walk(c){if(!c||!(c instanceof CompItem)||seen[c.id])return;seen[c.id]=true;var rows=[];
  for(var i=1;i<=c.numLayers;i++){var l=c.layer(i),p=SLTemplateText.text(l),s=l.source,t='';try{if(p)t=p.value.text;}catch(_){}
   rows.push({index:i,id:l.id,name:l.name,enabled:l.enabled,text:p?String(t):null,comment:String(l.comment||''),source:s?{id:s.id,name:s.name,width:s.width,height:s.height,comp:s instanceof CompItem}:null,parent:l.parent?l.parent.index:null,threeD:l.threeDLayer,matte:l.isTrackMatte,start:l.inPoint,end:l.outPoint,position:val(l,'ADBE Position'),scale:val(l,'ADBE Scale'),anchor:val(l,'ADBE Anchor Point'),rotation:val(l,'ADBE Rotate Z')});
   if(s&&s instanceof CompItem)walk(s);
  }comps.push({id:c.id,name:c.name,width:c.width,height:c.height,rows:rows});
 }
 var master=SLTemplateText.item('24516');walk(master);if(app.project.activeItem instanceof CompItem)walk(app.project.activeItem);
 var f=new File(root+'/output/template-text-repair/decoration-inventory.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify({active:app.project.activeItem?app.project.activeItem.id:null,master:master?master.id:null,comps:comps}));f.close();
})();

