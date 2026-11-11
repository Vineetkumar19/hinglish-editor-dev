const test=require('node:test'),assert=require('node:assert/strict');
test('connected panel executes the offered manifest and acknowledges actual native receipt',async()=>{
 const {deliver}=require('../hinglish_app/static/timed-choice-panel.js'),calls=[];
 const manifest={type:'timed_choice',operation_id:'saved-operation'},receipt={ok:true,item_id:'same-layer'};
 await deliver({id:'saved-operation',manifest},async(action,value)=>{calls.push([action,value]);return receipt;},async value=>{calls.push(['ack',value]);});
 assert.deepEqual(calls,[['import',manifest],['ack',{id:'saved-operation',receipt}]]);
});
test('uncertain native response is reported without fabricating success',async()=>{
 const {deliver}=require('../hinglish_app/static/timed-choice-panel.js'),acks=[];
 await deliver({id:'op',manifest:{type:'timed_choice',operation_id:'op'}},async()=>{throw Error('Disconnected');},async v=>acks.push(v));
 assert.equal(acks[0].id,'op');assert.equal(acks[0].error,'Disconnected');assert.equal(acks[0].receipt,undefined);
 await assert.rejects(deliver({id:'op',manifest:{type:'files'}},async()=>{},async()=>{}),/timed/);
});
