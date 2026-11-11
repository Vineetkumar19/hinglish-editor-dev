const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('project identity recovers from an invalid native reference after switching AEPs',()=>{
 const current={file:{fsName:'D:/New review.aep'}},c={app:{project:current},Date};vm.createContext(c);
 vm.runInContext(fs.readFileSync('editor_plugins/shared/aftereffects-panel.jsx','utf8'),c);
 let expired=true,stored;Object.defineProperty(c,'storylensPanelProject',{configurable:true,get(){if(expired)throw Error('Object is invalid');return stored},set(v){stored=v;expired=false}});
 assert.equal(c.storylensProjectId(),'D:/New review.aep');assert.equal(stored,current);
 c.app.project={file:null};const id=c.storylensProjectId();assert.match(id,/^unsaved-/);assert.equal(c.storylensProjectId(),id);
});

test('AE hot requests refresh project identity without clearing active tool state',()=>{
 const code=fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8');assert.match(code,/files.unshift\('editor_plugins\/shared\/aftereffects-project-session.jsx'\)/);
 const c={app:{project:{file:{fsName:'D:/Current.aep'}}},Date,storylensPanelProject:null,storylensPanelUnsavedId:'old',StorylensTemplateImportJob:{running:true},SLCopyPaste:{copied:true}};vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/shared/aftereffects-project-session.jsx','utf8'),c);assert.equal(c.storylensProjectId(),'D:/Current.aep');assert.equal(c.StorylensTemplateImportJob.running,true);assert.equal(c.SLCopyPaste.copied,true);
});
