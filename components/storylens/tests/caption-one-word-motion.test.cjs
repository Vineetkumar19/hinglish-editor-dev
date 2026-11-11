const fs=require('node:fs'),assert=require('node:assert/strict'),{test}=require('node:test'),mock=require('./helpers/ae-3d-mock.cjs'),model=require('../editor_plugins/caption-patterns/model.cjs');
test('native reusable entrance replaces stale keys and moves every word before settling in its fixed slot',()=>{
 const h=mock();h.run(fs.readFileSync('editor_plugins/caption-patterns/engine.jsx','utf8'));
 assert.equal(typeof h.context.StorylensCaptionPatterns.animate,'function');
 const page=model.prepare({script:'Anyone can run ads for big companies',duration:4}).pages[0];
 for(const w of page.words){const l=h.owner.layers.addText(w.text),pos=l.property('ADBE Transform Group').property('ADBE Position'),opacity=l.property('ADBE Transform Group').property('ADBE Opacity'),eased=[];for(const name of ['ADBE Position','ADBE Opacity','ADBE Rotate Z']){const p=l.property('ADBE Transform Group').property(name),native=p.setTemporalEaseAtKey;p.setTemporalEaseAtKey=(key,a,b)=>{native(key,a,b);eased.push({name,key,a,b});};}pos.setValueAtTime(9,[999,999]);opacity.setValueAtTime(9,0);h.context.StorylensCaptionPatterns.animate(l,w,page,{x:340,y:620},1);assert.equal(pos.keys.length,2,'Use native eased endpoints rather than a sampled linear curve');assert(!pos.keys.some(k=>k.t===9));assert.deepEqual(Array.from(pos.keys.at(-1).v),[340,620]);assert.notDeepEqual(Array.from(pos.keys[0].v),[340,620]);assert(opacity.keys.at(-1).t-opacity.keys[0].t>=.12);assert(pos.keys.at(-1).t-pos.keys[0].t>=.23);assert.equal(eased.length,6);if(w.font==='bold'){const r=l.property('ADBE Transform Group').property('ADBE Rotate Z');assert.equal(r.keys[0].v,0);assert.equal(r.keys.at(-1).v,0);assert.equal(pos.keys[0].v[0],pos.keys.at(-1).v[0]);}}
});
test('native spatial easing follows AE reported tangent dimensions instead of assuming two coordinates',()=>{
 const h=mock();h.run(fs.readFileSync('editor_plugins/caption-patterns/engine.jsx','utf8'));
 const page=model.prepare({script:'Anyone can run ads',duration:3}).pages[0],l=h.owner.layers.addText('Anyone'),pos=l.property('ADBE Transform Group').property('ADBE Position'),set=pos.setValueAtTime;
 pos.setValueAtTime=(t,v)=>set.call(pos,t,[v[0],v[1],0]);pos.isSpatial=true;let tangents=0;
 pos.setSpatialTangentsAtKey=(key,a,b)=>{assert.equal(a.length,3);assert.equal(b.length,3);tangents++;};
 h.context.StorylensCaptionPatterns.animate(l,page.words[0],page,{x:100,y:100},1);assert.equal(tangents,2);
});
