(function(){
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/template-assembler/host.jsx'));
 var output=new File('D:/Full Drive/remove silence/output/template-assembler-evidence/native-errors.json'),before=app.project.numItems,rows=SLTA.ui.rows();
 var shortResult=SLTA.buildAE({name:'Should not be created',rows:rows,options:{seconds:600,repeat:false}});
 var emptyResult=SLTA.inspect({path:'D:/Editing/AE documentry style editing templates/envato doc/1.1/best/Historical Slideshow/(Footage)/01.ASSETS/COMPS/Transitions/LL/Light Leaks.aep'});
 output.encoding='UTF-8';output.open('w');output.write(SLTA.json({beforeItems:before,afterItems:app.project.numItems,shortListReply:shortResult,emptyFileReply:emptyResult,projectSaved:false}));output.close();
})();
