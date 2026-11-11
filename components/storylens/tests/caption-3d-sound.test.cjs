const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
test('sound effects are enabled by default, with an explicit mute option',()=>{
 const m=require('../editor_plugins/caption-3d/model.cjs');for(const [family,variant] of [['3d1','boost'],['3d2','yellow'],['3d3','corner']]){assert.equal(m.prepare({family,variant}).sound_fx,true);assert.equal(m.prepare({family,variant,sound_fx:false}).sound_fx,false);}
});
test('bundled sound assets are short valid WAV files, not remote dependencies',()=>{
 const c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-3d/sound-data.jsx','utf8'),c);const assets=c.StorylensCaptionAudioData;assert.equal(Object.keys(assets).length,3);
 for(const a of Object.values(assets)){const b=Buffer.from(a.base64,'base64');assert.equal(b.toString('ascii',0,4),'RIFF');assert.equal(b.toString('ascii',8,12),'WAVE');assert(b.length<40000);assert(a.duration<.5);}
});
const mock=require('./helpers/ae-3d-mock.cjs'),bridge=require('../editor_plugins/caption-3d/bridge.cjs');
for(const [family,variant] of [['3d1','boost'],['3d2','red'],['3d3','corner']])test(family+' full bridge creates timed editable audio and safe retry',()=>{
 const r=mock(true,false,{misleadingPosition:true}),context=JSON.parse(r.run(bridge.nativeRequest(process.cwd(),{action:'context'}))),request={action:'insert',family,variant,motion:family==='3d1'?'line-slide':'emerge',context,request_id:'b'.repeat(32)};
 const result=JSON.parse(r.run(bridge.nativeRequest(process.cwd(),request)));assert(result.ok,JSON.stringify(result));assert(r.imports>0);
 const audio=r.created.flatMap(c=>c._layers.filter(l=>l.kind==='audio'));assert(audio.length>=2);assert(audio.every(l=>l.audioEnabled&&l.outPoint>l.inPoint&&l.props['ADBE Audio Group']._children['ADBE Audio Levels'].keys.length===4));
 const count=r.items.length;assert(JSON.parse(r.run(bridge.nativeRequest(process.cwd(),request))).reused);assert.equal(r.items.length,count);
});
test('Sound FX off creates no audio files, imports or audio layers',()=>{
 const r=mock(),context=JSON.parse(r.run(bridge.nativeRequest(process.cwd(),{action:'context'})));const answer=JSON.parse(r.run(bridge.nativeRequest(process.cwd(),{action:'insert',family:'3d3',variant:'corner',sound_fx:false,context,request_id:'d'.repeat(32)})));assert(answer.ok);assert.equal(r.imports,0);assert.equal(Object.keys(r.files).length,0);assert(!r.owner._layers.some(l=>l.kind==='audio'));
});
test('audio import failure rolls back only the new title and retains owner layers',()=>{
 const r=mock(),before=r.items.length,context=JSON.parse(r.run(bridge.nativeRequest(process.cwd(),{action:'context'})));r.context.app.project.importFile=()=>{throw Error('Injected audio import failure');};
 const answer=JSON.parse(r.run(bridge.nativeRequest(process.cwd(),{action:'insert',family:'3d3',variant:'corner',motion:'emerge',context,request_id:'e'.repeat(32)})));assert(answer.error);assert.equal(r.items.length,before);assert.deepEqual(r.owner._layers,[r.camera]);
});
