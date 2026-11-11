function hinglishEscape(value){return '"'+String(value).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n')+'"';}
#include "beats.jsx"
function hinglishSelectedMedia(){
  var paths=[], seen={};
  try{
    var sequence=app.project.activeSequence;
    if(sequence){var selected=sequence.getSelection();for(var i=0;i<selected.length;i++){var item=selected[i].projectItem;if(item){var path=item.getMediaPath();if(path&&!seen[path]){seen[path]=true;paths.push(path);}}}}
    if(!paths.length){var projectItems=app.getCurrentProjectViewSelection();for(var j=0;j<projectItems.length;j++){var p=projectItems[j].getMediaPath();if(p&&!seen[p]){seen[p]=true;paths.push(p);}}}
  }catch(error){return '{"error":'+hinglishEscape(error.toString())+'}';}
  var result='{"paths":[';for(var k=0;k<paths.length;k++){if(k)result+=',';result+=hinglishEscape(paths[k]);}return result+']}';
}
function hinglishExportActiveSequence(outputPath){
  try{
    var sequence=app.project.activeSequence;
    if(!sequence)return '{"error":"Open the sequence you want to edit first."}';
    sequence.exportAsFinalCutProXML(outputPath,1);
    var file=new File(outputPath);
    if(!file.exists)return '{"error":"Premiere could not export the sequence XML."}';
    return '{"path":'+hinglishEscape(outputPath)+',"name":'+hinglishEscape(sequence.name)+'}';
  }catch(error){return '{"error":'+hinglishEscape(error.toString())+'}';}
}
function hinglishImportXML(paths){
  try{if(!(paths instanceof Array)||!paths.length)throw new Error('Choose generated files to import.');for(var i=0;i<paths.length;i++){if(typeof paths[i]!=='string'||!new File(paths[i]).exists)throw new Error('An output file is unavailable.');}var ok=app.project.importFiles(paths,true,app.project.rootItem,false);return ok?'ok':'Premiere could not import the XML';}
  catch(error){return error.toString();}
}


#include "panel.jsx"

#include "photo-import.jsx"
