const test=require('node:test');const assert=require('node:assert/strict');const {intake}=require('../hinglish_app/static/publisher-intake.js');
const base={profile:'cricket',path:'D:/Final/Shorts 2.mp4',count:7,sourceMode:'finished',platforms:'youtube',kind:'short',makeShorts:false};
test('exact path and profile go to real prepare API contract without an upload flag',()=>{const p=intake(base);assert.equal(p.video_path,base.path);assert.equal(p.profile,'cricket');assert.deepEqual(p.platforms,['youtube']);assert.equal(p.kind,'short');assert.equal(p.make_shorts,false);assert.equal(p.authorize,undefined)});
test('gaming typed intake asks for one 15-minute highlight and N Shorts from it',()=>{const p=intake({...base,profile:'gaming',sourceMode:'stream',platforms:'paired',count:9});assert.equal(p.route,'prepare');assert.equal(p.source_mode,'stream');assert.equal(p.target_minutes,15);assert.equal(p.shorts_count,9);assert.deepEqual(p.platforms,['youtube','instagram']);assert.equal(p.daily_window,true);assert.equal(p.authorize,undefined)});

test('missing source, General destination, invalid counts and cricket stream refuse before request',()=>{for(const change of [{path:''},{profile:'general'},{count:0},{count:1.5},{sourceMode:'stream'},{path:'two\nfiles.mp4'}])assert.throws(()=>intake({...base,...change}))});
test('finished paired export uses typed draft pipeline and preserves script',()=>{
 const p=intake({...base,platforms:'paired',script:'Exact script from the owner.'});
 assert.equal(p.route,'prepare');assert.deepEqual(p.platforms,['youtube','instagram']);assert.equal(p.script,'Exact script from the owner.');assert.equal(p.daily_window,true);
});
test('gaming accepts official YouTube source links; rejects unrelated URLs',()=>{
 const p=intake({...base,profile:'gaming',sourceMode:'stream',path:'https://youtu.be/Abc12345678'});
 assert.equal(p.route,'prepare');assert.equal(p.source_mode,'stream');assert.throws(()=>intake({...base,profile:'gaming',sourceMode:'stream',path:'https://other.example/video'}));
});
test('channel workspaces never carry Cricket source/script into Gaming and restore on return',()=>{
 const w=require('../hinglish_app/static/publisher-intake.js').workspace();
 const cricket={command:'cricket.mp4',sourceScript:'Exact cricket script',notes:'Cricket notes',sourceMode:'finished',makeShorts:true};
 w.activate('cricket',cricket);
 const gaming=w.activate('gaming',cricket);assert.equal(gaming.command,'');assert.equal(gaming.sourceScript,'');
 const restored=w.activate('cricket',{...gaming,command:'gaming.mp4',sourceScript:'Gaming script'});assert.equal(restored.command,'cricket.mp4');assert.equal(restored.sourceScript,'Exact cricket script');
});
