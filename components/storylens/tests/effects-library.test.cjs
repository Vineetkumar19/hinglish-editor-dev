const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
test('discovers nested projects by folder name, omits ZIP duplicates and Mac/autosave debris',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'sl-effects-'));try{
  for(const f of ['Effect 10/Project File/Ae/Main.aep','Effect 2/deep/Project.aep','Effect 2/__MACOSX/._Main.aep','Effect 2/Adobe After Effects Auto-Save/Old.aep']){const p=path.join(root,f);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,'aep');}
  fs.writeFileSync(path.join(root,'Effect 10.zip'),'zip');fs.writeFileSync(path.join(root,'New Effect.zip'),'zip');
  const c=require('../editor_plugins/effects-library/catalog.cjs').createCatalog(root),r=c.list();
  assert.deepEqual(r.packs.map(p=>p.name),['Effect 2','Effect 10']);assert.deepEqual(r.archives,['New Effect.zip']);assert(!JSON.stringify(r.packs).includes(root.replace(/\\/g,'\\\\')));
  const p=c.resolve(r.packs[0].id,r.packs[0].signature);assert(p.path.endsWith('Project.aep'));
  fs.appendFileSync(p.path,'changed');assert.throws(()=>c.resolve(r.packs[0].id,r.packs[0].signature),/changed/i);
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('catalog refuses forged capability and never follows directory links',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'sl-effects-')),outside=fs.mkdtempSync(path.join(os.tmpdir(),'sl-outside-'));try{
  fs.writeFileSync(path.join(outside,'private.aep'),'aep');try{fs.symlinkSync(outside,path.join(root,'linked'),'junction');}catch(e){if(e.code==='EPERM'){t.diagnostic('Directory-link creation blocked by Windows; real junction probe unavailable.');}else throw e;}
  const c=require('../editor_plugins/effects-library/catalog.cjs').createCatalog(root);assert.equal(c.list().packs.length,0);assert.throws(()=>c.resolve('../private','forged'),/refresh/i);
 }finally{fs.rmSync(root,{recursive:true,force:true});fs.rmSync(outside,{recursive:true,force:true});}
});
test('multiple independent project files require project choice instead of silently choosing alphabetically',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'sl-effects-'));try{for(const f of ['Pack/First.aep','Pack/Second.aep']){const p=path.join(root,f);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,'aep');}const r=require('../editor_plugins/effects-library/catalog.cjs').createCatalog(root).list();assert.equal(r.packs.length,1);assert.equal(r.packs[0].projects.length,2);}finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('main output discovery ignores helpers and chooses only an unambiguous output',()=>{
 const m=require('../editor_plugins/effects-library/model.js');const rows=[{id:'1',name:'Controls',duration:10,used:0},{id:'2',name:'Video Placeholder',duration:10,used:0},{id:'3',name:'Main',duration:10,used:0},{id:'4',name:'Scene 01',duration:10,used:1}];
 assert.equal(m.outputs(rows).selected,'3');const r=m.outputs(rows.concat([{id:'5',name:'Final',duration:10,used:0}]));assert.equal(r.selected,null);assert.equal(r.choices.length,2);
});
test('delivery outputs may contain Video in their name; Video Placeholder and controls remain excluded',()=>{
 const m=require('../editor_plugins/effects-library/model.js');assert.equal(m.outputs([{id:'1',name:'Final Video',duration:10,used:0},{id:'2',name:'Main Controls',duration:10,used:0},{id:'3',name:'Video Placeholder',duration:10,used:0}]).selected,'1');
});
test('bridge only accepts catalog IDs, signatures, exact project choices and bounded request IDs',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'sl-effects-'));try{fs.writeFileSync(path.join(root,'Main.aep'),'aep');const {createCatalog}=require('../editor_plugins/effects-library/catalog.cjs'),c=createCatalog(root),p=c.list().packs[0],{prepare}=require('../editor_plugins/effects-library/bridge.cjs');
  assert(prepare({action:'catalog'},c).result.ok);const r=prepare({action:'insert',pack_id:p.id,signature:p.signature,project_key:p.projects[0].key,request_id:'owner-click-1'},c);assert(r.payload.pack.path.endsWith('Main.aep'));assert.throws(()=>prepare({action:'insert',pack_id:p.id,signature:p.signature,project_key:'../../evil',request_id:'owner-click-1'},c),/refresh/i);assert.throws(()=>prepare({action:'execute',pack_id:p.id,signature:p.signature},c),/action/i);
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
