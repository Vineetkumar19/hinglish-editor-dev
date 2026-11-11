/* Read-only capability check, no controls or values added. */
(function(){var root='D:/Full Drive/remove silence',result={properties:[],error:''};
 try{var main=app.project.itemByID(24516),source=main.layer(10).source,seen={},pending=[source],count=0;
  while(pending.length&&result.properties.length<4&&count++<300){var c=pending.pop();if(seen[c.id])continue;seen[c.id]=true;
   for(var n=1;n<=c.numLayers;n++){var l=c.layer(n),p=null;try{p=l.property('ADBE Text Properties').property('ADBE Text Document');}catch(_){}
    if(p){result.properties.push({comp:c.name,layer:l.name,can_add_local:typeof p.canAddToMotionGraphicsTemplate==='function'?p.canAddToMotionGraphicsTemplate(c):null,can_add_root:typeof p.canAddToMotionGraphicsTemplate==='function'?p.canAddToMotionGraphicsTemplate(source):null,keys:p.numKeys,expression:p.expressionEnabled});if(result.properties.length>=4)break;}
    else if(l.source&&l.source instanceof CompItem)pending.push(l.source);
   }
  }result.visited=count;
 }catch(e){result.error=String(e);}
 var f=new File(root+'/output/template-text-repair/essential-property-probe.json');f.encoding='UTF-8';if(f.open('w')){f.write(JSON.stringify(result));f.close();}
})();
