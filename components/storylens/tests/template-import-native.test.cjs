const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function harness(count=61){let next=1;const all=[],tasks=[],settings={},rootPath='D:/Editing/AE documentry style editing templates/LatestTemplete';
class FolderItem{remove(){const i=all.indexOf(this);if(i>=0)all.splice(i,1);const p=this.parentFolder;if(p&&p.children){const n=p.children.indexOf(this);if(n>=0)p.children.splice(n,1)}}constructor(name,parent){this.id=next++;this.name=name;this.comment='';this.parentFolder=parent;this.children=[]}get numItems(){return this.children.length}item(i){return this.children[i-1]}}
const root=new FolderItem('Root');function add(name,parent=root){const f=new FolderItem(name,parent);parent.children.push(f);all.push(f);return f}
const project={rootFolder:root,file:{fsName:'D:/Owner.aep'},activeItem:null,selection:[],get numItems(){return all.length},item:i=>all[i-1],items:{addFolder:name=>add(name)},importFile:()=>{add('Imported');return undefined}};
class Folder{constructor(p){this.fsName=p;this.exists=true;this.alias=false}getFiles(){if(this.fsName===rootPath)return Array.from({length:count},(_,i)=>new Folder(rootPath+'/Package'+i));return [new File(this.fsName+'/Main.aep')]}}
class File{constructor(p){this.fsName=p;this.name=p.split('/').pop();this.exists=true;this.modified=new Date(1)}}
const ctx={Folder,File,FolderItem,FootageItem:class{},CompItem:class{},ImportOptions:class{constructor(f){this.file=f}},app:{project,settings:{haveSetting:(a,b)=>b in settings,getSetting:(a,b)=>settings[b],saveSetting:(a,b,v)=>settings[b]=v},beginUndoGroup(){},endUndoGroup(){},beginSuppressDialogs(){},endSuppressDialogs(){},scheduleTask:s=>tasks.push(s)},hJSON:JSON.stringify,storylensProjectId:()=>project.file.fsName,Math,Date};
vm.createContext(ctx);for(const p of ['editor_plugins/shared/template-import-model.js','editor_plugins/shared/aftereffects-template-import.jsx'])vm.runInContext(fs.readFileSync(p,'utf8'),ctx);
return {ctx,project,all,root,add,tasks,call:p=>JSON.parse(ctx.storylensPanelTemplateImport(p)),tick:()=>vm.runInContext(tasks.shift(),ctx),finish(){while(tasks.length)this.tick()},count:n=>{count=n}}}
test('native imports exactly twenty with linked hierarchy even when importFile returns undefined',()=>{const h=harness(),r=h.call({action:'start'});assert.equal(r.total,20);h.finish();const s=h.call({action:'status'});assert.equal(s.state,'complete');assert.equal(s.imported,20);const bin=h.root.children.find(x=>x.name==='Import Template');assert.equal(h.all.filter(x=>x.parentFolder===bin).length,20);assert.ok(h.all.filter(x=>x.parentFolder===bin).every(x=>x.comment.includes('Storylens template package')))});

test('CEP hot loading inside a request function keeps the scheduled job in the persistent engine',()=>{
 const h=harness(3),source=fs.readFileSync('editor_plugins/shared/aftereffects-template-import.jsx','utf8');
 vm.runInContext('(function(){'+source+';return storylensPanelTemplateImport({action:"start"});})()',h.ctx);
 assert.equal(h.ctx.StorylensTemplateImportJob?.running,true);h.finish();assert.equal(h.call({action:'status'}).imported,3);
});

test('imports defer preview rendering without discarding caches or native Undo',()=>{
 const h=harness(2),writes=[],purges=[];let rendering=false;
 Object.defineProperty(h.ctx.app,'disableRendering',{get:()=>rendering,set:v=>{writes.push(v);rendering=v}});
 h.ctx.app.memoryInUse=9*1024*1024*1024;h.ctx.PurgeTarget={IMAGE_CACHES:101,UNDO_CACHES:102};h.ctx.app.purge=p=>purges.push(p);
 h.project.importFile=()=>{assert.equal(rendering,true);h.add('Imported')};h.call({action:'start'});h.finish();
 assert.deepEqual(writes,[true,false,true,false]);assert.deepEqual(purges,[]);assert.equal(rendering,false);
});

