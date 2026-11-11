const test=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const {createClient}=require('../editor_plugins/shared/project-view.cjs');
const project='D:/Edit/owner project.aep',root='Z:/nonexistent-storylens-test';
function fakeSpawn(reply){let calls=[],children=[];return {calls,children,spawn:(exe,args,options)=>{const child=new EventEmitter();child.stdout=new EventEmitter();child.stderr=new EventEmitter();child.stdin=new EventEmitter();child.stdin.write=(line,done)=>{const request=JSON.parse(line);queueMicrotask(()=>reply(child,request));done?.();};child.kill=()=>{child.killed=true;child.emit('exit');};children.push(child);calls.push({exe,args,options});return child;}};}
test('capture and restore reuse one small hidden process with no shell',async()=>{
 const f=fakeSpawn((child,r)=>child.stdout.emit('data',JSON.stringify({id:r.id,result:{ok:true,project_id:project,positions:{vertical:200}}})+'\n'));
 const client=createClient(root,{spawn:f.spawn});try{const captured=await client.capture(project);await client.restore(captured);assert.equal(f.calls.length,1);assert.equal(f.calls[0].options.shell,false);assert.equal(f.calls[0].options.windowsHide,true);assert.ok(f.calls[0].args.includes('--worker'));}finally{client.stop();}assert.ok(f.children[0].killed);
});
test('helper releases its memory after a short idle period',async()=>{
 const f=fakeSpawn((child,r)=>child.stdout.emit('data',JSON.stringify({id:r.id,result:{ok:true,project_id:project}})+'\n'));const client=createClient(root,{spawn:f.spawn,idleMs:8,leaseMs:40});const snapshot=await client.capture(project);await new Promise(r=>setTimeout(r,16));assert.ok(!f.children[0].killed,'keep capture lease through native Paste');await client.restore(snapshot);await new Promise(r=>setTimeout(r,20));assert.ok(f.children[0].killed);client.stop();
});
test('crash, malformed response and timeout fail open without hanging Paste',async()=>{
 for(const reply of [(c)=>c.emit('exit'),c=>c.stdout.emit('data','garbage\n'),()=>{}]){const f=fakeSpawn(reply),client=createClient(root,{spawn:f.spawn,timeoutMs:5});const keepAlive=setTimeout(()=>{},50);try{assert.equal((await client.capture(project)).reason,'scroll-unavailable');}finally{clearTimeout(keepAlive);client.stop();}}
});
test('unsafe project identity never starts a helper',async()=>{const f=fakeSpawn(()=>{}),client=createClient(root,{spawn:f.spawn});assert.equal((await client.capture('relative.aep')).reason,'project-unavailable');assert.equal(f.calls.length,0);client.stop();});
