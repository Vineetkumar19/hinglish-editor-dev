const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs');
const {fixture}=require('./quick-motion-ui.test.cjs');
async function group(name){const f=fixture();await f.view.init();await f.nodes.presetCategoryStrip.children[0].onclick();await f.nodes.presetPacks.children.find(x=>x.textContent===name).onclick();return f;}
test('repair: Word and Words have separate text samples and apply with the chosen scope',async()=>{
 const f=await group('Text Animations');assert.equal(f.el('quickMotionWords').attributes['aria-pressed'],'true');await f.el('quickMotionWord').onclick();assert.equal(f.el('quickMotionWord').attributes['aria-pressed'],'true');let card=f.nodes.presetScenes.children.find(x=>x._recipe.id==='text-fade');assert.equal(card._glyphs.length,1);assert.equal(card._glyphs[0].textContent,'WINNING');await card._add.onclick();assert.equal(f.calls.at(-1).text_scope,'word');await f.el('quickMotionWords').onclick();card=f.nodes.presetScenes.children.find(x=>x._recipe.id==='text-fade');assert.equal(card._glyphs.length,3);await card._add.onclick();assert.equal(f.calls.at(-1).text_scope,'words');
});
test('repair: object is a large geometric sample inside a centered full-card stage, not a tiny bullet',async()=>{
 const f=await group('Element Motion'),card=f.nodes.presetScenes.children[0];assert.equal(card._stage.className,'quick-motion-stage');assert.equal(card._sample.children[0],card._stage);assert.equal(card._glyphs[0].className,'quick-motion-glyph quick-motion-object');assert.equal(card._glyphs[0].textContent,'');const css=fs.readFileSync('hinglish_app/static/preset-library.css','utf8');assert.match(css,/\.quick-motion-sample\{[^}]*width:100%/);assert.match(css,/\.quick-motion-stage\{[^}]*inset:0[^}]*align-items:center[^}]*justify-content:center/);assert.match(css,/\.quick-motion-object\{[^}]*width:40px[^}]*height:40px/);
});
test('repair: text previews fill the card with black and use smaller centered sample lettering',async()=>{
 const f=await group('Text Animations'),card=f.nodes.presetScenes.children[0];assert.equal(card._stage.className,'quick-motion-stage');const css=fs.readFileSync('hinglish_app/static/preset-library.css','utf8');assert.match(css,/\.quick-motion-sample\{[^}]*background:#000[^}]*font:600 11px/);assert.match(css,/\.quick-motion-line\{[^}]*justify-content:center/);
});
test('repair: plain-text drag fallback carries an allowlisted recipe and chosen Word scope',async()=>{
 const f=await group('Text Animations');await f.el('quickMotionWord').onclick();const card=f.nodes.presetScenes.children[0],data={};card._add.ondragstart({dataTransfer:{setData:(k,v)=>data[k]=v}});await f.el('quickMotionDrop').ondrop({preventDefault(){},dataTransfer:{getData:k=>k==='text/plain'?data[k]:''}});assert.equal(f.calls.at(-1).action,'applyMotion');assert.equal(f.calls.at(-1).text_scope,'word');
});
