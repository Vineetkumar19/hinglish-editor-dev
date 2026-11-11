const test=require('node:test'),assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const {createClipboardWatcher}=require('../editor_plugins/shared/clipboard-shortcut.cjs');
test('watcher launches only the fixed local helper and forwards single-file events',async()=>{
 const child=new EventEmitter();child.stdout=new EventEmitter();child.stderr=new EventEmitter();child.kill=()=>{child.killed=true};const received=[],states=[];let args;
 const watch=createClipboardWatcher({root:'D:/Storylens',parentPid:77,onPaste:x=>received.push(x),onState:x=>states.push(x),spawn:(...a)=>{args=a;return child}});
 const starting=watch.setEnabled(true);child.stdout.emit('data',Buffer.from('{"event":"ready"}\n'));await starting;
 assert.equal(args[1].at(-1),'77');assert.equal(args[2].windowsHide,true);assert.equal(args[2].shell,false);
 child.stdout.emit('data',Buffer.from('{"event":"paste","request_id":"one","paths":["D:/photo.jpg"]}\n'));
 assert.equal(received.length,1);watch.stop();assert.equal(child.killed,true);
});
test('malformed helper input does not become an arbitrary native command',async()=>{
 const child=new EventEmitter();child.stdout=new EventEmitter();child.stderr=new EventEmitter();child.kill=()=>{};let calls=0;
 const watch=createClipboardWatcher({root:'D:/Storylens',onPaste:()=>calls++,onState(){},spawn:()=>child});
 const p=watch.setEnabled(true);child.stdout.emit('data','{"event":"ready"}\n');await p;
 child.stdout.emit('data','{"event":"eval","script":"bad"}\n{"event":"paste","paths":[]}\n');assert.equal(calls,0);watch.stop();
});
