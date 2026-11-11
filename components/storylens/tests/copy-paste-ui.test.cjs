const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.style={};this.textContent='';this.hidden=false;this.disabled=false;}
 append(el){el.parent=this;this.children.push(el)}replaceChildren(){for(const el of this.children)el.parent=null;this.children=[]}
 setAttribute(){}addEventListener(type,fn){(this.listeners[type]||=[]).push(fn)}removeEventListener(type,fn){this.listeners[type]=(this.listeners[type]||[]).filter(f=>f!==fn)}
 contains(el){for(let c=el;c;c=c.parent)if(c===this)return true;return false}
 closest(){return ['input','textarea','select'].includes(this.tagName)?this:null}
 click(){if(!this.disabled)return this.onclick?.()}
 find(tag,text){if(this.tagName===tag&&(text===undefined||this.textContent===text))return this;for(const child of this.children){const found=child.find(tag,text);if(found)return found}}
}
function setup(native,options={}){const root=new Element('section'),window={addEventListener(){}};const c={window,document:{createElement:tag=>new Element(tag)}};vm.createContext(c);vm.runInContext(fs.readFileSync('hinglish_app/static/feedback.js','utf8'),c);vm.runInContext(fs.readFileSync('editor_plugins/copy-paste/ui.js','utf8'),c);const mount=host=>window.storylensCopyPaste({root,host:host||'aftereffects',native,...options});return {root,window,mount}}
test('switching to Copy Paste twice does not issue two pastes for one panel shortcut',async()=>{let pastes=0;const f=setup(async(action,p)=>{if(p.action==='paste')pastes++;return {ok:true,total:1,next:1,complete:true,template:'Example',slots:[]}});f.mount();f.mount();const target=f.root.find('button','Paste');let prevented=0;for(const fn of f.root.listeners.keydown)fn({target,ctrlKey:true,key:'2',preventDefault(){prevented++}});await new Promise(resolve=>setImmediate(resolve));assert.equal(pastes,1);assert.equal(prevented,1)});
test('unknown parser failure is readable and diagnostics remain collapsed',async()=>{const f=setup(async()=>{throw new SyntaxError('Unexpected token < in JSON.parse response')});f.mount();await f.root.find('button','Paste').click();const technical=f.root.children.find(el=>el.tagName==='details'&&el.children[0].textContent==='Technical details');assert.equal(technical.hidden,false);assert.equal(technical.open,false);assert.match(technical.find('pre').textContent,/Unexpected token/);assert.ok(f.root.children.some(el=>el.textContent.includes('unreadable response')));assert.ok(!f.root.children.some(el=>el.tagName==='p'&&/Unexpected token/.test(el.textContent)))});
test('known native recovery message is preserved',async()=>{const message='Every detected slot is filled. Choose a different template.';const f=setup(async()=>({error:message,code:'copy_paste_full',details:'native guard'}));f.mount();await f.root.find('button','Paste').click();assert.ok(f.root.children.some(el=>el.textContent===message))});
test('Premiere mount exposes no paste command and does not call native',()=>{let calls=0;const f=setup(()=>{calls++});f.mount('premiere');assert.equal(f.root.find('button'),undefined);assert.equal(calls,0);assert.match(f.root.find('p').textContent,/Dynamic Link/)});
test('ordinary text and selection controls keep their keyboard commands',()=>{let calls=0;const f=setup(()=>{calls++});f.mount();const select=f.root.find('select');for(const fn of f.root.listeners.keydown)fn({target:select,ctrlKey:true,key:'v',preventDefault(){throw Error('must not intercept')}});assert.equal(calls,0)});

test('older known-code native exceptions cannot expose technical text in the status',async()=>{const f=setup(async()=>({error:'TypeError: footage.source is undefined',code:'copy_paste_native',details:'native failure'}));f.mount();await f.root.find('button','Copy').click();assert.ok(!f.root.children.some(el=>el.tagName==='p'&&/TypeError/.test(el.textContent)));});
test('native C/V and Save are never intercepted even over Copy Paste buttons',()=>{let calls=0;const f=setup(()=>calls++);f.mount();const target=f.root.find('button','Copy');for(const key of ['c','v','s'])for(const fn of f.root.listeners.keydown)fn({target,ctrlKey:true,key,preventDefault(){throw Error('native shortcut intercepted')}});assert.equal(calls,0)});
test('Off releases both panel commands and does not capture a source',async()=>{let calls=0;const f=setup(()=>calls++),view=f.mount();await view.setEnabled(false);for(const fn of f.root.listeners.keydown)fn({target:f.root.find('button','Copy'),ctrlKey:true,key:'1',preventDefault(){throw Error('Off intercepted a key')}});assert.equal(calls,0)});
test('Explorer acquisition disables paste immediately and a failed copy clears stale media',async()=>{
 let finish;const calls=[],f=setup(async(action,p)=>{calls.push([action,p]);if(action==='explorerSelection')return new Promise((_,reject)=>finish=reject);return {ok:true,copied:true};});f.mount();f.root.find('select').value='explorer';
 const first=f.root.find('button','Copy').click();await new Promise(r=>setImmediate(r));
 assert.equal(f.root.find('button','Paste').disabled,true);f.root.find('button','Copy').click();
 assert.equal(calls.filter(([action])=>action==='explorerSelection').length,1);
 finish(Error('Select one image or video in Explorer.'));await first;
 assert.ok(calls.some(([action,p])=>action==='copyPaste'&&p.action==='clear'));
});
test('late notifications cannot turn an Off component back on',async()=>{const f=setup(async()=>({ok:true})),view=f.mount();await view.setEnabled(false);view.filePaste({phase:'finished',result:{template:'Example',slots:[],pasted:{media:'Late.jpg',number:1},total:2}});assert.equal(f.root.find('button','Paste').disabled,true);assert.equal(f.root.children.some(el=>el.textContent.includes('Late.jpg')),false);});

