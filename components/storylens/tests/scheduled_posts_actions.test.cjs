const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {scheduledActionEnabled}=require('../hinglish_app/static/scheduled-posts.js');
test('Delete is available only for eligible failed entries and never while pending',()=>{
 assert.equal(scheduledActionEnabled({bucket:'failed',can_delete:true},'delete'),true);
 for(const post of [{bucket:'scheduled',can_delete:true},{bucket:'failed',can_delete:false},{bucket:'failed'}])assert.equal(scheduledActionEnabled(post,'delete'),false);
 assert.equal(scheduledActionEnabled({bucket:'failed',can_delete:true},'delete',true),false);
});
test('pending local Reels can be cancelled without enabling unsupported text edits',()=>{
 const p={can_edit:false,can_cancel:true};assert.equal(scheduledActionEnabled(p,'cancel'),true);assert.equal(scheduledActionEnabled(p,'save'),false);assert.equal(scheduledActionEnabled(p,'cancel',true),false);
});
test('unsupported or in-progress cancellation stays disabled',()=>{
 assert.equal(scheduledActionEnabled({can_edit:true},'cancel'),false);assert.equal(scheduledActionEnabled({can_cancel:false},'cancel'),false);
});
test('schedule cards override generic button height and keep readable previews',()=>{
 const css=fs.readFileSync('hinglish_app/static/scheduled-posts.css','utf8');assert.match(css,/\.scheduled-dialog \.scheduled-card\{height:auto;min-height:116px/);
 assert.match(css,/grid-template-columns:64px minmax\(0,1fr\)/);
});
