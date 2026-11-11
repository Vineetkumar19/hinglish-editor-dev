/* Read-only geometry probe on the owner-authorized recovery. Removes its probe. */
(function(){var base='D:/Full Drive/remove silence/',probe=null,report={ok:false,rows:[]},master=null,selection=[];
function read(p){var f=new File(base+p);f.encoding='UTF-8';f.open('r');var s=f.read();f.close();return JSON.parse(s);}
function save(){var f=new File(base+'output/template-text-repair/title-projection.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{
 if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Use recovery only.');
 var seed=read('output/template-text-repair/scene-heading-native-seed.json'),plan=seed.plan;master=app.project.itemByID(Number(plan.composition_id));selection=master.selectedLayers;
 probe=master.layers.addShape();probe.name='Storylens temporary title geometry';probe.enabled=false;probe.guideLayer=true;probe.shy=true;
 var point=probe.property('ADBE Root Vectors Group').addProperty('ADBE Vector Shape - Group').property('ADBE Vector Shape');
 var setup='',queries=[],roots={};for(var i=1;i<=master.numLayers;i++)roots[String(master.layer(i).id)]=master.layer(i);
 for(i=0;i<plan.actions.length;i++){var a=plan.actions[i];if(a.action!=='replace')continue;var root=roots[a.template_layer_id],path=a.text_id.split('/'),refs=['thisComp.layer('+root.index+')'],c=root.source,collapsed=!!root.collapseTransformation;
  for(var j=0;j<path.length;j++){var l=c.layer(Number(path[j]));refs.push('L['+j+'].source.layer('+l.index+')');if(l.collapseTransformation)collapsed=true;if(j<path.length-1)c=l.source;}
  var run=seed.heading_runs[a.template_layer_id+'/'+a.text_id][0],times=[];for(j=1;j<=3;j++)times.push(run.start+(run.end-run.start)*j/4);
  queries.push({id:a.template_layer_id+'/'+a.text_id,text:a.text,refs:refs,times:times,collapsed:collapsed});
 }
 for(i=0;i<queries.length;i+=24){var batch=queries.slice(i,i+24),expr='var V=[];';
  for(j=0;j<batch.length;j++){var q=batch[j];expr+='var L=['+q.refs[0]+'];';for(var k=1;k<q.refs.length;k++)expr+='L.push('+q.refs[k]+');';
   expr+='var ST='+JSON.stringify(q.times)+';for(var s=0;s<ST.length;s++){var T=[ST[s]];for(var z=1;z<L.length;z++)T.push(L[z-1].sourceTime(T[z-1]));var r=L[L.length-1].sourceRectAtTime(T[T.length-1],false);for(var n=0;n<4;n++){var p=[r.left+(n===1||n===2?r.width:0),r.top+(n>=2?r.height:0)];for(z=L.length-1;z>=0;z--)p=L[z].toComp(p,T[z]);V.push([p[0],p[1]]);}}';
  }expr+='createPath(V,[],[],false);';point.expression=expr;var shape=point.valueAtTime(0,false);if(point.expressionError)throw Error(point.expressionError);var vertices=shape.vertices,at=0;
  for(j=0;j<batch.length;j++){q=batch[j];var row={id:q.id,text:q.text,collapsed:q.collapsed,samples:[]};for(var s=0;s<3;s++){var xs=[],ys=[];for(k=0;k<4;k++){var v=vertices[at++];xs.push(v[0]);ys.push(v[1]);}row.samples.push({time:q.times[s],left:Math.min.apply(Math,xs),right:Math.max.apply(Math,xs),top:Math.min.apply(Math,ys),bottom:Math.max.apply(Math,ys)});}report.rows.push(row);}save();
 }
 report.width=master.width;report.height=master.height;report.ok=true;
}catch(e){report.error=String(e);report.line=e.line;}finally{if(probe)probe.remove();for(var i=0;i<selection.length;i++)try{selection[i].selected=true;}catch(_){}save();}
})();
