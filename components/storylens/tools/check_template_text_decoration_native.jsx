(function(){var root='D:/Full Drive/remove silence',out={ok:false},items=[],seen={};
 $.evalFile(new File(root+'/editor_plugins/template-text/model.js'));$.evalFile(new File(root+'/editor_plugins/template-text/host.jsx'));
 function walk(c){if(!c||!(c instanceof CompItem)||seen[c.id])return;seen[c.id]=true;if(/ \[SLTT /.test(c.name))items.push(c);for(var i=1;i<=c.numLayers;i++){var s=c.layer(i).source;if(s&&s instanceof CompItem)walk(s);}}
 var master=app.project.itemByID(24516),shortComp=app.project.itemByID(87529),oldResolution=shortComp.resolutionFactor;
 try{if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Use the recovery project.');walk(master);walk(shortComp);
  shortComp.resolutionFactor=[2,2];shortComp.saveFrameToPng(230.83,new File(root+'/output/template-text-repair/decorations-before.png'));
  app.beginUndoGroup('Template Text decoration repair');try{out.result=SLTemplateText.cleanDecorations(items);}finally{app.endUndoGroup();}
  shortComp.saveFrameToPng(230.83,new File(root+'/output/template-text-repair/decorations-after.png'));out.ok=true;out.comps=items.length;
 }catch(e){out.error=String(e);}finally{shortComp.resolutionFactor=oldResolution;var f=new File(root+'/output/template-text-repair/decoration-native-result.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(out));f.close();}
})();
