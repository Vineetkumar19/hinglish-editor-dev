(function(){
 var root='D:/Full Drive/remove silence',out=new File(root+'/output/template-assembler-evidence/native-ae-inspection.json');
 function write(s){out.encoding='UTF-8';out.open('w');out.write(s);out.close();}
 try{
  var before=app.project?app.project.file:null;
  if(typeof SLTA!=='undefined'&&SLTA.ui)try{SLTA.ui.window.close();}catch(_){}
  $.evalFile(new File(root+'/editor_plugins/template-assembler/Template Assembler.jsx'));
  SLTA.ui.append(['D:/Editing/AE documentry style editing templates/envato doc/Upload/Project/Historical_Documentary_v6.aep','D:/Editing/AE documentry style editing templates/envato doc/The Fog of History Logo/The Fog of History Logo.aep']);
  SLTA.ui.inspect();
  write(SLTA.json({ok:true,sourceProjectBefore:before?before.fsName:null,sourceProjectAfter:app.project.file?app.project.file.fsName:null,rows:SLTA.ui.rows()}));
 }catch(e){write(typeof SLTA!=='undefined'?SLTA.error(e):String(e));}
})();
