const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
test('Caption 2 carries measured row offsets, colour and per-frame translation, not generic spacing',()=>{
 const m=require('../editor_plugins/caption-two/model.cjs'),r=m.profile.recipes[0];assert(r.optics);assert(r.optics.top_left.y<0);assert(r.optics.top_left.y>-.4);
 const p=m.prepare({script:'If the Prospects have to meet you',duration:5});assert.deepEqual(p.pages[0].optics,r.optics);assert(p.pages[0].camera_path.length>5);
 assert.notDeepEqual(p.pages[0].words.find(w=>w.colour==='lime').fill_rgb,[225,255,93]);
 assert(p.pages[0].words.filter(w=>w.role==='support').every(w=>w.font==='bold'));
});
test('Reference lower row uses its regular font and camera translation differs between motifs',()=>{
 const m=require('../editor_plugins/caption-two/model.cjs'),p=m.prepare({script:'even if You record you are unsure',duration:5,template_slot:4});assert(p.pages[0].words.filter(w=>w.row==='bottom').every(w=>w.font==='regular'));
 assert(m.profile.recipes[3].camera_path.some(k=>Math.abs(k[3])>5));
});
test('Reference optical offsets are checked against new glyph ink before placement',()=>{
 const c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-two/geometry.jsx','utf8'),c);const p=require('../editor_plugins/caption-two/model.cjs').prepare({script:'If the Prospects have to meet you',duration:5}).pages[0];
 const metrics=p.words.map(w=>({left:0,top:-w.size*.75,width:w.text.length*w.size*.5,height:w.size*.75})),g=c.StorylensCaptionGeometry.layout(p,metrics,720,1280);assert(g.ink_clearance_verified);assert(g.pivot);for(const a of g.ink_boxes)for(const b of g.ink_boxes)if(a.row.startsWith('top')&&b.row==='main'){const x=Math.min(a.bounds[2],b.bounds[2])-Math.max(a.bounds[0],b.bounds[0]);if(x>0)assert(a.bounds[3]<=b.bounds[1]);}
});
test('Native appearance has an explicit configurable soft drop shadow',()=>{
 const src=fs.readFileSync('editor_plugins/caption-two/motion.jsx','utf8');assert.match(src,/ADBE Drop Shadow/);assert.match(src,/camera_path/);assert.match(src,/pivot/);
});
test('Words with descenders share one baseline instead of being bottom-aligned by ink boxes',()=>{
 const c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-two/geometry.jsx','utf8'),c);
 const page={words:[{text:'Your',size:104},{text:'plate',size:104}],rows:[{id:'main',words:[0,1]}],camera:[[0,1]],camera_path:[[0,1,0,0]],optics:{},ink_gap:2.7,word_gap_em:.24,safe_width_fraction:.66};
 const metrics=[{left:0,top:-78,width:230,height:78},{left:0,top:-78,width:230,height:102}],g=c.StorylensCaptionGeometry.layout(page,metrics,720,1280);
 const baselines=g.words.map((w,i)=>w.y-(metrics[i].top+metrics[i].height/2)*w.scale);
 assert(Math.abs(baselines[0]-baselines[1])<1e-8);
});
