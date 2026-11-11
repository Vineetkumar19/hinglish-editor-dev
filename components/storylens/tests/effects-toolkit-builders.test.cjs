'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const b=require('../editor_plugins/effects-toolkit/builders-model.js');
test('chart data is validated before a layout is built',()=>{
 assert.throws(()=>b.make('chart',{data:'A: ten'},1080,1920),/number/);
 assert.throws(()=>b.make('chart',{data:'A: -2'},1080,1920),/nonnegative/);
 const s=b.make('chart',{data:'A: 10\nB: 20'},1080,1920);const bars=s.layers.filter(l=>l.role==='bar');assert.equal(bars.length,2);assert.equal(bars[1].size[0]/bars[0].size[0],2);
});
test('sports fields keep user names and scores and create distinct card structures',()=>{
 const p=b.make('player-stats',{title:'Vineet',data:'Runs: 42\nBalls: 30'},1920,1080);assert(p.layers.some(l=>l.text==='Vineet'));assert(p.layers.some(l=>l.text==='42'));
 const q=b.make('scorecard',{title:'CSK vs RCB',score:'180/4',subtitle:'20 overs'},1920,1080);assert(q.layers.some(l=>l.text==='180/4'));assert.notEqual(JSON.stringify(p.layers.map(l=>l.role)),JSON.stringify(q.layers.map(l=>l.role)));
});
test('every builder produces named editable layers with finite positions and positive duration',()=>{
 for(const id of b.ids){const plan=b.make(id,{},1080,1920);assert(plan.layers.length>0,id);assert(plan.duration>0,id);for(const layer of plan.layers){assert(layer.name,id);assert(layer.position.every(Number.isFinite),id);if(layer.size)assert(layer.size.every(x=>x>0),id);}}
});
test('points tables reject ragged rows and preserve data as supplied',()=>{
 assert.throws(()=>b.make('points-table',{data:'Team,Played,Points\nCSK,4'},1080,1920),/column/);
 const r=b.make('points-table',{data:'Team,Played,Points\nCSK,4,6'},1080,1920);assert(r.layers.some(l=>l.text==='CSK'));assert(r.layers.some(l=>l.text==='6'));
});
test('user content stays data, including quotes, slashes and Unicode',()=>{
 const r=b.make('lower-third',{title:'"Vineet" / क्रिकेट',subtitle:'a\\b'},1080,1920);assert(r.layers.some(l=>l.text==='"Vineet" / क्रिकेट'));assert(r.layers.some(l=>l.text==='a\\b'));
});
