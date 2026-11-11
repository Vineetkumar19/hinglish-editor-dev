const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.hidden=false;this.style={};this.dataset={};this.value='';this.attrs={};this.textContent='';}
 append(...items){this.children.push(...items)}replaceChildren(...items){this.children=[...items]}add(item){this.append(item)}setAttribute(k,v){this.attrs[k]=v}addEventListener(){}removeEventListener(){}
 querySelector(tag){let e=this.children.find(c=>c.tagName===tag);if(!e){e=new Element(tag);this.children.push(e)}return e}
 querySelectorAll(tag){return this.children.filter(c=>c.tagName===tag)}contains(el){return el===this||this.children.some(c=>c.contains?.(el))}
}
async function panel(host='aftereffects',options={}){
 const nodes=new Map(),calls=[],api=[],requests=[],listeners={};const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};
 const window={storylensIcon:()=>'<span></span>',storylensError:e=>e.message,storylensClearError(){},storylensFetch:async (path,init)=>{api.push(path);requests.push({path,body:init?.body?JSON.parse(init.body):null});return options.response?options.response(path):{caption_styles:[]}},storylensResponse:async r=>r,addEventListener:(type,fn)=>{(listeners[type]||=[]).push(fn)}};
 window.parent={postMessage:message=>{calls.push(message);const result=options.native?options.native(message):message.action==='shortcutWatch'?{ok:true,enabled:message.payload.enabled}:message.action==='clipboardWatch'?{ok:true,enabled:true,message:'Keyboard paste ready.'}:message.action==='copyPaste'?{ok:true,copied:true,clipboard:{name:'Owner photo.jpg',id:42}}:{ok:true,placements:[],covered_duration:0,uncovered_duration:0};listeners.message.forEach(fn=>fn({source:window.parent,data:{type:'storylens-host-response',nonce:'test',id:message.id,result}}))}};
 const context={window,document:{getElementById:get,createElement:tag=>new Element(tag),body:{dataset:{}},documentElement:{dataset:{token:'local'}}},location:{search:'?host='+host+'&nonce=test'},localStorage:{getItem:()=>null,setItem(){}},URLSearchParams,Option:class extends Element{constructor(text,value){super('option');this.textContent=text;this.value=value}},setTimeout,clearTimeout,console};
 vm.createContext(context);for(const file of ['editor_plugins/shared/panel-model.js','hinglish_app/static/template-aliner.js','editor_plugins/copy-paste/ui.js','hinglish_app/static/template-import.js','hinglish_app/static/editor-panel.js'])vm.runInContext(fs.readFileSync(file,'utf8'),context);
 await new Promise(r=>setImmediate(r));return {get,get rawCalls(){return calls},get calls(){return calls.filter(c=>c.action!=='shortcutWatch'&&!(c.action==='templateImport'&&c.payload.action==='status'))},api,requests,notify:data=>listeners.message.forEach(fn=>fn({source:window.parent,data:{type:'storylens-file-paste',nonce:'test',...data}})),shortcutState:state=>listeners.message.forEach(fn=>fn({source:window.parent,data:{type:'storylens-shortcut-state',nonce:'test',state}}))};
}
function all(root){return [root,...root.children.flatMap(all)]}
test('AE feature 13 opens local Copy Paste controls without starting an editing job',async()=>{
 const p=await panel(),buttons=p.get('tools').children,copyTile=buttons.find(b=>b.dataset.mode==='copyPaste');
 assert.equal(buttons.filter(b=>b.dataset.mode==='copyPaste').length,1);assert.ok(copyTile);
 p.get('sharedScript').value='Keep these exact words';await copyTile.onclick();
 assert.equal(p.get('copyPasteSection').hidden,false);assert.equal(p.get('sharedSettings').hidden,true);assert.equal(p.get('editingControls').hidden,true);assert.equal(p.calls.filter(c=>c.action==='copyPaste').length,0);assert.deepEqual(p.api,['/api/panel/config','/api/captions/auto2/catalog']);
 const copy=all(p.get('copyPasteSection')).find(e=>e.tagName==='button'&&e.textContent==='Copy');await copy.onclick();
 const copied=p.calls.filter(c=>c.action==='copyPaste');assert.equal(copied.length,2);assert.deepEqual(copied.map(c=>c.payload.action),['clear','copy']);
 const caption=all(p.get('copyPasteSection')).find(e=>e.tagName==='button'&&e.title==='Owner photo.jpg');assert.ok(caption);
 buttons[0].onclick();await copyTile.onclick();assert.ok(all(p.get('copyPasteSection')).includes(caption));assert.equal(p.get('sharedScript').value,'Keep these exact words');
});
test('Premiere and CapCut do not expose or launch the AE-only native feature',async()=>{
 for(const host of ['premiere','capcut']){const p=await panel(host);assert.equal(p.get('tools').children.some(b=>b.dataset.mode==='copyPaste'),false);assert.equal(p.get('copyPasteSection').hidden,true);assert.equal(p.calls.length,0);}
});
test('Explorer paste events reveal the Copy Paste tool and show the confirmed native slot',async()=>{
 const p=await panel();await p.get('tools').children.find(b=>b.dataset.mode==='copyPaste').onclick();p.notify({phase:'working'});assert.equal(p.get('copyPasteSection').hidden,false);
 p.notify({phase:'finished',result:{ok:true,next:2,total:24,slots:[],pasted:{media:'River.jpg',number:2}}});
 assert.ok(all(p.get('copyPasteSection')).some(e=>e.title==='Placed River.jpg · 2 of 24'));
});