test('slow batches preserve image caches and Undo instead of adding unmeasured purge delays',()=>{
 for(const compact of [true,false]){const h=harness(10),purges=[];let clock=0;
  h.ctx.Date=class{getTime(){return clock}};h.ctx.PurgeTarget={IMAGE_CACHES:101,UNDO_CACHES:102};h.ctx.app.purge=value=>purges.push(value);
  h.project.importFile=()=>{clock+=6000;h.add('Imported')};h.call({action:'start',low_memory:compact});h.finish();
  assert.equal(h.call({action:'status'}).imported,10);assert.deepEqual(purges,[]);
 }
});
test('native refuses concurrent start and stops before next file',()=>{const h=harness();h.call({action:'start'});h.tick();assert.equal(h.call({action:'start'}).total,20);h.call({action:'stop'});h.finish();assert.equal(h.call({action:'status'}).imported,1);assert.equal(h.call({action:'status'}).state,'stopped')});
test('newly added library packages appear on the next scan; imported packages are skipped',()=>{const h=harness(3);h.call({action:'start'});h.finish();assert.equal(h.call({action:'start'}).total,0);h.count(4);const n=h.call({action:'start'});assert.equal(n.total,1);h.finish();assert.equal(h.all.filter(x=>x.comment.includes('Storylens template package')).length,4)});
test('changing projects prevents any queued import into the new project',()=>{const h=harness();h.call({action:'start'});h.ctx.app.project={};h.tick();assert.equal(h.all.length,1);assert.equal(h.call({action:'status'}).state,'project_changed')});
test('source failure is plain language and never creates the destination',()=>{const h=harness();h.ctx.Folder=class{constructor(){this.exists=false}};const r=h.call({action:'start'});assert.equal(r.code,'template_import_source');assert.equal(h.all.length,0);assert.doesNotMatch(r.error,/Error:|TypeError/)});

test('a bad native source is rolled back and replaced without stopping twenty good imports',()=>{
 const h=harness();let tries=0;h.project.importFile=()=>{h.add(++tries===1?'Partial':'Imported');if(tries===1)throw Error('Could not read from source')};
 h.call({action:'start'});h.finish();const s=h.call({action:'status'});assert.equal(s.state,'complete');assert.equal(s.imported,20);assert.equal(tries,21);assert.equal(s.skipped,1);assert.equal(h.all.some(x=>x.name==='Partial'),false);assert.equal(s.results[0].status,'skipped');assert.match(s.results[0].details,/Could not read/);
});
test('failed sources never retry endlessly or claim twenty were imported',()=>{
 const h=harness();let tries=0;h.project.importFile=()=>{tries++;h.add('Partial');throw Error('Unreadable')};h.call({action:'start'});h.finish();const s=h.call({action:'status'});assert.ok(tries<=61);assert.equal(s.imported,0);assert.equal(s.shortfall,20);assert.equal(h.all.length,1);assert.equal(s.state,'complete');
});
test('rollback refuses to remove a partial import used by an existing owner item',()=>{
 const h=harness();const owner=h.add('Owner composition');h.project.importFile=()=>{const partial=h.add('Partial');partial.usedIn=[owner];throw Error('Unreadable')};h.call({action:'start'});h.finish();const s=h.call({action:'status'});assert.equal(s.state,'needs_attention');assert.ok(h.all.some(x=>x.name==='Owner composition'));assert.ok(h.all.some(x=>x.name==='Partial'));assert.equal(s.results[0].rollback_complete,false);
});
test('a stopped batch resumes toward its original twenty instead of adding another twenty',()=>{
 const h=harness();h.call({action:'start'});h.tick();h.call({action:'stop'});h.finish();const resumed=h.call({action:'start'});assert.equal(resumed.imported,1);assert.equal(resumed.total,20);h.finish();const s=h.call({action:'status'});assert.equal(s.imported,20);assert.equal(h.all.filter(x=>x.comment.includes('Storylens template package')).length,20);
});

test('AE import into an existing selected bin is regrouped without moving old items',()=>{const h=harness(1),old=h.add('Owner bin');h.project.importFile=()=>h.add('Imported',old);h.call({action:'start'});h.finish();const s=h.call({action:'status'});assert.equal(s.imported,1);assert.equal(old.parentFolder,h.root);const imported=h.all.find(x=>x.comment.includes('Storylens template package'));assert.equal(imported.parentFolder.name,'Import Template')});

test('legacy template root is renamed in place and reused',()=>{const h=harness(1),old=h.add('All Project Files'),id=old.id;h.call({action:'start'});h.finish();assert.equal(old.name,'Import Template');assert.equal(old.id,id);assert.equal(h.all.filter(x=>x.name==='Import Template').length,1)});

test('a twenty-template batch does one post-import inventory pass per file in a large stable project',()=>{
 const h=harness(),size=6000;for(let i=0;i<size;i++)h.add('Owner '+i);h.project.revision=1;
 const item=h.project.item;let reads=0;h.project.item=i=>{reads++;return item(i)};h.project.importFile=()=>{h.add('Imported');h.project.revision++;};
 h.call({action:'start'});h.finish();assert.equal(h.call({action:'status'}).imported,20);assert.ok(reads<size*30,'Unnecessary full-project native reads: '+reads);
});

