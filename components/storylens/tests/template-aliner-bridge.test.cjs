const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {finishFolderCleanup}=require('../editor_plugins/shared/project-folder-cleanup.cjs');
function bridge(host='aftereffects',fail=false,nativeResult={ok:true,project_id:'D:/Edits/owner.aep',placements:[{}]}){
 const sequence=[],messages=[],codes=[],source={},nodes={storylensPanel:{contentWindow:{postMessage:r=>{sequence.push('response');messages.push(r);}}},shellStatus:{},reconnect:{}};let receive;
 const context={URL,Date,Math,JSON,String,Error,require:name=>name==='path'?path:{finishFolderCleanup,runFolderCleanup:async()=>{sequence.push('cleanup');if(fail)throw Error('Timeout');return {ok:true,message:'Project folders collapsed.'}}},fetch:async()=>({ok:true}),document:{getElementById:id=>nodes[id],documentElement:{dataset:{host}}},window:{HINGLISH_APP_ROOT:'D:/Storylens',HINGLISH_BRIDGE:'http://127.0.0.1:8765',addEventListener:(type,fn)=>{receive=fn},__adobe_cep__:{evalScript:(code,cb)=>{sequence.push('native');codes.push(code);cb(JSON.stringify(nativeResult));}}}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8'),context);
 async function send(action='templateAlign',payload={},overrides={}){const nonce=/nonce=([^&]+)/.exec(nodes.storylensPanel.src||'')?.[1];await receive({source:nodes.storylensPanel.contentWindow,origin:'http://127.0.0.1:8765',data:{type:'storylens-host-request',id:'1',nonce:decodeURIComponent(nonce),action,payload},...overrides});}
 return {sequence,messages,codes,send,ready:()=>new Promise(r=>setImmediate(r)),nodes};
}
test('CEP completes JSX before cleanup and sends one successful response afterward',async()=>{
 const b=bridge();await b.ready();await b.send();assert.deepEqual(b.sequence,['native','cleanup','response']);assert.equal(b.messages[0].result.ui_cleanup.ok,true);
});
test('CEP keeps a successful edit when cleanup fails',async()=>{
 const b=bridge('aftereffects',true);await b.ready();await b.send();assert.equal(b.messages[0].result.ok,true);assert.equal(b.messages[0].result.ui_cleanup.ok,false);assert.equal(b.messages[0].error,undefined);
});
test('CEP honors opt-out and rejects other origins',async()=>{
 const b=bridge();await b.ready();await b.send('templateAlign',{collapse_folders:false});assert.deepEqual(b.sequence,['native','response']);
 await b.send('templateAlign',{}, {origin:'https://other.example'});assert.equal(b.messages.length,1);
});
test('the AE-only action never dispatches through Premiere',async()=>{
 const b=bridge('premiere');await b.ready();await b.send('templateAlign');assert.equal(b.sequence.length,0);
});
test('Copy Paste dispatches only its named AE action with the exact payload',async()=>{
 const b=bridge();await b.ready();await b.send('copyPaste',{action:'paste',fit:'fit'});
 const calls=b.codes.filter(code=>code.includes('storylensPanelCopyPaste('));assert.equal(calls.length,1);assert.ok(calls[0].includes('storylensPanelCopyPaste({"action":"paste","fit":"fit"})'));assert.match(calls[0],/copy-paste/);assert.ok(b.codes.filter(code=>!code.includes('storylensPanelCopyPaste(')).every(code=>code.includes('project_id:app.project')));assert.deepEqual(b.sequence,['native','native','response']);
 const pp=bridge('premiere');await pp.ready();await pp.send('copyPaste',{action:'paste'});assert.equal(pp.codes.length,0);
});

test('Import Template uses only the named AE bridge action and rejects other hosts',async()=>{const a=bridge();await a.ready();await a.send('templateImport',{action:'start'});assert.equal(a.codes.length,1);assert.match(a.codes[0],/return storylensPanelTemplateImport\(\{"action":"start"\}\)/);assert.match(a.codes[0],/aftereffects-template-import\.jsx/);const p=bridge('premiere');await p.ready();await p.send('templateImport',{action:'start'});assert.equal(p.codes.length,0)});

// Prepared for owner-run validation; no live folder operation in these fixtures.
test('finished Import Template collapses once per batch after native completion',async()=>{const b=bridge('aftereffects',false,{ok:true,state:'complete',running:false,imported:20,batch_id:'batch1',project_id:'D:/Edits/owner.aep'});await b.ready();await b.send('templateImport',{action:'status'});await b.send('templateImport',{action:'status'});assert.equal(b.sequence.filter(s=>s==='cleanup').length,1);assert.equal(b.messages[0].result.ui_cleanup.ok,true)});
test('running imports never trigger folder cleanup',async()=>{const b=bridge('aftereffects',false,{ok:true,state:'running',running:true,imported:12,batch_id:'batch1',project_id:'D:/Edits/owner.aep'});await b.ready();await b.send('templateImport',{action:'status'});assert.equal(b.sequence.includes('cleanup'),false)});
test('import cleanup failure keeps successful imports and supplies a separate warning',async()=>{const b=bridge('aftereffects',true,{ok:true,state:'complete',running:false,imported:20,batch_id:'batch1',project_id:'D:/Edits/owner.aep'});await b.ready();await b.send('templateImport',{action:'status'});assert.equal(b.messages[0].result.imported,20);assert.equal(b.messages[0].result.ui_cleanup.ok,false);assert.equal(b.messages[0].error,undefined)});

test('every Aliner click loads current native dependencies before invoking the named action',async()=>{const b=bridge();await b.ready();await b.send('templateAlign');assert.match(b.codes[0],/\$\.evalFile/);assert.match(b.codes[0],/template-aliner-model\.js/);assert.match(b.codes[0],/aftereffects-template-aliner\.jsx/);assert.match(b.codes[0],/storylensPanelTemplateAlign/)});

test('resuming the same batch triggers cleanup again after more imports finish',async()=>{const result={ok:true,state:'stopped',running:false,imported:7,processed:7,batch_id:'same',project_id:'unsaved-123'};const b=bridge('aftereffects',false,result);await b.ready();await b.send('templateImport',{action:'status'});result.state='complete';result.imported=20;result.processed=21;await b.send('templateImport',{action:'status'});assert.equal(b.sequence.filter(s=>s==='cleanup').length,2);});