test('helper failure reports unavailable shortcuts while buttons remain usable and explicit retry recovers',async()=>{
 const states=[],f=setup(async()=>({ok:true}),{keyboard:async enabled=>({ok:true,enabled}),onEnabled:(enabled,ready)=>states.push([enabled,ready])}),view=f.mount();
 await view.setEnabled(true);assert.equal(view.isShortcutReady(),true);
 view.shortcutState({enabled:false,message:'Storylens shortcuts stopped.'});
 assert.equal(view.isEnabled(),true);assert.equal(view.isShortcutReady(),false);assert.equal(f.root.find('button','Paste').disabled,false);assert.deepEqual(states.at(-1),[true,false]);
 await view.setEnabled(true);assert.equal(view.isShortcutReady(),true);assert.deepEqual(states.at(-1),[true,true]);
 assert.equal(f.root.children.some(el=>el.tagName==='p'&&/shortcuts stopped/i.test(el.textContent)),false);
});

test('Off during delayed Explorer selection cannot capture late media or overwrite status',async()=>{
 let finish;const calls=[],f=setup(async(action,p)=>{calls.push([action,p]);if(action==='explorerSelection')return new Promise(resolve=>finish=resolve);return {ok:true,cleared:true};}),view=f.mount();f.root.find('select').value='explorer';
 const copying=f.root.find('button','Copy').click();await new Promise(r=>setImmediate(r));await view.setEnabled(false);finish({paths:['D:/late.jpg']});await copying;
 assert.equal(calls.some(([action,p])=>action==='copyPaste'&&p.action==='copyFile'),false);assert.equal(f.root.find('button','Paste').disabled,true);
});

test('Off while native clipboard clear is pending prevents any Explorer acquisition or late status update',async()=>{
 let finish;const calls=[],f=setup(async(action,p)=>{calls.push([action,p]);if(p.action==='clear')return new Promise(resolve=>finish=resolve);return {paths:['D:/late.jpg']};}),view=f.mount();f.root.find('select').value='explorer';
 const copying=f.root.find('button','Copy').click();await new Promise(r=>setImmediate(r));await view.setEnabled(false);finish({ok:true,cleared:true});await copying;
 assert.equal(calls.some(([action])=>action==='explorerSelection'),false);assert.equal(f.root.find('button','Paste').disabled,true);
});

test('compact controls start shortcuts automatically with no activation or empty instruction rows',async()=>{
 const states=[],f=setup(async()=>({ok:true}),{keyboard:async enabled=>{states.push(enabled);return {ok:true,enabled}}}),view=f.mount();
 await view.ready;assert.equal(view.isShortcutReady(),true);assert.deepEqual(states,[true]);
 const row=f.root.children[0];assert.deepEqual(row.children.map(e=>e.tagName),['select','button','button','button']);assert.equal(row.style.display,'grid');
 assert.deepEqual(row.children.slice(1).map(e=>e.textContent),['Copy','Paste','Undo']);assert.equal(row.children[0].value,'project');
 assert.equal(f.root.find('button','Off'),undefined);assert.equal(f.root.find('button','Read slots'),undefined);assert.equal(f.root.find('label','Picture fit'),undefined);
 assert.equal(f.root.children.filter(e=>e.tagName==='p'&&!e.hidden).length,0);
 for(const details of f.root.children.filter(e=>e.tagName==='details'))assert.ok(!details.open);
});

test('mouse shortcuts work before opening Copy Paste and use fill even after changing source',async()=>{
 const calls=[],f=setup(async(action,p)=>{calls.push([action,p]);return {ok:true}}, {keyboard:async enabled=>({ok:true,enabled})}),view=f.mount();await view.ready;
 await view.shortcut({command:'copy',source:'project'});await view.shortcut({command:'paste'});await view.shortcut({command:'undo'});
 assert.deepEqual(calls.filter(c=>c[0]==='copyPaste').map(c=>c[1].action),['clear','copy','paste','undo']);assert.equal(calls.find(c=>c[1].action==='paste')[1].fit,'fill');
});

test('one local error does not create a second global error box',async()=>{
 let globalErrors=0;const f=setup(async()=>({error:'Choose a template.',code:'copy_paste_target',details:'selection diagnostic'}),{showError:()=>globalErrors++});f.mount();await f.root.find('button','Paste').click();
 assert.equal(globalErrors,0);assert.equal(f.root.children.filter(e=>e.tagName==='p'&&!e.hidden).length,1);assert.equal(f.root.children.filter(e=>e.tagName==='details'&&!e.hidden&&e.children[0].textContent==='Technical details').length,1);
});
