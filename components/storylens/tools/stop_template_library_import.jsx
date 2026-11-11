(function(){
var running=typeof SLTemplateLibraryImport!=="undefined"&&SLTemplateLibraryImport.running;
if(running){SLTemplateLibraryImport.stop=true;SLTemplateLibraryImport.finish("stopped");}
var f=new File("D:/Full Drive/remove silence/output/template-library-import/stop-receipt.json");f.open("w");f.write("{\"stopped\":true,\"was_running\":"+(running?"true":"false")+",\"items\":"+app.project.numItems+"}");f.close();
})();