test('Clean and Script Edit selection show one action without unrelated template settings or automatic runs',async()=>{const p=await panel();for(const [index,label]of[[0,'Run Smart Clean'],[1,'Run Script Edit']]){p.get('tools').children[index].onclick();assert.equal(p.get('run').textContent,label);assert.equal(p.get('toolTitle').hidden,true);assert.equal(p.get('templateAlinerSettings').hidden,true);assert.equal(p.calls.length,0);assert.equal(p.api.includes('/api/panel/run'),false)}});

test('Script Edit reuses shared words and two clicks send only one request',async()=>{const p=await panel('aftereffects',{native:()=>({project_id:'fixture',sequence_id:'fixture',name:'Fixture'}),response:path=>path==='/api/panel/context'?{id:'fixture'}:path==='/api/panel/run'?{status:'failed',stage:'Fixture stops before generation'}:{styles:[]}});p.get('tools').children[1].onclick();p.get('sharedScript').value='Keep exact shared words 2026';await Promise.all([p.get('run').onclick(),p.get('run').onclick()]);const runs=p.requests.filter(r=>r.path==='/api/panel/run');assert.equal(runs.length,1);assert.equal(runs[0].body.script,'Keep exact shared words 2026');assert.equal(runs[0].body.mode,'script');assert.equal(p.get('run').disabled,false)});

test('Caption action has a short Run label for its narrow thirty percent column',async()=>{const p=await panel();p.get('tools').children[2].onclick();assert.equal(p.get('run').textContent,'Run')});

test('failed context capture clears the reading indicator and cannot submit a job',async()=>{const p=await panel('aftereffects',{native:()=>({project_id:'fixture',sequence_id:'fixture'}),response:path=>{if(path==='/api/panel/context')throw Error('Open a composition first.');return {styles:[]}}});await p.get('run').onclick();assert.equal(p.get('connection').textContent,'Check timeline');assert.equal(p.get('error').hidden,false);assert.equal(p.api.includes('/api/panel/run'),false);assert.equal(p.get('run').disabled,false)});

test('panel auto-connects shortcuts without a Copy Paste activation and keeps its label stable after recovery',async()=>{
 const p=await panel(),button=p.get('tools').children.find(b=>b.dataset.mode==='copyPaste');assert.equal(p.rawCalls.filter(c=>c.action==='shortcutWatch'&&c.payload.enabled===true).length,1);assert.equal(button.textContent,'Copy Paste');
 p.shortcutState({enabled:false,message:'Storylens shortcuts stopped.'});assert.equal(button.textContent,'Copy Paste');assert.equal(p.get('copyPasteSection').hidden,false);
 assert.equal(all(p.get('copyPasteSection')).find(e=>e.textContent==='Paste').disabled,false);
 await button.onclick();assert.equal(button.textContent,'Copy Paste');assert.equal(p.rawCalls.filter(c=>c.action==='shortcutWatch').at(-1).payload.enabled,true);assert.equal(p.get('error').hidden,true);
});

test('Import Template is one native click with no script or worker call',async()=>{const p=await panel('aftereffects',{native:msg=>msg.action==='templateImport'?{ok:true,state:'complete',running:false,total:0,imported:0,message:'Already imported.'}:{ok:true}});const button=p.get('tools').children.find(x=>x.dataset.mode==='templateImport');assert.ok(button);await button.onclick();await p.get('templateImport').onclick();assert.equal(p.get('templateImportSection').hidden,false);assert.equal(p.get('sharedSettings').hidden,true);assert.equal(p.get('editingControls').hidden,true);assert.equal(p.calls.length,1);assert.equal(p.calls[0].action,'templateImport');assert.equal(p.calls[0].payload.action,'start');assert.equal(p.api.includes('/api/panel/run'),false);assert.match(p.get('templateImportStatus').textContent,/Already imported/)});

test('opening Copy Paste repeatedly keeps its buttons enabled instead of toggling Off',async()=>{const p=await panel(),button=p.get('tools').children.find(b=>b.dataset.mode==='copyPaste');await button.onclick();await button.onclick();assert.equal(button.textContent,'Copy Paste');assert.equal(all(p.get('copyPasteSection')).find(e=>e.textContent==='Copy').disabled,false);assert.equal(p.rawCalls.filter(c=>c.action==='shortcutWatch'&&c.payload.enabled===false).length,0)});
