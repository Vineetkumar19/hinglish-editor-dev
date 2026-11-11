(function(){
 var rows=[],output={version:app.version,project:app.project.file?app.project.file.fsName:null,used:[],available:[],loads:[]};
 var base=Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/';
 try{$.evalFile(new File(base+'host.jsx'));output.loads.push({file:'host.jsx',loaded:true});}
 catch(e){output.loads.push({file:'host.jsx',error:e.toString(),line:e.line,filename:e.fileName});}
 function info(f){return {postScriptName:f.postScriptName,familyName:f.familyName,styleName:f.styleName,isSubstitute:f.isSubstitute,fontID:f.fontID};}
 try{
  var used=app.project.usedFonts;
  for(var i=0;i<used.length;i++){var row=info(used[i].font);row.usage_count=used[i].usedAt.length;output.used.push(row);}
  var all=app.fonts.allFonts;
  for(var j=0;j<all.length;j++)for(var k=0;k<all[j].length;k++)output.available.push(info(all[j][k]));
 }catch(e){output.error=e.toString();}
 var file=new File('D:/Full Drive/remove silence/output/template-fonts/native-fonts.json');file.encoding='UTF-8';file.open('w');file.write(hJSON(output));file.close();
})();
