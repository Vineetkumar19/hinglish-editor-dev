'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const uiPath = path.join(__dirname, '..', 'hinglish_app', 'phone_static');
const memory = () => {
  const data = new Map();
  return {data, getItem: k => data.get(k) || null, setItem: (k, v) => data.set(k, String(v)), removeItem: k => data.delete(k)};
};
const snapshot = (id = 'chat-1', extra = {}) => ({id, title:'Phone chat', status:'idle', stage:'Ready', messages:[], attachments:[], files:[], ...extra});
const paired = {paired:true, csrf:'private-csrf', connected:true, assistant:true, chats:[]};
function harness(respond, extra = {}) {
  const calls = [];
  const api = async (route, options = {}) => {
    calls.push({route, ...options});
    return respond ? respond(route, options, calls.length) : (route === '/phone/state' ? paired : snapshot());
  };
  const app = require(path.join(uiPath, 'phone.js')).createApp({api, storage:memory(), pendingStorage:memory(), requestId:()=>'fixed-request', ...extra});
  return {app, calls};
}
if (!process.argv.includes('--fixture')) {
  const ui = require(path.join(uiPath, 'phone.js'));
  test('files and compact accessible shell have no external dependencies or engine routes', () => {
    const html = fs.readFileSync(path.join(uiPath, 'index.html'), 'utf8');
    const js = fs.readFileSync(path.join(uiPath, 'phone.js'), 'utf8');
    const css = fs.readFileSync(path.join(uiPath, 'phone.css'), 'utf8');
    assert.match(html, /name="viewport"/);
    assert.match(html, /type="password"/);
    assert.match(html, /id="message"/);
    assert.match(html, /Technical details/);
    assert.doesNotMatch(html + js, /https?:\/\/|\/api\/|innerHTML|insertAdjacentHTML|getUserMedia/);
    assert.match(css, /safe-area-inset-bottom/);
    assert.match(css, /prefers-reduced-motion/);
  });
  test('pair fragment is removed before any request and query credentials are never used', () => {
    const order = [];
    const code = ui.consumePairFragment({hash:'#pair=123456', pathname:'/phone/', search:'?unrelated=1'}, {replaceState:(_,__,url)=>order.push(url)});
    assert.equal(code, '123456');
    assert.deepEqual(order, ['/phone/?unrelated=1']);
    assert.equal(ui.consumePairFragment({hash:'', pathname:'/phone/', search:'?pair=secret'}, {replaceState(){}}), '');
  });
  test('file links require exact same-origin opaque file endpoint; reject encoded traversal and active content', () => {
    const base = 'http:' + '//phone.test';
    assert.equal(ui.safeFileUrl('/phone/files/abc-123?download=1', base), '/phone/files/abc-123?download=1');
    assert.equal(ui.safeFileUrl(base + '/phone/files/id', base), '/phone/files/id');
    for (const input of ['javascript:alert(1)', '//other.test/phone/files/id', '/api/file', '/phone/files/../state', '/phone/files/%2e%2e', '/phone/files/%252e%252e', '/phone/files/a/b', '/phone/files/a%2fb', '/phone/files/abc#x', '/phone/files/']) assert.equal(ui.safeFileUrl(input, base), null, input);
    assert.equal(ui.previewKind({mime:'text/html', name:'unsafe.html'}), 'download');
    assert.equal(ui.previewKind({mime:'image/svg+xml', name:'unsafe.svg'}), 'download');
    assert.equal(ui.previewKind({mime:'video/mp4', name:'actual.mp4'}), 'video');
    assert.equal(ui.previewKind({mime:'audio/wav', name:'actual.wav'}), 'audio');
    assert.equal(ui.previewKind({mime:'image/jpeg', name:'actual.jpg'}), 'image');
    assert.equal(ui.previewKind({mime:'application/pdf', name:'actual.pdf'}), 'download');
  });
  test('request IDs work on private HTTP origins without secure-context randomUUID', () => {
    const id=ui.makeRequestId({getRandomValues(bytes){bytes.fill(171);return bytes;}});
    assert.match(id,/^[a-f0-9]{32}$/);
    assert.throws(()=>ui.makeRequestId({}),/secure|browser|random/i);
  });
  test('attachment limits reject unsupported files and accept bounded real assistant inputs', () => {
    assert.equal(ui.validateFile({name:'clip.MP4', size:256*1024*1024}), '');
    assert.match(ui.validateFile({name:'clip.mp4', size:256*1024*1024+1}), /256/);
    for (const name of ['payload.svg', 'file.html', 'a.pdf', 'a.zip', 'a.exe', 'a.mp4.exe']) assert.ok(ui.validateFile({name, size:1}), name);
    assert.ok(ui.validateFile({name:'a.txt', size:0}));
  });
  test('progress is measured only and malformed/unknown percentages stay indeterminate', () => {
    assert.deepEqual(ui.progressInfo({completed:2,total:5}), {completed:2,total:5,remaining:3});
    assert.deepEqual(ui.progressInfo({current:3,total:8}), {current:3,total:8}, 'A reported current unit is not proof of completed work');
    assert.deepEqual(ui.progressInfo({completed:0,total:2}), {completed:0,total:2,remaining:2});
    for (const value of [{percent:65}, {completed:9,total:3}, {completed:true,total:5}, {completed:0,total:0}, {current:'2',total:5}, {stage:'Section 3/8'}]) assert.equal(ui.progressInfo(value), null);
  });
  test('diagnostics remove tokens and local paths rather than expose engine internals', () => {
    const clean = ui.redact('failed C:\\private\\media.mp4 token=secret csrf=private-csrf /home/user/file Bearer abc123');
    assert.doesNotMatch(clean, /secret|private-csrf|abc123|C:\\private|\/home\/user/);
    assert.match(ui.friendlyError({status:401}).message, /pair/i);
    assert.doesNotMatch(ui.friendlyError({message:'TypeError: raw stack'}).message, /TypeError/);
  });
  test('client confines traffic, sends cookies and CSRF, and handles 401/non-JSON safely', async () => {
    const calls=[];
    const client=ui.createClient(async (route, options)=>{ calls.push({route,...options}); return {ok:true,status:200,json:async()=>({ok:true})}; });
    await client('/phone/pair',{method:'POST',body:{code:'123'}});
    await client('/phone/chats',{method:'POST',csrf:'s',body:{request_id:'r'}});
    assert.equal(calls[0].credentials,'same-origin');
    assert.equal(calls[0].headers['X-Phone-CSRF'],undefined);
    assert.equal(calls[1].headers['X-Phone-CSRF'],'s');
    assert.deepEqual(JSON.parse(calls[1].body),{request_id:'r'});
    await assert.rejects(()=>client('/api/assistant'),/phone/i);
    await assert.rejects(()=>client('/phone/chats',{method:'POST',body:{}}),/pair/i);
    await assert.rejects(()=>ui.createClient(async()=>({ok:false,status:401,json:async()=>{throw Error('html');}}))('/phone/state'), error=>error.status===401);
  });
  test('unauthorized state opens pairing without saving code or csrf', async () => {
    const storage=memory(); const pendingStorage=memory();
    const {app}=harness(async route=>{if(route==='/phone/state')throw Object.assign(Error(),{status:401}); return {paired:true,csrf:'s'};},{storage,pendingStorage});
    await app.init();
    assert.equal(app.state.paired,false);
    assert.equal(app.state.chat,null);
    assert.equal(app.state.network,true, 'An authentication response means the laptop is reachable');
    assert.equal(JSON.stringify([...storage.data]),'[]');
    assert.equal(JSON.stringify([...pendingStorage.data]),'[]');
  });
  test('fresh paired state does not fetch an undefined chat or trust non-string IDs', async () => {
    const {app,calls}=harness();await app.init();
    assert.equal(app.state.chat,null);assert.equal(calls.length,1);
    await app.selectChat(undefined);await app.selectChat(true);assert.equal(calls.length,1);
  });
  test('restores chat and draft without automatically sending after refresh', async () => {
    const storage=memory(); storage.setItem('phone.chat','chat-1'); storage.setItem('phone.draft.chat-1','Exact Hinglish words\nLine 2');
    const {app,calls}=harness(undefined,{storage}); await app.init();
    assert.equal(app.state.chat.id,'chat-1');
    assert.equal(app.state.draft,'Exact Hinglish words\nLine 2');
    assert.ok(calls.every(call=>!call.method || call.method==='GET'));
  });
  test('send preserves exact message/profile/attachment identity and clears only submitted draft', async () => {
    const {app,calls}=harness(async route=>route==='/phone/state'?paired:route.includes('/attachments?')?{id:'attachment-1',name:'original.jpg',size:10,kind:'image'}:snapshot()); await app.init(); await app.selectChat('chat-1');
    app.setDraft('  Exact words\nHinglish hai  '); app.setProfile('cricket');
    await app.upload({name:'original.jpg',size:10});
    await app.send();
    const call=calls.find(c=>c.route.endsWith('/messages'));
    assert.deepEqual(call.body,{request_id:'fixed-request',message:'  Exact words\nHinglish hai  ',attachments:['attachment-1'],profile:'cricket'});
    assert.equal(app.state.draft,''); assert.equal(app.state.selected.length,0);
    assert.equal(call.csrf,'private-csrf');
  });
  test('ambiguous send never replays on polls and explicit retry keeps original request ID and text', async () => {
    let failed=false;
    const {app,calls}=harness(async (route, options)=>{
      if(route==='/phone/state')return paired;
      if(route.endsWith('/messages')&&!failed){failed=true;throw Error('Network lost');}
      return snapshot();
    });
    await app.init();await app.selectChat('chat-1');app.setDraft('Original exact text');await app.send();
    assert.ok(app.state.pending); assert.match(app.state.error.message,/check|progress/i);
    await app.refresh();await app.refresh();
    assert.equal(calls.filter(c=>c.route.endsWith('/messages')).length,1);
    app.setDraft('Next draft');await app.retry();
    const posts=calls.filter(c=>c.route.endsWith('/messages'));
    assert.equal(posts.length,2);assert.deepEqual(posts[0].body,posts[1].body);
    assert.equal(app.state.draft,'Next draft');
  });
  test('same request survives same-tab refresh without persisting authentication secrets', async () => {
    const storage=memory();const pendingStorage=memory();
    const {app}=harness(async route=>{if(route==='/phone/state')return paired;if(route.endsWith('/messages'))throw Error('lost');return snapshot();},{storage,pendingStorage});
    await app.init();await app.selectChat('chat-1');app.setDraft('Saved draft');await app.send();
    assert.doesNotMatch(JSON.stringify([...storage.data,...pendingStorage.data]),/private-csrf/);
    const next=harness(undefined,{storage,pendingStorage});await next.app.init();
    assert.equal(next.app.state.pending.request_id,'fixed-request');
    assert.ok(next.calls.every(c=>!c.method||c.method==='GET'));
  });
  test('polling and stale chat responses cannot replace the current draft or selected chat', async () => {
    let release;
    const {app}=harness(async route=>{
      if(route==='/phone/state')return paired;
      if(route.endsWith('/slow'))return new Promise(resolve=>{release=resolve;});
      return snapshot(route.split('/').pop());
    });
    await app.init();const first=app.selectChat('slow');await app.selectChat('latest');app.setDraft('Do not replace');
    release(snapshot('slow'));await first;await app.refresh();
    assert.equal(app.state.chat.id,'latest');assert.equal(app.state.draft,'Do not replace');
  });
  test('new chat and file upload use fixed request IDs; stop is after-current-step only', async () => {
    const {app,calls}=harness(async route=>route==='/phone/state'?paired:route.includes('/attachments?')?{id:'upload-1',name:'clip.mp4',size:12,kind:'video'}:snapshot('chat-1',{status:'running'}));
    await app.init();await app.newChat();await app.upload({name:'clip.mp4',size:12});await app.stop();
    assert.deepEqual(calls.find(c=>c.route==='/phone/chats').body,{request_id:'fixed-request'});
    const upload=calls.find(c=>c.route.includes('/attachments?'));
    assert.match(upload.route,/request_id=fixed-request/);assert.equal(upload.binary,true);assert.equal(upload.body.name,'clip.mp4');
    assert.deepEqual(calls.find(c=>c.route.endsWith('/stop')).body,{});
    assert.equal(calls.filter(c=>c.route.endsWith('/stop')).length,1);
  });
  test('uploads reject invalid input before a request and remain selectable after a successful GET', async () => {
    const {app,calls}=harness(async route=>route==='/phone/state'?paired:route.includes('/attachments?')?{id:'a1',name:'image.png',size:4,kind:'image'}:snapshot());
    await app.init();await app.selectChat('chat-1');await app.upload({name:'evil.exe',size:4});
    assert.equal(calls.filter(c=>c.route.includes('/attachments?')).length,0);
    await app.upload({name:'image.png',size:4});await app.refresh();assert.equal(app.state.selected[0].id,'a1');
    app.removeAttachment('a1');assert.equal(app.state.selected.length,0);
  });
  test('disconnected backend blocks new work and unauthorized poll locks private results', async () => {
    let connected=false; let unauthorized=false;
    const {app,calls}=harness(async route=>{
      if(unauthorized)throw Object.assign(Error(),{status:401});
      return route==='/phone/state'?{...paired,connected}:snapshot();
    });
    await app.init();await app.newChat();assert.equal(calls.filter(c=>c.method==='POST').length,0);
    connected=true;await app.refresh();await app.selectChat('chat-1');unauthorized=true;await app.refresh();
    assert.equal(app.state.paired,false);assert.equal(app.state.chat,null);assert.equal(app.state.csrf,'');
  });
  test('an unreadable successful POST response remains ambiguous and keeps the same retry identity', async () => {
    const client=ui.createClient(async()=>({ok:true,status:200,json:async()=>{throw Error('partial JSON');}}));
    const {app}=harness(async(route,options)=>route==='/phone/state'?paired:options.method==='POST'?client(route,options):snapshot());
    await app.init();await app.selectChat('chat-1');app.setDraft('Do not duplicate');await app.send();
    assert.equal(app.state.pending.request_id,'fixed-request');
  });
  test('uploaded chat attachments remain available to explicitly reattach after refresh', async () => {
    const {app}=harness(async route=>route==='/phone/state'?paired:snapshot('chat-1',{attachments:[{id:'a1',name:'own.png',size:4,kind:'image'}]}));
    await app.init();await app.selectChat('chat-1');app.addAttachment('a1');
    assert.deepEqual(app.state.selected.map(file=>file.id),['a1']);app.addAttachment('not-in-chat');assert.equal(app.state.selected.length,1);
  });
  test('pending retries stay bound to the original chat and cannot mix another chat draft', async () => {
    const {app,calls}=harness(async route=>{if(route==='/phone/state')return paired;if(route.endsWith('/messages'))throw Error('lost response');return snapshot();});
    await app.init();await app.selectChat('chat-1');app.setDraft('Bound message');await app.send();
    await app.selectChat('chat-2');
    assert.equal(app.state.currentId,'chat-1');
    assert.equal(calls.filter(call=>call.route==='/phone/chats/chat-2').length,0);
  });
  test('client preserves normal filenames containing adjacent periods and sends binary bytes untouched', async () => {
    const calls=[];const client=ui.createClient(async(route,options)=>{calls.push({route,...options});return {ok:true,status:200,json:async()=>({id:'upload-1'})};});
    const bytes=new Uint8Array([0,128,255]);
    await client('/phone/chats/c1/attachments?name=take..mp4&request_id=r1',{method:'POST',csrf:'s',binary:true,body:bytes});
    assert.equal(calls[0].body,bytes);assert.equal(calls[0].headers['Content-Type'],'application/octet-stream');
  });
  test('private chat logout and draft retention tolerate blocked browser storage', async () => {
    const denied={getItem(){throw Error('denied');},setItem(){throw Error('denied');},removeItem(){throw Error('denied');}};
    const {app}=harness(undefined,{storage:denied,pendingStorage:denied});await app.init();await app.selectChat('chat-1');app.setDraft('Words');
    await app.send();assert.equal(app.state.draft,'');await app.logout();assert.equal(app.state.paired,false);
  });
  test('mobile back-forward cache resumes polling without losing the mounted composer', async () => {
    const events=new Map(), timers=new Map(), nodes=new Map();let serial=0,requests=0;
    function element(){return {value:'',children:[],append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},setAttribute(){},removeAttribute(){},addEventListener(){},scrollIntoView(){}};}
    const doc={hidden:false,activeElement:null,documentElement:{scrollHeight:0},getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},createElement:element,createDocumentFragment:element,addEventListener(){}};
    const win={document:doc,location:{hash:'',pathname:'/phone/',search:''},history:{},localStorage:memory(),sessionStorage:memory(),innerHeight:740,scrollY:0,fetch:async()=>{requests++;return {ok:true,status:200,json:async()=>paired};},setInterval(fn){const id=++serial;timers.set(id,fn);return id;},clearInterval(id){timers.delete(id);},addEventListener(name,fn){events.set(name,fn);}};
    const app=ui.mount(win);await new Promise(resolve=>setImmediate(resolve));
    assert.equal(timers.size,1);events.get('pagehide')({persisted:true});assert.equal(timers.size,0);
    assert.equal(typeof events.get('pageshow'),'function');events.get('pageshow')({persisted:true});
    await new Promise(resolve=>setImmediate(resolve));assert.equal(timers.size,1);assert.ok(requests>=2);app.destroy();
  });
  test('logout revokes once and clears saved local chat/drafts without touching other storage', async () => {
    const storage=memory();storage.setItem('unrelated','keep');
    const {app,calls}=harness(undefined,{storage});await app.init();await app.selectChat('chat-1');app.setDraft('private draft');await app.logout();
    assert.equal(app.state.paired,false);assert.equal(storage.getItem('phone.chat'),null);assert.equal(storage.getItem('phone.draft.chat-1'),null);
    assert.equal(storage.getItem('unrelated'),'keep');assert.equal(calls.filter(c=>c.route==='/phone/logout').length,1);
  });
}

