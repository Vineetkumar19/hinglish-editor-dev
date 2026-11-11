'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('real CEP dispatch preserves origin and nonce checks and evaluates only validated apply requests',async()=>{
 let receive;const responses=[],scripts=[],nodes={storylensPanel:{contentWindow:{postMessage:r=>responses.push(r)}},shellStatus:{},reconnect:{}};
 const c={URL,Date,Math,JSON,String,Error,require,fetch:async()=>({ok:true}),document:{getElementById:id=>nodes[id],documentElement:{dataset:{host:'aftereffects'}}},window:{HINGLISH_APP_ROOT:process.cwd(),HINGLISH_BRIDGE:'http://127.0.0.1:8765',addEventListener:(kind,fn)=>{if(kind==='message')receive=fn;},__adobe_cep__:{evalScript:(s,cb)=>{scripts.push(s);cb('{"ok":true,"changed":1}');}}}};
 vm.runInNewContext(fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8'),c);await new Promise(r=>setImmediate(r));const nonce=decodeURIComponent(/nonce=([^&]+)/.exec(nodes.storylensPanel.src)[1]),event={source:nodes.storylensPanel.contentWindow,origin:'http://127.0.0.1:8765',data:{type:'storylens-host-request',id:'read',nonce,action:'presetLibrary',payload:{action:'toolkitCatalog'}}};
 await receive(event);assert.equal(responses[0].result.tools.length,96);assert.equal(scripts.length,0);
 await receive({...event,origin:'https://outside.invalid'});await receive({...event,data:{...event.data,nonce:'wrong'}});assert.equal(responses.length,1);
 await receive({...event,data:{...event.data,payload:{action:'toolkitApply',id:'tracking',settings:{duration:2}}}});assert.equal(scripts.length,1);assert.match(scripts[0],/storylensToolkit/);
 await receive({...event,data:{...event.data,payload:{action:'toolkitApply',id:'../unsafe'}}});assert.equal(scripts.length,1);assert.match(responses.at(-1).error,/Choose/);
});
test('all native toolkit modules parse as ES3 and shared errors preserve actionable text',()=>{
 const acorn=require('../tools/motion-engines-runtime/node_modules/acorn');for(const file of fs.readdirSync('editor_plugins/effects-toolkit').filter(f=>/\.(js|jsx)$/.test(f)))acorn.parse(fs.readFileSync('editor_plugins/effects-toolkit/'+file,'utf8'),{ecmaVersion:3,allowReserved:'never'});
 const catalog=JSON.parse(fs.readFileSync('hinglish_app/error_catalog.json'));assert(catalog.some(r=>r.code==='effects_toolkit'));const window={storylensErrorCatalog:catalog};vm.runInNewContext(fs.readFileSync('hinglish_app/static/feedback.js','utf8'),{window,document:{addEventListener(){}}});assert.equal(window.storylensProblem({code:'effects_toolkit',message:'Select timeline keyframes first.'}).message,'Select timeline keyframes first.');
});
test('full generated native request loads 96 tools and creates a builder without missing globals',()=>{
 const f=require('./effects-toolkit-builders-native.test.cjs').fixture(),bridge=require('../editor_plugins/effects-toolkit/bridge.cjs');f.context.File=function(p){this.fsName=p;};f.context.$.evalFile=file=>vm.runInContext(fs.readFileSync(file.fsName,'utf8'),f.context);
 const code=bridge.nativeRequest(process.cwd(),{id:'callout',settings:require('../editor_plugins/effects-toolkit/model.js').validate({id:'callout'}).settings}),r=JSON.parse(vm.runInContext(code,f.context));assert.equal(r.ok,true,r.details||r.error);assert.equal(f.context.SLToolkitModel.catalog().length,96);assert(f.owner._layers.some(l=>l.source?.comment==='Storylens Toolkit:callout:v1'));assert.equal(f.saves,0);
});
