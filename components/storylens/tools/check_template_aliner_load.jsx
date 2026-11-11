(function(){
 var base=Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/',rows=[],names=['template-model.js','template-aliner-model.js','template-aliner.jsx','host.jsx'];
 function quote(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n')+'"';}
 for(var i=0;i<names.length;i++){
  try{$.evalFile(new File(base+names[i]));rows.push('{"file":'+quote(names[i])+',"loaded":true}');}
  catch(e){rows.push('{"file":'+quote(names[i])+',"error":'+quote(e.toString())+',"line":'+quote(e.line)+',"filename":'+quote(e.fileName)+',"source":'+quote(e.source)+'}');}
 }
 var output=new File('D:/Full Drive/remove silence/output/template-aliner-evidence/native-load-diagnostic.json');output.encoding='UTF-8';output.open('w');output.write('['+rows.join(',')+']');output.close();
})();