// Owned isolated fixture only: no Storylens calls, models, media jobs or external traffic.
if (process.argv.includes('--fixture')) {
  const http=require('node:http');
  let authed=false;let chat=snapshot('fixture-chat',{title:'Isolated UI fixture',status:'running',stage:'Checking saved work',task_progress:{completed:2,total:5},messages:[{id:'fixture-user',role:'user',text:'<img src=x onerror=alert(1)> Exact fixture text'},{id:'fixture-assistant',role:'assistant',text:'Isolated fixture response. No real model or media job.'}]});
  let failNext=false, connected=true; const seen=new Map(); const requests=[];
  const wav=Buffer.alloc(44+1600);wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(8000,24);wav.writeUInt32LE(16000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(1600,40);
  const fixtureFiles={wave:{name:'Fixture silence.wav',mime:'audio/wav',bytes:wav},image:{name:'Fixture pixel.png',mime:'image/png',bytes:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=','base64')},document:{name:'Fixture notes.txt',mime:'text/plain',bytes:Buffer.from('Isolated fixture download only.')}};
  chat.files=Object.entries(fixtureFiles).map(([id,file])=>({id,name:file.name,mime:file.mime,size:file.bytes.length,url:'/phone/files/'+id,download_url:'/phone/files/'+id+'?download=1'}));
  chat.files.push({id:'unsafe',name:'Blocked external fixture',mime:'image/png',url:'javascript:alert(1)',download_url:'//external.invalid/phone/files/x'});
  const server=http.createServer(async(req,res)=>{
    const url=new URL(req.url,'http:'+'//127.0.0.1');let body='';for await(const chunk of req)body+=chunk;
    requests.push({path:url.pathname,method:req.method,body:body.slice(0,2000)});
    function json(status,data){res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data));}
    if(url.pathname==='/fixture/requests')return json(200,requests);
    if(url.pathname==='/fixture/fail-next'){failNext=true;return json(200,{ok:true});}
    if(url.pathname==='/fixture/disconnect'){connected=false;return json(200,{ok:true});}
    if(url.pathname==='/fixture/reconnect'){connected=true;return json(200,{ok:true});}
    if(url.pathname.startsWith('/phone/files/')){const file=fixtureFiles[url.pathname.split('/').pop()];if(!file){res.writeHead(404);res.end();return;}res.writeHead(200,{'Content-Type':file.mime,'Content-Length':file.bytes.length,...(url.searchParams.has('download')?{'Content-Disposition':'attachment; filename="'+file.name+'"'}:{})});res.end(file.bytes);return;}
    if(url.pathname==='/phone/pair'){authed=true;return json(200,{paired:true,csrf:'fixture-only-csrf'});}
    if(url.pathname==='/phone/state')return authed?json(200,{...paired,connected,csrf:'fixture-only-csrf',chats:[{id:chat.id,title:chat.title,status:chat.status}]}):json(401,{error:'Pair this phone.'});
    if(url.pathname==='/phone/logout'){authed=false;return json(200,{ok:true});}
    if(url.pathname==='/phone/chats'&&req.method==='POST')return json(200,chat);
    if(url.pathname==='/phone/chats/fixture-chat/messages'){
      const data=JSON.parse(body);if(!seen.has(data.request_id)){seen.set(data.request_id,true);chat={...chat,messages:[...chat.messages,{id:data.request_id,role:'user',text:data.message}]};}
      if(failNext){failNext=false;return json(503,{error:'Fixture response lost after commit'});}return json(200,chat);
    }
    if(url.pathname==='/phone/chats/fixture-chat/stop'){chat={...chat,status:'idle',stage:'Stopped after current step'};return json(200,chat);}
    if(url.pathname==='/phone/chats/fixture-chat')return json(200,chat);
    if(url.pathname.startsWith('/phone/chats/fixture-chat/attachments')){const file={id:'fixture-attachment',name:url.searchParams.get('name'),size:body.length,kind:'file'};chat.attachments=[file];return json(200,file);}
    const names={'/phone/':'index.html','/phone/phone.css':'phone.css','/phone/phone.js':'phone.js'};
    if(names[url.pathname]){res.writeHead(200,{'Content-Type':names[url.pathname].endsWith('.html')?'text/html':names[url.pathname].endsWith('.css')?'text/css':'text/javascript','Cache-Control':'no-store'});res.end(fs.readFileSync(path.join(uiPath,names[url.pathname])));return;}
    res.writeHead(404);res.end();
  });
  server.listen(0,'127.0.0.1',()=>console.log('FIXTURE_URL=http:'+'//127.0.0.1:'+server.address().port+'/phone/'));
}
