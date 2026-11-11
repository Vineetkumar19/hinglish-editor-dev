const {test}=require('node:test'),assert=require('node:assert/strict');
const get=()=>require('../editor_plugins/caption-two/model.cjs');
test('Caption 2 preserves split headers, sentence-case main phrase and lowercase support',()=>{
 const p=get().prepare({script:'If the Prospects have to meet you',duration:5});const page=p.pages[0];
 assert.equal(page.words.map(w=>w.source).join(' '),p.script);assert.equal(page.words.filter(w=>w.role==='main').map(w=>w.text).join(' '),'Prospects');
 assert.deepEqual(page.rows.map(r=>r.id),['top_left','main','top_right','bottom']);
 assert(page.words.filter(w=>w.role!=='main').every(w=>w.text===w.text.toLowerCase()));
});
test('Reference pairs capitalize only first letter and reference recipes have distinct camera curves',()=>{
 const m=get(),p=m.prepare({script:'being on Camera Stresses you out',duration:5,template_slot:3}),page=p.pages[0];
 assert.equal(page.words.filter(w=>w.role==='main').map(w=>w.text).join(' '),'Camera stresses');
 assert(m.profile.recipes[0].camera[0][1]>1);assert(m.profile.recipes[1].camera[0][1]<1);
});
test('Different scripts paginate without loss, reserve fixed slots, and never emphasize all-function-word groups',()=>{
 for(const script of ['the and to of hai aur ke ko','extraordinarily complicated communication creates misunderstanding between international audiences every single afternoon','Aaj hum apne naye business ke liye videos banayenge aur customers ko clear ideas denge. '.repeat(6)]){
  const p=get().prepare({script,duration:60});assert.equal(p.pages.flatMap(p=>p.words.map(w=>w.source)).join(' '),script.trim());
  assert(p.pages.every(p=>p.words.length<=7&&p.words.length>0));
  assert(p.pages.every(p=>p.rows.flatMap(r=>r.words).length===p.words.length));
  if(script.startsWith('the and'))assert(p.pages.every(p=>p.words.every(w=>w.colour==='white')));
 }
});
test('Speech onsets and review metadata survive style-specific planning',()=>{
 const script='to understand your value',words=script.split(' ').map((text,i)=>({text,start:i*.7,end:i*.7+.3,...(i===1?{review_reason:'Review'}:{})}));
 const p=get().prepare({script,words,duration:4,template_slot:1});assert.deepEqual(p.pages.flatMap(p=>p.words.map(w=>w.start)),words.map(w=>w.start));
 assert.equal(p.pages[0].words[1].review_reason,'Review');assert(p.pages[0].words.every(w=>!w.gradient));
 assert.equal(p.pages[0].words.at(-1).colour,'lime');assert.equal(p.pages[0].words.at(-2).colour,'white');
});
test('Production bridge creates only editable Caption 2 text, glow and motion controller; retry is idempotent',()=>{
 const h=require('./helpers/ae-3d-mock.cjs')(),bridge=require('../editor_plugins/caption-patterns/bridge.cjs');
 const context=JSON.parse(h.run(bridge.nativeRequest(process.cwd(),{action:'patternContext'},{persist:false})));
 const input={action:'patternInsert',style:'caption_2',script:'If the Prospects have to meet you to understand your value',duration:8,context,request_id:'c'.repeat(32)};
 const r=JSON.parse(h.run(bridge.nativeRequest(process.cwd(),input,{persist:false})));assert(r.ok,JSON.stringify(r));
 const groups=h.owner._layers.filter(l=>l.kind==='av');assert(groups.length>0);assert(groups.every(l=>l.source.parentFolder.parentFolder.name==='Caption 2'));
 const texts=groups.flatMap(l=>l.source._layers.filter(l=>l.kind==='text'&&l.name.startsWith('EDIT ')));assert.equal(texts.length,input.script.split(' ').length);
 assert(texts.every(l=>!l.props['ADBE Effect Parade']?._list.some(e=>e.matchName==='ADBE Glo2')));assert(groups.every(l=>l.source._layers.some(l=>l.name.startsWith('Glow - '))));
 assert(groups.every(l=>l.source._layers.some(l=>l.name==='Caption motion')));assert.equal(h.imports,0);assert.equal(h.saves,0);
 const count=h.items.length;assert(JSON.parse(h.run(bridge.nativeRequest(process.cwd(),input,{persist:false}))).reused);assert.equal(h.items.length,count);
});
test('Caption 2 native failure rolls back only its own items and cannot save the owner project',()=>{
 const h=require('./helpers/ae-3d-mock.cjs')(),bridge=require('../editor_plugins/caption-patterns/bridge.cjs'),before=h.items.length;
 const context=JSON.parse(h.run(bridge.nativeRequest(process.cwd(),{action:'patternContext'},{persist:false})));h.failText();
 const r=JSON.parse(h.run(bridge.nativeRequest(process.cwd(),{action:'patternInsert',style:'caption_2',script:'useful ideas help people',duration:5,context,request_id:'d'.repeat(32)},{persist:false})));
 assert(r.error);assert.equal(h.items.length,before);assert.equal(h.saves,0);assert.equal(h.owner.renderer,'OWNER RENDERER');
});
test('Unknown native style is rejected instead of silently inserting another style',()=>{
 const bridge=require('../editor_plugins/caption-patterns/bridge.cjs');assert.throws(()=>bridge.nativeRequest(process.cwd(),{action:'patternContext',style:'caption_900'},{persist:false}),/style/i);
});
