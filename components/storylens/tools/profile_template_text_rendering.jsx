/* Small reversible native A/B probe; no media or owner layers changed. */
(function(){var root='D:/Full Drive/remove silence',results=[],before=app.disableRendering,created=[],started=new Date().getTime();
 function save(){var f=new File(root+'/output/template-text-repair/rendering-ab-profile.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify({results:results,elapsed_ms:new Date().getTime()-started,items:app.project.numItems}));f.close();}
 try{var comp=app.project.itemByID(24516),source=comp.layer(10).source;
  app.beginUndoGroup('Template Text reversible performance probe');
  for(var mode=0;mode<2;mode++){app.disableRendering=mode===1;var entry={disable_rendering:app.disableRendering,copies:[],name_ms:[]};results.push(entry);save();
   for(var i=0;i<3;i++){var at=new Date().getTime(),copy=source.duplicate();created.push(copy);entry.copies.push(new Date().getTime()-at);at=new Date().getTime();copy.name=source.name+' [Speed probe '+mode+'-'+i+']';entry.name_ms.push(new Date().getTime()-at);save();}
   for(i=created.length-1;i>=0;i--)created[i].remove();created=[];
  }
 }catch(e){results.push({error:String(e)});}finally{for(var n=created.length-1;n>=0;n--)try{created[n].remove();}catch(_){}app.disableRendering=before;app.endUndoGroup();save();}
})();
