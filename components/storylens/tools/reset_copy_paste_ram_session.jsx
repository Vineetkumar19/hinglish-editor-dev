/* Preserve every current edit in a separate checkpoint before releasing AE RAM. */
(function(){var base='D:/Full Drive/remove silence/',report={ok:false};function write(){var f=new File(base+'output/copy-paste-evidence/scroll-speed/ram-reset.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('The owner-authorized recovery is required.');
var destination=new File(base+'output/template-text-repair/Storylens recovery RAM check 2026-10-26.aep');if(destination.exists)throw Error('RAM checkpoint already exists; do not overwrite it.');
report.source=app.project.file.fsName;report.items=app.project.numItems;report.phase='saving';write();app.project.save(destination);report.path=app.project.file.fsName;report.bytes=destination.length;report.ok=destination.exists&&destination.length>1000000;report.phase=report.ok?'saved':'failed';write();if(report.ok)app.quit();
}catch(e){report.error=String(e);report.phase='failed';write();}})();
