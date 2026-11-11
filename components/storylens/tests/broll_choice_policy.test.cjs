const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
test('browser request caps match Instagram five and YouTube two',()=>{
 const context={window:{}};vm.runInNewContext(fs.readFileSync('hinglish_app/static/broll-format.js','utf8'),context);
 const limit=context.window.storylensBrollFormat.limit;
 assert.equal(limit('vertical',6),5);assert.equal(limit('horizontal',5),2);
 assert.equal(limit('vertical',''),5);assert.equal(limit('horizontal',''),2);assert.equal(limit('horizontal',1),1);
});
