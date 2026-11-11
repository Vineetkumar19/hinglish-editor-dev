(function(){var root='D:/Full Drive/remove silence',out={ok:false};
 function write(name,value){var f=new File(root+'/output/template-text-repair/'+name);f.encoding='UTF-8';if(!f.open('w'))throw Error('Cannot save '+name);f.write(JSON.stringify(value));f.close();}
 try{if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Use the recovery project.');
 $.evalFile(new File(root+'/editor_plugins/template-text/model.js'));$.evalFile(new File(root+'/editor_plugins/template-text/host.jsx'));
 var c=app.project.itemByID(24516);if(!c||c.name!=='rcb final')throw Error('Recovery master unavailable.');
 app.project.save();write('heading-repair-snapshot.json',SLTemplateText.scan(c));out.ok=true;out.project=app.project.file.fsName;
 }catch(e){out.error=String(e);out.line=e.line;}write('heading-repair-prepare.json',out);
})();
