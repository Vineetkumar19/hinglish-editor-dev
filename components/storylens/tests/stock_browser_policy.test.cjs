const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=path.join(__dirname,'../editor_plugins/storylens-stock-chrome');
test('searches are fixed public video searches, never arbitrary commands',()=>{
 const p=require(path.join(base,'stock.js'));
 assert.equal(p.searchUrl('pexels','wifi router','vertical'),'https://www.pexels.com/search/videos/wifi%20router/?orientation=portrait');
 assert.equal(new URL(p.searchUrl('pixabay','bed','horizontal')).hostname,'pixabay.com');
 assert.throws(()=>p.searchUrl('instagram','bed','vertical'));
 assert.throws(()=>p.searchUrl('pexels','x','execute-code'));
 assert.equal(p.videoPage('pexels','https://www.pexels.com/photos/bed-123/'),false);
 assert.equal(p.videoPage('pexels','https://www.pexels.com/video/bed-123/'),true);
 assert.equal(p.media('pixabay','https://cdn.pixabay.com.evil.test/clip.mp4'),false);
 assert.equal(p.pairSender('http://127.0.0.1:8765/stock-browser.html',8765),true);
 assert.equal(p.pairSender('http://127.0.0.1:8765/publisher.html',8765),false);
 assert.equal(p.pairSender('https://evil.test/stock-browser.html',8765),false);
});
test('manifest is a separate opt-in stock-only connector',()=>{
 const m=JSON.parse(fs.readFileSync(path.join(base,'manifest.json')));
 assert.deepEqual(m.permissions.sort(),['alarms','scripting','storage']);
 assert.deepEqual(m.optional_host_permissions.sort(),['https://pixabay.com/*','https://www.pexels.com/*']);
 assert.deepEqual(m.host_permissions,['http://127.0.0.1/*']);
 assert.equal(m.permissions.includes('debugger'),false);
});
test('DOM extraction returns only public videos, not photos or credentials',()=>{
 const p=require(path.join(base,'stock.js'));
 global.location={href:'https://pixabay.com/videos/bed-123/'};
 const video={currentSrc:'https://cdn.pixabay.com/video/123-large.mp4',src:'',videoWidth:720,videoHeight:1280,duration:8,poster:''};
 global.document={title:'Bed',body:{innerText:'Free video Bed'},querySelector:s=>s==='h1'?{textContent:'Bed'}:null,querySelectorAll:s=>s==='video'?[video]:[]};
 const result=p.scrape('pixabay','detail');
 assert.equal(result.result.width,720);assert.equal(result.result.media_url,video.currentSrc);
 assert.deepEqual(Object.keys(result.result).sort(),['duration','height','media_url','page_url','thumbnail','title','width']);
 document.body.innerText='Verify you are human';
 assert.equal(p.scrape('pixabay','detail').state,'needs_verification');
 delete global.document;delete global.location;
});
test('reader ignores another stock video advertised beside the selected video',()=>{
 const p=require(path.join(base,'stock.js'));
 global.location={href:'https://www.pexels.com/video/router-123/'};
 const video=id=>({currentSrc:'https://videos.pexels.com/video-files/'+id+'/clip.mp4',videoWidth:720,videoHeight:1280,duration:8});
 global.document={title:'Router',body:{innerText:'Router free video'},querySelector:()=>null,querySelectorAll:s=>s==='video'?[video(999),video(123)]:[]};
 assert.equal(p.scrape('pexels','detail').result.media_url,video(123).currentSrc);
 delete global.document;delete global.location;
});
test('background player can use its public advertised CDN URL without autoplay',()=>{
 const p=require(path.join(base,'stock.js'));
 global.location={href:'https://www.pexels.com/video/router-123/'};
 const link=id=>({href:'https://www.canva.com/content-partner/?external-id='+id+'&file-url='+encodeURIComponent('https://videos.pexels.com/video-files/'+id+'/clip_1080_1920_30fps.mp4')});
 global.document={title:'Router',body:{innerText:'Router free video'},querySelector:()=>null,querySelectorAll:s=>s==='a[href]'?[link(999),link(123)]:[]};
 const row=p.scrape('pexels','detail').result;
 assert.ok(row);assert.equal(row.media_url,'https://videos.pexels.com/video-files/123/clip_1080_1920_30fps.mp4');
 assert.equal(row.width,1080);assert.equal(row.height,1920);
 delete global.document;delete global.location;
});
test('background Pixabay keeps unknown dimensions for actual local decoder validation',()=>{
 const p=require(path.join(base,'stock.js'));
 global.location={href:'https://pixabay.com/videos/wifi-123/'};
 const url='https://cdn.pixabay.com/video/2026/10/29/123-large.mp4';
 global.document={title:'Wifi',body:{innerText:'Wifi free video'},querySelector:()=>null,querySelectorAll:s=>s==='a[href]'?[{href:'https://www.canva.com/content-partner/?external-id=video%3A123&file-url='+encodeURIComponent(url)}]:[]};
 const row=p.scrape('pixabay','detail').result;assert.ok(row);assert.equal(row.media_url,url);assert.equal(row.width,0);
 delete global.document;delete global.location;
});
test('dispatcher starts both websites without waiting and prevents duplicate provider work',async()=>{
 const p=require(path.join(base,'stock.js')),active=new Set(),started=[];let release;
 const hold=new Promise(resolve=>release=resolve);
 const perform=async task=>{started.push(task.provider);await hold;};
 const claim=async provider=>({provider,id:provider});
 await p.launchReady(['pexels','pixabay'],active,claim,perform,()=>{});
 await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(started,['pexels','pixabay']);assert.equal(active.size,2);
 await p.launchReady(['pexels','pixabay'],active,claim,perform,()=>{});
 assert.equal(started.length,2);release();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(active.size,0);
});
test('parallel dispatch requires both the new server and reloaded extension',()=>{
 const p=require(path.join(base,'stock.js'));
 assert.equal(p.parallelReady({},'0.1.2'),false);
 assert.equal(p.parallelReady({parallel_provider_claims:true},'0.1.1'),false);
 assert.equal(p.parallelReady({parallel_provider_claims:true},'0.1.2'),true);
});
