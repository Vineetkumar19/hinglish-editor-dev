const {test}=require('node:test'),assert=require('node:assert/strict');
const {analyzeMedia}=require('../editor_plugins/shared/subject-framing.cjs');
test('subject inspection uses the exact native media path as a separate process argument with no shell',async()=>{
 let call;const file='D:/Photos/owner & family $(never-execute).png';const result=await analyzeMedia('D:/Storylens',file,(exe,args,opts,done)=>{call={exe,args,opts};done(null,JSON.stringify({version:1,width:1200,height:675,faces:[]}),'');});
 assert.equal(call.args.at(-1),file);assert.equal(call.opts.shell,false);assert.equal(call.opts.windowsHide,true);assert.equal(result.version,1);
});
test('analysis error is actionable and preserves original diagnostics separately',async()=>{
 await assert.rejects(analyzeMedia('D:/Storylens','D:/photo.jpg',(_,__,___,done)=>done(null,JSON.stringify({error:'Bad image',details:'decoder diagnostic'}),'')),e=>e.code==='copy_paste_media'&&e.details==='decoder diagnostic');
});
test('relative paths cannot start the subject helper',async()=>{let calls=0;await assert.rejects(analyzeMedia('D:/Storylens','../photo.jpg',()=>calls++));assert.equal(calls,0)});
