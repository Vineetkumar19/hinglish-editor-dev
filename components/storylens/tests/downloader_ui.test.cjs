const test=require('node:test');const assert=require('node:assert/strict');
const model=require('../hinglish_app/static/downloader-model.js');
test('only YouTube displays four bounded resolution choices',()=>{
  assert.equal(model.platform('https://youtu.be/abc'),'youtube');
  assert.equal(model.platform('https://www.instagram.com/reel/a/'),'instagram');
  assert.equal(model.platform('https://pin.it/a'),'pinterest');
  assert.equal(model.platform('https://youtube.com.evil.org/watch?v=x'),'');
});
test('payload takes current settings and forces best for Instagram',()=>{
  assert.deepEqual(model.request('https://instagram.com/reel/a/','720','both','wav'),{url:'https://instagram.com/reel/a/',quality:'best',mode:'both',audio_format:'wav'});
  assert.equal(model.request('https://youtu.be/a','2160','video','mp3').quality,'2160');
});
test('show actual resolution, not requested cap',()=>{
  const text=model.summary({kind:'video',height:720,width:1280,duration:3.2});
  assert.match(text,/1280 × 720/);assert.doesNotMatch(text,/4K/);
});
test('reports completed transfer separately from editor preparation',()=>{
  const job={source:'source.mp4',progress:87,stage:'Preparing video for your editor'};
  assert.deepEqual(model.progress(job),{downloaded:true,percent:null,stage:job.stage});
  assert.deepEqual(model.progress({...job,stage_progress:35}),{downloaded:true,percent:35,stage:job.stage+' · 35%'});
  assert.equal(model.progress({progress:85,stage:'Downloading media'}).percent,99);
});
test('audio summary never labels an audio file as video',()=>{
  assert.match(model.summary({kind:'audio',channels:2,sample_rate:48000,duration:3}),/48 kHz/);
});
test('Facebook and YouTube clip controls preserve queue destination and timestamps',()=>{
 assert.equal(model.platform('https://fb.watch/test/'),'facebook');
 const request=model.request('https://youtu.be/test','2160','video','wav',{start_time:'2:50',end_time:'3:10',destination:'D:/Downloads',submission_id:'click-1'});
 assert.equal(request.start_time,'2:50');assert.equal(request.end_time,'3:10');assert.equal(request.destination,'D:/Downloads');
});
