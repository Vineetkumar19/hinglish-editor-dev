const test=require('node:test'),assert=require('node:assert/strict');
test('browser choice uses an offered source and waits for native confirmation',async()=>{
 const {controller}=require('../hinglish_app/static/broll-editor-choices.js'),calls=[];
 const c=controller({api:async value=>{calls.push(value);if(value.action==='connect')return{name:'Test comp'};if(value.action==='select')return{id:'op',status:'queued'};return{id:'op',status:'confirmed',message:'Same item replaced'};},wait:async()=>{}});
 await c.connect('aftereffects');const result=await c.select({folder:'bank',project:'saved',slot_index:2,source_id:'offered'});
 assert.equal(result.status,'confirmed');assert.equal(calls[1].source_id,'offered');assert.equal(calls[1].host,'aftereffects');assert.equal(calls[2].action,'status');
});
test('CapCut is identified as a new project and does not pretend to swap',async()=>{
 const {controller}=require('../hinglish_app/static/broll-editor-choices.js');
 const c=controller({api:async v=>v.action==='connect'?{name:'New project'}:{manifest:{type:'capcut',task_id:'draft'}},wait:async()=>{}});
 await c.connect('capcut');const result=await c.select({source_id:'choice'});
 assert.equal(result.manifest.type,'capcut');assert.match(result.message,/new editable project/i);
});
