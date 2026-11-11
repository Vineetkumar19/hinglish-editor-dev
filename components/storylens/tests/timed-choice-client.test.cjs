const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),crypto=require('crypto'),vm=require('vm');
const client=require('../editor_plugins/shared/timed-choice-client.cjs');
function fixture(t){
 const base=path.resolve('cache/test-timed-client');fs.mkdirSync(base,{recursive:true});const root=fs.mkdtempSync(path.join(base,'case-'));
 t.after(()=>{assert.ok(root.startsWith(base+path.sep));fs.rmSync(root,{recursive:true,force:true});});
 const binding='b'.repeat(64),bytes=Buffer.from('fixture-only'),sha=crypto.createHash('sha256').update(bytes).digest('hex');
 const folder=path.join(root,'output/editor-handoffs/timed-choices/media',binding);fs.mkdirSync(folder,{recursive:true});
 const file=path.join(folder,sha+'.mp4');fs.writeFileSync(file,bytes);
 return {root,file,manifest:{type:'timed_choice',version:1,operation_id:'a'.repeat(32),binding_id:binding,
  asset_sha256:sha,path:file,expected:{host:'aftereffects'}}};
}
test('verified private media dispatches only the intended public host function',t=>{
 const f=fixture(t),code=client.nativeCode(f.root,'aftereffects',f.manifest),calls=[];
 const c={$:{evalFile(file){calls.push(file.path);}},File:function(path){this.path=path;},
  hJSON:JSON.stringify,SLTimedChoice:{ae(m){return {ok:true,operation_id:m.operation_id};}}};
 const receipt=JSON.parse(vm.runInNewContext(code,c));assert.equal(receipt.ok,true);
 assert.equal(receipt.operation_id,f.manifest.operation_id);assert.equal(calls.length,1);
 assert.equal(calls[0],path.join(f.root,'editor_plugins/shared/timed-choice.jsx'));
});
test('changed media, wrong host and unbound paths fail before any host code is created',t=>{
 const f=fixture(t);fs.writeFileSync(f.file,'changed');assert.throws(()=>client.nativeCode(f.root,'aftereffects',f.manifest),/changed/i);
 assert.throws(()=>client.nativeCode(f.root,'premiere',f.manifest),/host|editor/i);
 assert.throws(()=>client.nativeCode(f.root,'aftereffects',{...f.manifest,path:path.join(f.root,'outside.mp4')}));
});