test('an owner item inserted between import steps is never mistaken for imported content',()=>{
 const h=harness(3);h.project.revision=1;h.project.importFile=()=>{h.add('Imported');h.project.revision++;};h.call({action:'start'});h.tick();const owner=h.add('New owner folder');h.project.revision++;h.finish();assert.equal(owner.parentFolder,h.root);assert.equal(owner.comment,'');assert.equal(h.call({action:'status'}).imported,3);
});

test('saved project checkpoint resumes after native engine state is lost',()=>{
 const h=harness();h.call({action:'start'});h.tick();h.tick();h.tick();h.ctx.StorylensTemplateImportJob=null;h.tasks.length=0;const resumed=h.call({action:'start'});assert.equal(resumed.imported,3);assert.equal(resumed.total,20);h.finish();assert.equal(h.call({action:'status'}).imported,20);assert.equal(h.all.filter(x=>x.comment.includes('Storylens template package')).length,20);
});
test('unchanged failed sources are skipped on resume but a changed source can be retried',()=>{
 const h=harness(1);let tries=0;h.project.importFile=()=>{tries++;throw Error('Unreadable')};h.call({action:'start'});h.finish();h.call({action:'start'});h.finish();assert.equal(tries,1);const Base=h.ctx.File;h.ctx.File=class extends Base{constructor(p){super(p);this.modified=new Date(2)}};h.project.importFile=()=>{tries++;h.add('Imported')};h.call({action:'start'});h.finish();assert.equal(tries,2);assert.equal(h.call({action:'status'}).imported,1);
});

test('unsafe partial recovery remains blocked on retry instead of deleting owner dependencies',()=>{
 const h=harness();const owner=h.add('Owner');h.project.importFile=()=>{const p=h.add('Partial');p.usedIn=[owner];throw Error('Unreadable')};h.call({action:'start'});h.finish();const result=h.call({action:'start'});assert.equal(result.code,'template_import_recovery');assert.ok(h.all.includes(owner));
});

test('legacy partial import after timeline edits is kept aside rather than deleting existing items',()=>{
 const h=harness();h.project.revision=1;h.call({action:'start'});const j=h.ctx.StorylensTemplateImportJob,path=j.queue[0].path;const partial=h.add('Main.aep');h.add('Partial child',partial);j.state='needs_attention';j.running=false;j.results=[{name:'Legacy',path,status:'failed',items_added:2,stage:'native-import'}];j.index=1;h.tasks.length=0;h.project.revision=2;const resumed=h.call({action:'start'});assert.equal(resumed.running,true);assert.ok(h.all.includes(partial));assert.equal(partial.parentFolder.name,'Skipped templates');assert.match(partial.parentFolder.comment,/failed imports/);
});

test('missing assets reject a template before it counts, and a spare fills the twentieth slot',()=>{
 const h=harness();h.ctx.FootageItem=class extends h.ctx.FolderItem{};let attempts=0;
 h.project.importFile=()=>{const folder=h.add('Imported');if(++attempts===1){const m=h.add('Missing asset',folder);Object.setPrototypeOf(m,h.ctx.FootageItem.prototype);m.footageMissing=true;m.mainSource={missingFootagePath:'Z:/gone.png'};}};
 h.call({action:'start'});h.finish();const result=h.call({action:'status'});assert.equal(result.imported,20);assert.equal(attempts,21);assert.equal(result.skipped,1);assert.equal(h.all.some(x=>x.name==='Missing asset'),false);assert.equal(result.results[0].missing_media,1);assert.equal(result.results[0].status,'skipped');
});
test('user Undo of an unsafe partial allows the same batch to resume safely',()=>{
 const h=harness();const owner=h.add('Owner');h.project.importFile=()=>{const m=h.add('Partial');m.usedIn=[owner];throw Error('Unreadable')};h.call({action:'start'});h.finish();h.all.find(x=>x.name==='Partial').remove();h.project.importFile=()=>h.add('Imported');const result=h.call({action:'start'});assert.equal(result.running,true);h.finish();assert.equal(h.call({action:'status'}).imported,20);assert.ok(h.all.includes(owner));
});

test('spares scan the available library once so many bad sources cannot consume valid slots',()=>{
 const h=harness();let tries=0;h.project.importFile=()=>{if(++tries<=35)throw Error('Unreadable');h.add('Imported')};h.call({action:'start'});h.finish();const r=h.call({action:'status'});assert.equal(r.imported,20);assert.equal(tries,55);assert.equal(r.skipped,35);
});

