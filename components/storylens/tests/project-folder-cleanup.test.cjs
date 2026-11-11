const test=require('node:test'),assert=require('node:assert/strict');
const {finishFolderCleanup}=require('../editor_plugins/shared/project-folder-cleanup.cjs');
test('only successful AE alignment runs the bounded helper, after native completion',async()=>{
 const calls=[],run=async(...args)=>{calls.push(args);return {ok:true,message:'Project folders collapsed.'}};
 const result={ok:true,project_id:'D:/Edits/test.aep',placements:[{}]};
 assert.equal(await finishFolderCleanup('premiere','templateAlign',{},result,run),result);assert.equal(calls.length,0);
 await finishFolderCleanup('aftereffects','templateAlign',{collapse_folders:false},result,run);assert.equal(calls.length,0);
 await finishFolderCleanup('aftereffects','templateAlign',{}, {needs_choices:true},run);assert.equal(calls.length,0);
 const done=await finishFolderCleanup('aftereffects','templateAlign',{},result,run);
 assert.equal(calls.length,1);assert.equal(calls[0][0],result.project_id);assert.equal(done.ui_cleanup.ok,true);assert.equal(done.placements,result.placements);
});
test('helper failure cannot turn successful alignment into a failed edit',async()=>{
 const done=await finishFolderCleanup('aftereffects','templateAlign',{}, {ok:true,project_id:'p',placements:[{}]},async()=>{throw Error('timeout')});
 assert.equal(done.ok,true);assert.equal(done.ui_cleanup.ok,false);assert.match(done.ui_cleanup.message,/templates are kept/i);
});
test('manual cleanup runs without adding timeline layers',async()=>{
 const done=await finishFolderCleanup('aftereffects','templateCollapseFolders',{}, {ok:true,project_id:'p'},async()=>({ok:true,message:'Project folders collapsed.'}));
 assert.equal(done.ui_cleanup.ok,true);assert.equal(done.placements,undefined);
});
test('executor uses argument boundaries and a fixed runtime without a shell',async()=>{
 const {runFolderCleanup}=require('../editor_plugins/shared/project-folder-cleanup.cjs');let invocation;
 const r=await runFolderCleanup('D:/Storylens','D:/Projects/owner & text.aep',(exe,args,options,callback)=>{invocation={exe,args,options};callback(null,'{"ok":true,"message":"Project folders collapsed."}');});
 assert.equal(r.ok,true);assert.equal(invocation.args.at(-1),'D:/Projects/owner & text.aep');assert.equal(invocation.options.shell,false);assert.equal(invocation.options.windowsHide,true);assert.equal(invocation.options.timeout,12000);
});

test('unsaved AE sessions reach the guarded helper without forcing a Save As',async()=>{
 const {runFolderCleanup}=require('../editor_plugins/shared/project-folder-cleanup.cjs');let called=false;
 const result=await runFolderCleanup('D:/Storylens','unsaved-123456',(exe,args,opts,cb)=>{called=true;assert.equal(args.at(-1),'unsaved-123456');cb(null,'{"ok":true}');});assert.equal(called,true);assert.equal(result.ok,true);
});
test('preset imports collapse folders only after a successful scene insertion, never during browsing',async()=>{let calls=0;const run=async()=>{calls++;return {ok:true}};for(const action of ['catalog','gallery','galleryStatus','destination'])await finishFolderCleanup('aftereffects','presetLibrary',{action},{ok:true,project_id:'p'},run);assert.equal(calls,0);await finishFolderCleanup('aftereffects','presetLibrary',{action:'insertChoice'},{ok:false,project_id:'p'},run);assert.equal(calls,0);const result=await finishFolderCleanup('aftereffects','presetLibrary',{action:'insertChoice'},{ok:true,project_id:'p',layer_id:'7'},run);assert.equal(calls,1);assert.equal(result.ui_cleanup.ok,true);});
