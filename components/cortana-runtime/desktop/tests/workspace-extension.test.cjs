const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function extension(tabs, playback = {available:true, paused:true, seconds:42}) {
  const actions = [];
  const listener = {addListener() {}};
  const chrome = {
    tabs: {
      query: async () => tabs,
      get: async id => tabs.find(t=>t.id===id),
      update: async (id, changes) => { actions.push(['update',id,changes]); return {...tabs.find(t=>t.id===id),...changes}; },
      create: async () => { throw new Error('Unexpected duplicate tab creation'); },
    },
    windows: {update:async (...args)=>actions.push(['focus',...args])},
    scripting:{executeScript:async()=>[{result:playback}]},
    runtime:{onMessage:listener,onStartup:listener},
  };
  const context=vm.createContext({chrome,URL,setTimeout,clearInterval,setInterval,crypto:require('node:crypto').webcrypto});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../browser-extension/worker.js'),'utf8'),context);
  vm.runInContext("port={}; config={browser:'chrome',profile:'demo'}",context);
  return {actions, run:command=>{context.command=command;return vm.runInContext('execute(command)',context);},
    stop:id=>{context.stopId=id;vm.runInContext('cancelled.add(stopId)',context);}};
}
function command(args={}) {
  return {id:'test-command',operation:'restore',expires_at:Date.now()/1000+15,
    arguments:{url:'https://www.youtube.com/watch?v=demo',playback_seconds:42,...args}};
}

test('YouTube reuse verifies video identity despite unrelated URL parameters',async()=>{
  const ext=extension([{id:7,windowId:2,url:'https://www.youtube.com/watch?v=demo&t=1',status:'complete'}]);
  const result=await ext.run(command());
  assert.equal(result.verified,true);
  assert.equal(result.reused,true);
  assert.equal(result.tab_id,7);
});
test('Paused at the wrong time does not pass timestamp restoration',async()=>{
  const ext=extension([{id:7,windowId:2,url:'https://www.youtube.com/watch?v=demo',status:'complete'}],
    {available:true,paused:true,seconds:3});
  assert.equal((await ext.run(command())).verified,false);
});
test('Duplicate matches stop before changing any tab',async()=>{
  const ext=extension([1,2].map(id=>({id,url:'https://www.youtube.com/watch?v=demo',status:'complete'})));
  await assert.rejects(ext.run(command()),/Multiple matching/);
  assert.equal(ext.actions.length,0);
});
test('Cancelled and expired commands cannot start tab mutations',async()=>{
  const ext=extension([]);
  ext.stop('test-command');
  await assert.rejects(ext.run(command()),/stopped or expired/);
  await assert.rejects(ext.run({...command(),id:'expired',expires_at:0}),/stopped or expired/);
  assert.equal(ext.actions.length,0);
});

test('Periodic capture reads only saved tabs without focus or playback changes',async()=>{
  const ext=extension([{id:7,windowId:2,url:'https://www.youtube.com/watch?v=demo',status:'complete'},
    {id:8,windowId:2,url:'https://example.com/unrelated',status:'complete'}]);
  const result=await ext.run({...command(),operation:'capture_saved',arguments:{items:[{target:'https://www.youtube.com/watch?v=demo'}]}});
  assert.equal(result.items.length,1);
  assert.equal(result.items[0].tab_id,7);
  assert.equal(ext.actions.length,0);
});
