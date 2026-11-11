'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
exports.nativeCode=function(root,host,manifest){
 if(!['premiere','aftereffects'].includes(host)||manifest?.expected?.host!==host)throw Error('Connect the matching Adobe editor before inserting this choice.');
 if(manifest.type!=='timed_choice'||manifest.version!==1||!/^[a-f0-9]{32}$/.test(manifest.operation_id)||!/^[a-f0-9]{64}$/.test(manifest.binding_id)||!/^[a-f0-9]{64}$/.test(manifest.asset_sha256))throw Error('Reopen this saved timeline operation.');
 const base=fs.realpathSync(path.join(root,'output/editor-handoffs/timed-choices/media',manifest.binding_id));
 const file=fs.realpathSync(manifest.path),relative=path.relative(base,file);
 if(!relative||relative.startsWith('..')||path.isAbsolute(relative)||path.basename(file).split('.')[0]!==manifest.asset_sha256)throw Error('Choose this slot’s private checked media before inserting it.');
 const before=fs.statSync(file);if(!before.isFile()||before.size>1500000000)throw Error('Choose a supported saved media option.');
 const hash=crypto.createHash('sha256'),buffer=Buffer.alloc(1024*1024),fd=fs.openSync(file,'r');
 try{let n;while((n=fs.readSync(fd,buffer,0,buffer.length,null))>0)hash.update(buffer.subarray(0,n));}finally{fs.closeSync(fd);}
 const after=fs.statSync(file);
 if(before.size!==after.size||before.mtimeMs!==after.mtimeMs||hash.digest('hex')!==manifest.asset_sha256)throw Error('This saved media changed. Check it again before inserting it.');
 const script=path.join(root,'editor_plugins/shared/timed-choice.jsx'),serializer=host==='aftereffects'?'hJSON':'storylensPanelJSON',method=host==='aftereffects'?'ae':'premiere';
 return '(function(){try{$.evalFile(new File('+JSON.stringify(script)+'));return '+serializer+'(SLTimedChoice.'+method+'('+JSON.stringify(manifest)+'));}catch(e){return '+serializer+'({error:"This timeline choice could not be confirmed. Retry the same choice to reconcile it.",code:"timed_choice_native",details:String(e)});}})()';
};
