(function(){var base='D:/Full Drive/remove silence/',report={ok:false};try{
if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Save the recovery only.');
app.project.save();report.ok=true;report.path=app.project.file.fsName;report.bytes=app.project.file.length;report.items=app.project.numItems;
}catch(e){report.error=String(e);}var f=new File(base+'output/template-text-repair/final-recovery-save.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();})();
