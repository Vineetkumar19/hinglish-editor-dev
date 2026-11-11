'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const m=require('../editor_plugins/effects-toolkit/model.js');
test('duration retime shares one origin and preserves relative layer offsets',()=>{
 const r=m.retime([{times:[2,3,6]},{times:[4,5]}],8,false);
 assert.deepEqual(r.map(x=>x.times),[[2,4,10],[6,8]]);
 assert.equal(r[0].speedScale,.5);
});
test('reverse maps global range and reverses derivative direction',()=>{
 const r=m.retime([{times:[2,3,6]},{times:[4,5]}],4,true);
 assert.deepEqual(r.map(x=>x.times),[[6,5,2],[4,3]]);
 assert.equal(r[0].speedScale,-1);
});
test('rejects collapsed and nonfinite key times',()=>{
 assert.throws(()=>m.retime([{times:[1,1]}],2),/distinct/);
 assert.throws(()=>m.retime([{times:[1,Infinity]}],2),/finite/);
});
test('retiming rejects collision with untouched keys before mutation',()=>{
 assert.throws(()=>m.checkCollisions([0,2],[2,4],.001),/unselected/);
 assert.doesNotThrow(()=>m.checkCollisions([0,2],[3,4],.001));
});
test('payload validates allowlisted operations and bounded settings',()=>{
 assert.equal(m.validate({id:'ease',settings:{influence:70,mode:'out'}}).settings.influence,70);
 assert.throws(()=>m.validate({id:'ease',settings:{influence:101}}),/Influence/);
 assert.throws(()=>m.validate({id:'ease',settings:{mode:'execute'}}),/Easing/);
 assert.throws(()=>m.validate({id:'../run'}),/Choose/);
 assert.throws(()=>m.validate({id:'ease',settings:{command:'danger'}}),/Unknown/);
});
test('stagger shifts by the requested step while preserving layer trim',()=>{
 const result=m.stagger([{start:0,inPoint:2,outPoint:4},{start:1,inPoint:3,outPoint:5}],.2,'in');
 assert.equal(result[0],0);assert.ok(Math.abs(result[1]-.2)<1e-10);
});
