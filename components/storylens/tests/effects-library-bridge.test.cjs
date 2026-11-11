const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
async function fixture(host='aftereffects',fault=false){
 const events={},sent=[],codes=[],prepared=[],frame={contentWindow:{postMessage:m=>sent.push(m)}},elements={storylensPanel:frame,shellStatus:{},reconnect:{}};
 const root=process.cwd(),c={URL,Date,Math,JSON,Promise,String,Error,fetch:async()=>({ok:true}),document:{getElementById:id=>elements[id],documentElement:{dataset:{host}}},require:name=>{if(name==='path')return path;if(name.endsWith('effects-library\\bridge.cjs')||name.endsWith('effects-library/bridge.cjs'))return {prepare(payload){prepared.push(payload);if(fault)throw new TypeError('PRIVATE_PARSER_DIAGNOSTIC');return payload.action==='catalog'?{result:{ok:true,packs:[]}}:{payload:{action:'insert',pack:{id:'resolved'},request_id:'click-1'}};}};throw Error(name);},window:{HINGLISH_APP_ROOT:root,addEventListener:(type,fn)=>events[type]=fn,__adobe_cep__:{evalScript:(code,cb)=>{codes.push(code);cb(JSON.stringify({ok:true,slots:1}));}}}};
 vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8'),c);await new Promise(r=>setImmediate(r));const nonce=decodeURIComponent(/nonce=([^&]+)/.exec(frame.src)[1]);
 const send=(payload,change={})=>events.message({source:frame.contentWindow,origin:'http://127.0.0.1:8765',data:{type:'storylens-host-request',nonce,id:'1',action:'effectsLibrary',payload},...change});return {send,sent,codes,prepared,frame};
}
test('real CEP shell catalog is filesystem-only; insertion hot-loads native modules in dependency order',async()=>{
 const h=await fixture();await h.send({action:'catalog'});assert.equal(h.codes.length,0);assert(h.sent.at(-1).result.ok);await h.send({action:'insert'});assert.equal(h.codes.length,1);const code=h.codes[0];assert(code.indexOf('copy-paste')<code.indexOf('effects-library'));assert(code.includes('storylensPanelEffects'));assert(h.sent.at(-1).result.ok);
});
test('a foreign origin/frame or Premiere cannot acquire Effects filesystem/native capability',async()=>{
 for(const host of ['aftereffects','premiere']){const h=await fixture(host);await h.send({action:'catalog'},{origin:'https://example.com'});await h.send({action:'catalog'},{source:{}});if(host==='premiere')await h.send({action:'catalog'});assert.equal(h.prepared.length,0);assert.equal(h.codes.length,0);assert.equal(h.sent.length,0);}
});
test('final review: an unexpected filesystem/parser exception is hidden behind a useful shared error',async()=>{
 const h=await fixture('aftereffects',true);await h.send({action:'catalog'});const r=h.sent.at(-1);assert.equal(r.code,'effects_library');assert.doesNotMatch(r.error,/TypeError|PRIVATE_PARSER/);assert.match(r.error,/Check|refresh/);assert.match(r.details,/PRIVATE_PARSER/);assert.equal(h.codes.length,0);
});
