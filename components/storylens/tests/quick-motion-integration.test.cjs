const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),vm=require('vm');
test('CEP motion catalog never evaluates AE; named apply dispatches once; origin, nonce and bad IDs are rejected',async()=>{
 let receive;const responses=[],scripts=[],nodes={storylensPanel:{contentWindow:{postMessage:r=>responses.push(r)}},shellStatus:{},reconnect:{}};
 const c={URL,Date,Math,JSON,String,Error,require,fetch:async()=>({ok:true}),document:{getElementById:id=>nodes[id],documentElement:{dataset:{host:'aftereffects'}}},window:{HINGLISH_APP_ROOT:process.cwd(),HINGLISH_BRIDGE:'http://127.0.0.1:8765',addEventListener:(kind,fn)=>{if(kind==='message')receive=fn;},__adobe_cep__:{evalScript:(s,cb)=>{scripts.push(s);cb('{"ok":true,"layers":1}');}}}};
 vm.runInNewContext(fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8'),c);await new Promise(r=>setImmediate(r));const nonce=decodeURIComponent(/nonce=([^&]+)/.exec(nodes.storylensPanel.src)[1]),event={source:nodes.storylensPanel.contentWindow,origin:'http://127.0.0.1:8765',data:{type:'storylens-host-request',id:'read',nonce,action:'presetLibrary',payload:{action:'motionCatalog'}}};
 await receive(event);assert.equal(responses[0].result.presets.length,18);assert.equal(scripts.length,0);
 await receive({...event,origin:'https://outside.invalid'});await receive({...event,data:{...event.data,nonce:'wrong'}});assert.equal(responses.length,1);
 await receive({...event,data:{...event.data,payload:{action:'applyMotion',id:'text-up',duration:2,blur:true,exit:true}}});assert.equal(scripts.length,1);assert.match(scripts[0],/storylensQuickMotion/);assert.doesNotMatch(scripts[0],/storylensPanelPreset/);
 await receive({...event,data:{...event.data,payload:{action:'applyMotion',id:'../unsafe',duration:2}}});assert.equal(scripts.length,1);assert.match(responses.at(-1).error,/Choose a motion/);
});
test('native serialization is ASCII ES3 and safely treats unusual workspace names as data',()=>{
 const b=require('../editor_plugins/quick-motion/bridge.cjs'),acorn=require('../tools/motion-engines-runtime/node_modules/acorn');const source=b.nativeRequest('D:/हिन्दी " directory/\u2028',{id:'text-up',duration:2});assert(!/[^\x00-\x7f]/.test(source));acorn.parse(source,{ecmaVersion:3,allowReserved:'never'});let count=0;const result=vm.runInNewContext(source,{$:{evalFile:()=>count++},File:function(p){this.path=p;},storylensQuickMotion:p=>p});assert.equal(count,2);assert.equal(result.id,'text-up');
});
test('shared error catalog supplies a motion-specific fallback while native actionable causes stay intact',()=>{
 const catalog=JSON.parse(fs.readFileSync('hinglish_app/error_catalog.json','utf8'));assert(catalog.some(r=>r.code==='quick_motion'));const window={storylensErrorCatalog:catalog};vm.runInNewContext(fs.readFileSync('hinglish_app/static/feedback.js','utf8'),{window,document:{addEventListener(){}}});const p=window.storylensProblem({code:'quick_motion',message:'Select your text layer first.',details:'locked layer'});assert.equal(p.message,'Select your text layer first.');assert.equal(p.details,'locked layer');
});
