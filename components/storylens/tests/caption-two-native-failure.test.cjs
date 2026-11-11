const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm'),model=require('../editor_plugins/caption-two/model.cjs');
test('New-script headers cannot intersect visible keyword glyphs',()=>{
 const page=model.prepare({script:'toh flat nahi mila, pg le liya.',duration:5}).pages[0];const c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-two/geometry.jsx','utf8'),c);
 const metrics=page.words.map(w=>({left:0,top:-w.size*.76,width:w.text.length*w.size*.48,height:w.size*.92})),g=c.StorylensCaptionGeometry.layout(page,metrics,720,1280);
 const words=page.words.map((w,i)=>({...w,bounds:g.words[i].bounds})),head=words.filter(w=>w.row.startsWith('top')),main=words.filter(w=>w.row==='main');
 for(const a of head)for(const b of main){const overlap=Math.min(a.bounds[2],b.bounds[2])-Math.max(a.bounds[0],b.bounds[0]);if(overlap>0)assert(a.bounds[3]<=b.bounds[1]||g.ink_clearance_verified,'Rows must be separated or glyph-clearance verified');}
});
test('Native glow never runs a brightness effect on the foreground text',()=>{
 const src=fs.readFileSync('editor_plugins/caption-two/motion.jsx','utf8');assert(!/addProperty\('ADBE Glo2'\)/.test(src));assert.match(src,/duplicate\(/);assert.match(src,/moveAfter\(/);
});
test('Native colour readback is checked before reporting successful insertion',()=>{
 const src=fs.readFileSync('editor_plugins/caption-patterns/engine.jsx','utf8');assert.match(src,/verifyFill/);
});
test('Actual failed PG wording has no cross-row glyph collisions at native geometry stage',()=>{
 const saved=JSON.parse(fs.readFileSync('output/captions/ae-patterns/a0b1f1010c6eed6fd010be853c7411fb/plan.json','utf8')),c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-two/geometry.jsx','utf8'),c);
 const words=saved.plan.pages.flatMap(p=>p.words).map(w=>({text:w.source,start:w.start,end:w.end})),plan=model.prepare({script:words.map(w=>w.text).join(' '),words,duration:saved.plan.duration});
 assert.equal(plan.pages.flatMap(p=>p.words).length,words.length);
 for(const page of plan.pages){const metrics=page.words.map(w=>({left:0,top:-w.size*.76,width:w.text.length*w.size*.48,height:w.size*.92})),g=c.StorylensCaptionGeometry.layout(page,metrics,1080,1920);
  for(const a of g.ink_boxes)for(const b of g.ink_boxes)if(a.row.startsWith('top')&&b.row==='main'||a.row==='main'&&b.row==='bottom'){const overlap=Math.min(a.bounds[2],b.bounds[2])-Math.max(a.bounds[0],b.bounds[0]);if(overlap>0)assert(a.bounds[3]<=b.bounds[1]+.01);}
  assert(g.fit<=.70);assert(page.camera_path.every(k=>k[2]===0&&k[3]===0));
 }
});
test('Native foreground retains lime and refuses a colour-corrupting text setter',()=>{
 const mock=require('./helpers/ae-3d-mock.cjs'),bridge=require('../editor_plugins/caption-patterns/bridge.cjs');
 for(const corrupt of [false,true]){const h=mock(),before=h.items.length,add=h.context.app.project.items.addComp;
  if(corrupt)h.context.app.project.items.addComp=(...args)=>{const c=add(...args),text=c.layers.addText;c.layers.addText=t=>{const l=text(t),p=l.property('ADBE Text Properties').property('ADBE Text Document'),set=p.setValue;p.setValue=v=>{v.fillColor=[1,1,1];set.call(p,v)};return l};return c;};
  const context=JSON.parse(h.run(bridge.nativeRequest(process.cwd(),{action:'patternContext'},{persist:false}))),r=JSON.parse(h.run(bridge.nativeRequest(process.cwd(),{action:'patternInsert',style:'caption_2',script:'If the Prospects have to meet you',duration:5,context,request_id:'f'.repeat(32)},{persist:false})));
  if(corrupt){assert(r.error);assert.match(r.details,/fill colour/);assert.equal(h.items.length,before);}
  else{assert(r.ok,JSON.stringify(r));const doc=h.created.flatMap(c=>c._layers).find(l=>l.name==='EDIT 3 - Prospects').property('ADBE Text Properties').property('ADBE Text Document').value;assert(doc.fillColor[1]>.9&&doc.fillColor[2]<.5);}
 }
});
test('A late placement failure removes the new glow/controller items and empty generation folders',()=>{
 const h=require('./helpers/ae-3d-mock.cjs')(),bridge=require('../editor_plugins/caption-patterns/bridge.cjs'),before=h.items.length;
 const context=JSON.parse(h.run(bridge.nativeRequest(process.cwd(),{action:'patternContext'},{persist:false})));h.owner.layers.add=()=>{throw Error('placement stopped')};
 const r=JSON.parse(h.run(bridge.nativeRequest(process.cwd(),{action:'patternInsert',style:'caption_2',script:'If the Prospects have to meet you',duration:5,context,request_id:'b'.repeat(32)},{persist:false})));
 assert(r.error);assert.equal(h.items.length,before);assert.equal(h.saves,0);
});
test('A short keyword below a wide header cannot swing the caption sideways during zoom',()=>{
 const page=model.prepare({script:'toh flat nahi mila, pg le liya.',duration:5}).pages[0],c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-two/geometry.jsx','utf8'),c);
 const metrics=page.words.map(w=>({left:0,top:-w.size*.76,width:w.text.length*w.size*.48,height:w.size*.92})),g=c.StorylensCaptionGeometry.layout(page,metrics,720,1280),zoom=1.36;
 const left=Math.min(...g.words.map(w=>w.bounds[0])),right=Math.max(...g.words.map(w=>w.bounds[2])),movingCentre=g.pivot[0]+((left+right)/2-g.pivot[0])*zoom;
 assert(Math.abs(movingCentre-360)<.01);
});
