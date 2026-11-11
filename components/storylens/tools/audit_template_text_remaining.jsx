/* Read-only source-graph audit independent of narration/timeremap mapping. */
(function(){var root='D:/Full Drive/remove silence',c=app.project.itemByID(24516),seen={},rows=[],kept=[],total=0;
 function walk(comp,template,path,stack){if(stack[comp.id])return;var next={};for(var k in stack)next[k]=true;next[comp.id]=true;
  for(var n=1;n<=comp.numLayers;n++){var l=comp.layer(n);if(!l.enabled)continue;var p=null;try{p=l.property('ADBE Text Properties').property('ADBE Text Document');}catch(_){}
   var key=template+'/'+comp.id+'/'+l.id;
   if(p&&!seen[key]){seen[key]=true;total++;var text=String(p.valueAtTime(0,true).text);for(var q=1;q<=p.numKeys;q++){var nextText=String(p.keyValue(q).text);if(nextText.length>text.length)text=nextText;}
    var row={root:template,comp_id:String(comp.id),layer_id:String(l.id),layer_index:n,path:path.concat([n]).join('/'),name:l.name,text:text,matte:!!l.isTrackMatte,expression:p.expressionEnabled,comment:String(l.comment||'')};
    if(row.comment.indexOf('"action":"replace"')>=0)kept.push(row);else rows.push(row);
   }
   if(l.source&&l.source instanceof CompItem)walk(l.source,template,path.concat([n]),next);
  }
 }
 for(var i=1;i<=c.numLayers;i++){var l=c.layer(i);if(l.enabled&&l.source&&l.source instanceof CompItem)walk(l.source,String(l.id),[],{});}
 var f=new File(root+'/output/template-text-repair/remaining-source-text.json');f.encoding='UTF-8';if(f.open('w')){f.write(JSON.stringify({enabled_text:total,kept:kept,remaining:rows}));f.close();}
})();
