const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
test('AE evalFile called inside a CEP request exposes the scene model through the engine global',()=>{const vm=require('node:vm'),ctx={};vm.createContext(ctx);vm.runInContext('$={global:this};(function(){'+fs.readFileSync('editor_plugins/cinematic-text/model.js','utf8')+'}).call({requestScope:true});',ctx);assert.equal(vm.runInContext('typeof SLCinematicModel.scenes',ctx),'function');});
test('an inherited module object cannot hide the AE engine-global scene model',()=>{const vm=require('node:vm'),ctx={module:{exports:{}}};vm.createContext(ctx);vm.runInContext('$={global:this};(function(){'+fs.readFileSync('editor_plugins/cinematic-text/model.js','utf8')+'}).call({});',ctx);assert.equal(vm.runInContext('typeof SLCinematicModel.scenes',ctx),'function');});
test('real pack rules select the 12, 3 and 21 delivery comps, natural ordered, excluding helpers',()=>{
 const m=require('../editor_plugins/cinematic-text/model.js');
 for(const [kind,n,name] of [['interactive',12,i=>'Scene '+i],['cinematic',3,i=>'title_0'+i],['intro',21,i=>'Cinematic Title '+i],['lowerThirds',6,i=>'Cinematic Lower Third '+i]]){
  const rows=Array.from({length:n},(_,i)=>({id:String(i+1),name:name(i+1),text:true})).reverse();
  rows.push({id:'helper',name:'Color Scene 1',text:true},{id:'preview',name:'Preview',text:true});
  assert.deepEqual(m.scenes(rows,kind).map(x=>x.name),Array.from({length:n},(_,i)=>name(i+1)));
 }
});
test('background classification preserves text, mattes, controllers, adjustment and masked animation solids',()=>{
 const m=require('../editor_plugins/cinematic-text/model.js');
 assert.equal(m.background({name:'Background',kind:'solid',enabled:true}),true);
 assert.equal(m.background({name:'BG',kind:'shape',enabled:true}),true);
 assert.equal(m.background({name:'Black Solid 1',kind:'solid',fullFrame:true,bottom:true,enabled:true}),true);
 for(const flags of [{text:true},{matte:true},{controller:true},{adjustment:true},{containsText:true}])assert.equal(m.background({name:'Background',kind:'solid',...flags}),false);
 assert.equal(m.background({name:'Background',kind:'shape',masked:true,parent:true}),true);
 assert.equal(m.background({name:'Shape Layer 1',kind:'shape',fullFrame:true,filled:true,bottom:true}),true);
 assert.equal(m.background({name:'Shape Layer 1',kind:'shape',fullFrame:true,filled:false,bottom:true}),false);
 assert.equal(m.background({name:'Animated underline',kind:'shape'}),false);
});
test('future packs expose text delivery roots and numbered scenes without exposing text-edit helper comps',()=>{
 const m=require('../editor_plugins/cinematic-text/model.js');
 const rows=[{id:'a',name:'Title 10',text:true,usedBy:0},{id:'b',name:'Title 2',text:true,usedBy:1},{id:'c',name:'Edit Text 1',text:true,usedBy:2},{id:'d',name:'Logo',text:false,usedBy:0}];
 assert.deepEqual(m.scenes(rows,'generic').map(x=>x.id),['b','a']);
});
test('catalog picks one source per pack, skips archives, Mac metadata, backups and external symlinks',()=>{
 const {createCatalog}=require('../editor_plugins/cinematic-text/catalog.cjs');
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sl-cinematic-'));
 try{for(const f of ['12-text-interactive-titles/After Effects/main.aep','cinematic-title-pack/Main.aep','intro-cinematic-trailer-titles/Main.aep','intro-cinematic-trailer-titles/__MACOSX/._Main.aep','intro-cinematic-trailer-titles/Adobe After Effects Auto-Save/Main 2.aep']){fs.mkdirSync(path.dirname(path.join(dir,f)),{recursive:true});fs.writeFileSync(path.join(dir,f),'fixture');}
 const c=createCatalog(dir),r=c.list();assert.equal(r.packs.length,3);assert.equal(r.packs.find(p=>p.kind==='intro').expected,21);assert.throws(()=>c.resolve('../escape'),/Refresh/);
 fs.mkdirSync(path.join(dir,'new-pack'));fs.writeFileSync(path.join(dir,'new-pack/Fresh.aep'),'new');assert.equal(c.list().packs.length,4);
 const p=r.packs[0],valid=c.resolve(p.id,p.signature);assert(valid.path.endsWith('.aep'));fs.appendFileSync(valid.path,'changed');assert.throws(()=>c.resolve(p.id,p.signature),/changed/);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('future packs with several distinct AEP projects expose another level instead of silently dropping projects',()=>{const {createCatalog}=require('../editor_plugins/cinematic-text/catalog.cjs'),dir=fs.mkdtempSync(path.join(os.tmpdir(),'sl-effects-multiple-'));try{fs.mkdirSync(path.join(dir,'Future Pack'));for(const f of ['Title Set A.aep','Title Set B.aep'])fs.writeFileSync(path.join(dir,'Future Pack',f),'fixture');const c=createCatalog(dir),p=c.list().packs[0];assert.equal(p.projects.length,2);assert.notEqual(p.projects[0].id,p.projects[1].id);assert.equal(path.basename(c.resolve(p.projects[1].id,p.projects[1].signature).path),'Title Set B.aep')}finally{fs.rmSync(dir,{recursive:true,force:true})}});