test('a previously imported batch member with newly missing assets no longer counts on resume',()=>{
 const h=harness();h.ctx.FootageItem=class extends h.ctx.FolderItem{};let media,root;h.project.importFile=()=>{root=h.add('Imported');media=h.add('Asset',root);Object.setPrototypeOf(media,h.ctx.FootageItem.prototype);media.footageMissing=false;media.mainSource={};};h.call({action:'start'});h.tick();const badRoot=root,badMedia=media;h.call({action:'stop'});h.finish();badMedia.footageMissing=true;badMedia.mainSource={missingFootagePath:'Z:/gone.png'};h.project.importFile=()=>h.add('Imported');const resumed=h.call({action:'start'});assert.equal(resumed.imported,0);assert.match(badRoot.comment,/rejected assets/);h.finish();assert.equal(h.call({action:'status'}).imported,20);assert.ok(h.all.includes(badMedia));
});

test('adding a restored asset invalidates a missing-template rejection without changing the AEP',()=>{
 const h=harness(1),base=h.ctx.Folder.prototype.getFiles;let restored=false,tries=0;h.ctx.Folder.prototype.getFiles=function(){const files=base.call(this);if(restored&&this.fsName.endsWith('/Package0'))files.push(new h.ctx.File(this.fsName+'/fixed.jpg'));return files};h.project.importFile=()=>{tries++;throw Error('Source unavailable')};h.call({action:'start'});h.finish();h.call({action:'start'});h.finish();assert.equal(tries,1);restored=true;h.project.importFile=()=>{tries++;h.add('Imported')};h.call({action:'start'});h.finish();assert.equal(tries,2);assert.equal(h.call({action:'status'}).imported,1);
});
test('failure cache survives a small per-setting storage limit',()=>{
 const h=harness(),set=h.ctx.app.settings.saveSetting;h.ctx.app.settings.saveSetting=(section,key,value)=>{if(Buffer.byteLength(value,'utf8')>1999)throw Error('Setting too long');set(section,key,value)};let tries=0;h.project.importFile=()=>{if(++tries<=35)throw Error('Unreadable');h.add('Imported')};h.call({action:'start'});h.finish();assert.equal(h.call({action:'status'}).imported,20);assert.match(h.ctx.app.settings.getSetting('Storylens','templateImportFailuresMeta'),/^[AB]\|[2-9]\d*$/);
});

test('a missing proxy or absent file is rejected even when AE missing flag is false',()=>{
 for(const proxy of [false,true]){const h=harness(1);h.ctx.FootageItem=class extends h.ctx.FolderItem{};h.project.importFile=()=>{const f=h.add('Imported'),m=h.add('Media',f);Object.setPrototypeOf(m,h.ctx.FootageItem.prototype);m.footageMissing=false;m.mainSource={};if(proxy)m.proxySource={missingFootagePath:'Z:/lost.png'};else m.file={exists:false,fsName:'Z:/lost.png'};};h.call({action:'start'});h.finish();const result=h.call({action:'status'});assert.equal(result.imported,0);assert.equal(result.shortfall,1);assert.equal(result.skipped,1);}
});
test('a source successfully reconnected within its own package passes validation',()=>{
 const h=harness(1),original=h.ctx.Folder.prototype.getFiles;h.ctx.Folder.prototype.getFiles=function(){const items=original.call(this);if(this.fsName.endsWith('/Package0'))items.push(new h.ctx.File(this.fsName+'/found.png'));return items};h.ctx.FootageItem=class extends h.ctx.FolderItem{};h.project.importFile=()=>{const f=h.add('Imported'),m=h.add('Media',f);Object.setPrototypeOf(m,h.ctx.FootageItem.prototype);m.footageMissing=true;m.mainSource={missingFootagePath:'Z:/found.png'};m.replace=file=>{m.file=file;m.footageMissing=false;m.mainSource={};};};h.call({action:'start'});h.finish();const result=h.call({action:'status'});assert.equal(result.imported,1);assert.equal(result.missing_media,0);assert.equal(result.relinked_media,1);
});

test('an empty new project with only cached bad candidates reports a shortfall without throwing',()=>{
 const h=harness(1);h.project.importFile=()=>{throw Error('Unreadable')};h.call({action:'start'});h.finish();h.all.splice(0);h.root.children.splice(0);h.ctx.StorylensTemplateImportJob=null;const result=h.call({action:'start'});assert.equal(result.ok,true);assert.equal(result.imported,0);assert.equal(result.shortfall,1);assert.equal(result.skipped,1);assert.match(result.message,/usable|0 of 1/);
});
