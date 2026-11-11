const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const M=require('../editor_plugins/copy-paste/model.js');
function graph(){return {
 1:{name:'Final',layers:[{index:1,name:'Scene_10',source:3,kind:'comp',start:10},{index:2,name:'Scene_02',source:2,kind:'comp',start:0}]},
 2:{name:'Scene_02',layers:[{index:1,name:'Image_02',source:4,kind:'comp',start:0},{index:2,name:'Particles.mp4',source:99,kind:'media',start:0},{index:3,name:'Texture Background',source:98,kind:'media',start:0}]},
 3:{name:'Scene_10',layers:[{index:1,name:'Photo 10',source:55,kind:'media',start:0},{index:2,name:'Text 3',source:56,kind:'media',start:0}]},
 4:{name:'Image_02',layers:[{index:1,name:'source.jpg',source:54,kind:'media',start:0}]}
};}
test('deep holder discovery excludes particles/text/background, follows scene time',()=>{const r=M.scan(graph(),1);assert.deepEqual(r.slots.map(s=>s.comp),['4','3']);assert.deepEqual(Object.keys(r.ancestors).sort(),['1','2','3','4']);});
test('unlabelled arbitrary footage is not guessed as a media slot',()=>{assert.equal(M.scan({1:{name:'Final',layers:[{index:1,name:'0001.jpg',source:2,kind:'media',start:0}]}},1).slots.length,0)});

test('an unlabelled single-picture holder is discovered by its structure',()=>{const g={1:{name:'Final',layers:[{index:1,name:'Scene',source:2,kind:'comp',start:0}]},2:{name:'Comp 42',structuralHolder:true,layers:[{index:1,name:'0001.jpg',source:3,kind:'media',start:0}]}};assert.equal(M.scan(g,1).slots.length,1)});

test('a named holder cannot guess among multiple unnamed distinct media sources',()=>{const g={1:{name:'Image 1',layers:[{index:1,name:'0001.jpg',source:2,kind:'media',start:0},{index:2,name:'0002.jpg',source:3,kind:'media',start:0}]}};assert.throws(()=>M.scan(g,1),e=>e.code==='copy_paste_template'&&/multiple unnamed/.test(e.message));});

test('explicitly named media layers in one holder remain separate supported slots',()=>{const g={1:{name:'Images',layers:[{index:1,name:'Image 1',source:2,kind:'media',start:0},{index:2,name:'Image 2',source:3,kind:'media',start:1}]}};assert.equal(M.scan(g,1).slots.length,2)});

test('named solid picture placeholders can be replaced without treating backgrounds as pictures',()=>{const g={1:{name:'Final',layers:[{index:1,name:'Image 1',source:2,kind:'comp',start:0},{index:2,name:'Background',source:4,kind:'media',start:0,solid:true}]},2:{name:'Image 1',layers:[{index:1,name:'Gray Solid',source:3,kind:'media',solid:true,start:0}]}};assert.equal(M.scan(g,1).slots.length,1)});

test('composition expressions resolve renamed isolated branches, including computed names',()=>{
 const source='var n="Image "+1; comp(n).width + comp("Controls").height';
 const rewritten=M.expression(source,{'Image 1':'Image 1 [Copy Paste 4]','Controls':'Controls [Copy Paste 4]'});
 const calls=[],context={comp:name=>{calls.push(name);return {width:10,height:20}}};vm.createContext(context);vm.runInContext(rewritten,context);
 assert.deepEqual(calls,['Image 1 [Copy Paste 4]','Controls [Copy Paste 4]']);
 assert.equal(vm.runInContext(rewritten,context),30);
});
test('literal controller expressions carry only aliases they actually reference',()=>{
 const names={Controls:'Private Controls'};for(let i=0;i<200;i++)names['Unused scene '+i]='Unused scene '+i+' private';
 const rewritten=M.expression('comp("Controls").width',names);assert.ok(!rewritten.includes('Unused scene'));const calls=[];assert.equal(vm.runInNewContext(rewritten,{comp:name=>{calls.push(name);return {width:42};}}),42);assert.deepEqual(calls,['Private Controls']);
 assert.equal(M.expression('wiggle(2, 10)',names),'wiggle(2, 10)');
});

test('isolation follows the next holder and its expression dependants rather than every unused scene',()=>{
 const g={1:{name:'Final',layers:[{kind:'comp',source:2},{kind:'comp',source:3},{kind:'comp',source:4}]},2:{name:'Image 1',layers:[]},3:{name:'Image 2',layers:[]},4:{name:'Titles',layers:[]}};
 const selected=M.isolationSet(g,1,2,{'4':{names:['Final'],dynamic:false}});
 assert.deepEqual(Object.keys(selected.graph).sort(),['1','2','4']);assert.equal(selected.mode,'affected-branch');
 assert.deepEqual(M.referencedComps('// comp("Unused")\ncomp("Final").width'),{names:['Final'],dynamic:false});
 const dynamic=M.isolationSet(g,1,2,{'4':M.referencedComps('comp(prefix + index).width')});
 assert.equal(dynamic.mode,'full-controller-graph');assert.equal(Object.keys(dynamic.graph).length,4);
});

test('keeping a private controller identity avoids copying unrelated scenes that reference it',()=>{
 const g={1:{name:'Final',layers:[{kind:'comp',source:2},{kind:'comp',source:3}]},2:{name:'Image 1',layers:[]},3:{name:'Titles',layers:[]}};
 const refs={'3':{names:['Final'],dynamic:false}};
 const chosen=M.isolationSet(g,1,2,refs,{'1':true});
 assert.deepEqual(Object.keys(chosen.graph).sort(),['1','2']);
 refs['3'].names=['Image 1'];assert.deepEqual(Object.keys(M.isolationSet(g,1,2,refs,{'1':true}).graph).sort(),['1','2','3']);
});

test('literal controllers remain direct calls with no added function compilation',()=>{
 assert.equal(M.expression('comp("Controls").width',{Controls:'Private Controls'}),'comp("Private Controls").width');
 assert.equal(M.expression('comp("Other").width',{Controls:'Private Controls'}),'comp("Other").width');
 assert.equal(M.expression('comp("A\\\"B").width',{'A"B':'Private'}),'comp("Private").width');
 assert.match(M.expression('comp("Scene " + number).width',{'Scene 1':'Private'}),/function __storylensCompRef/);
});

test('the real native template contains empty image canvases; masks and publisher marks are excluded',()=>{
 const data=JSON.parse(fs.readFileSync('tests/fixtures/copy-paste-empty-holder-graph.json','utf8').replace(/^\uFEFF/,''));
 const result=M.scan(data.graph,data.root_id);assert.ok(result.slots.length>=15);assert.match(result.slots[0].path,/Image_01$/);assert.ok(result.slots.every(s=>! /Mask 10|envato/i.test(s.path)));
});
test('one repeated image holder reached through multiple masks is one logical slot',()=>{const g=graph();g[2].layers.push({index:4,name:'Mask03',source:4,kind:'comp',start:1});const s=M.scan(g,1).slots;assert.equal(s.length,2);assert.deepEqual(s[0].layers,[1]);});
test('two distinct holders using the same source footage are distinct slots',()=>{const g=graph();g[3].layers[0].source=54;assert.equal(M.scan(g,1).slots.length,2);});
test('one holder repeats the same source on several animated layers as one slot',()=>{const g=graph();g[4].layers.push({index:2,name:'source.jpg',source:54,kind:'media',start:0});assert.deepEqual(M.scan(g,1).slots[0].layers,[1,2]);});
test('cycles fail without infinite recursion',()=>{const g=graph();g[4].layers.push({index:2,name:'Loop',source:1,kind:'comp',start:0});assert.throws(()=>M.scan(g,1),/circular/);});
test('a solid placeholder in a named picture holder is supported while excluded branches remain untouched',()=>{const g=graph();g[4].layers[0].solid=true;assert.equal(M.scan(g,1).slots.length,2);});
test('saved cursor preserves Aliner prefix and arbitrary owner comments',()=>{const c='Storylens Template Aliner v1 | folder=23 | source=4\nOwner notes',s={owner:8,root:9,next:2,signature:'9:1;4:3,4'};const saved=M.writeState(c,s);assert.ok(saved.startsWith(c));assert.deepEqual(M.state(saved),{...s,owner:'8',root:'9'});assert.equal((M.writeState(saved,{...s,next:3}).match(/\[Storylens Copy Paste/g)||[]).length,1)});
test('pixel aspect is part of Fill/Fit without changing outer transforms',()=>{assert.equal(M.fit(1920,1080,1,1000,1000,1,'fill'),192);assert.equal(M.fit(1920,1080,1,1000,1000,1,'fit'),108);assert.equal(M.fit(1920,1080,1,1920,1080,2,'fill'),100)});

function fixture(){
 let serial=1,undo=0,replaceCount=0,failAt=0;const all=[];
 class SolidSource{};
 class FootageItem{constructor(name,still=true){Object.assign(this,{id:serial++,name,width:1000,height:600,pixelAspect:1,duration:still?1:2,frameRate:30,hasVideo:true,footageMissing:false,file:{fsName:'D:/'+name,exists:true},mainSource:{isStill:still},comment:''});all.push(this)}}
 class Layer{
  constructor(comp,source,name){Object.assign(this,{id:serial++,source,name:name||source.name,containingComp:comp,inPoint:0,outPoint:comp.duration,startTime:0,comment:'',locked:false,audioEnabled:false,keys:{},enabled:true});}
  replaceSource(s){if(this.locked)throw Error('Locked layer');if(++replaceCount===failAt)throw Error('Simulated native replacement failure');this.source=s;this.name=s.name;}
  duplicate(){const l=new Layer(this.containingComp,this.source,this.name);l.keys=structuredClone(this.keys);this.containingComp.children.unshift(l);return l}
  moveAfter(other){const a=this.containingComp.children;a.splice(a.indexOf(this),1);a.splice(a.indexOf(other)+1,0,this)}
  get numProperties(){return (this.expressions||[]).length}
  property(name){if(typeof name==='number')return this.expressions[name-1];if(name==='ADBE Effect Parade')return {addProperty:()=>({property:()=>({setValue(){}})})};if(name==='ADBE Time Remapping')return this.remap||(this.remap={frameRate:this.containingComp.frameRate,keys:[[0,0],[this.source.duration,this.source.duration]],get numKeys(){return this.keys.length},keyTime(i){return this.keys[i-1][0]},removeKey(i){this.keys.splice(i-1,1)},setValueAtTime(t,v){t=Math.round(t*this.frameRate)/this.frameRate;if(!this.keys.length)throw Error('Time Remapping property is hidden after its last key is removed');const old=this.keys.find(k=>Math.abs(k[0]-t)<1e-7);if(old)old[1]=v;else this.keys.push([t,v]);this.keys.sort((a,b)=>a[0]-b[0]);}});return {property:n=>({setValue:v=>{this.keys[n]=v}})}}
 }
 class CompItem{
  constructor(name,w=1920,h=1080,p=1,d=10,fps=30){Object.assign(this,{id:serial++,name,width:w,height:h,pixelAspect:p,duration:d,frameRate:fps,children:[],comment:'',selectedLayers:[],parentFolder:{id:0}});all.push(this);this.layers={add:source=>{const l=new Layer(this,source);this.children.unshift(l);return l}};}
  get numLayers(){return this.children.length}layer(i){return this.children[i-1]}
  get usedIn(){return all.filter(c=>c instanceof CompItem&&c.children.some(l=>l.source===this))}
  duplicate(){const c=new CompItem(this.name,this.width,this.height,this.pixelAspect,this.duration,this.frameRate);c.comment=this.comment;c.parentFolder=this.parentFolder;for(const old of this.children){const l=new Layer(c,old.source,old.name);Object.assign(l,{locked:old.locked,comment:old.comment,startTime:old.startTime,inPoint:old.inPoint,outPoint:old.outPoint,keys:structuredClone(old.keys),expressions:structuredClone(old.expressions||[])});c.children.push(l)}return c}
  remove(){all.splice(all.indexOf(this),1)}
 }
 const media=new FootageItem('my-image.jpg'),video=new FootageItem('my-video.mp4',false),placeholder=new FootageItem('placeholder.jpg'),particles=new FootageItem('Particles.mp4');
 const a=new CompItem('Image_01'),b=new CompItem('Image_02'),scene=new CompItem('Scene_01'),root=new CompItem('Final'),master=new CompItem('Master');
 a.layers.add(placeholder);b.layers.add(placeholder);scene.layers.add(a);scene.layers.add(b);scene.layers.add(particles);root.layers.add(scene);
 const target=master.layers.add(root),other=master.layers.add(root);target.name='Owner template';target.comment='Storylens Template Aliner v1 | folder=1 | source='+root.id;master.selectedLayers=[target];
 const project={revision:1,activeItem:master,selection:[media],get numItems(){return all.length},item:i=>all[i-1],items:{addComp:(...args)=>new CompItem(...args)}};
 const ctx={app:{project,beginUndoGroup(){undo++},endUndoGroup(){undo--}},CompItem,FootageItem,SolidSource};vm.createContext(ctx);
 vm.runInContext(fs.readFileSync('editor_plugins/copy-paste/model.js','utf8'),ctx);vm.runInContext(fs.readFileSync('editor_plugins/copy-paste/framing-model.js','utf8'),ctx);vm.runInContext(fs.readFileSync('editor_plugins/copy-paste/host.jsx','utf8'),ctx);
 const call=p=>JSON.parse(ctx.storylensPanelCopyPaste(p));
 return {call,project,all,master,target,other,root,scene,a,b,media,video,ctx,get undo(){return undo},failNext(n=1){failAt=replaceCount+n}};
}
test('native ID lookup avoids walking thousands of unrelated Project items',()=>{
 const f=fixture();let lookups=0;f.project.itemByID=id=>{lookups++;return f.all.find(item=>item.id===id)||null;};f.project.item=()=>{throw Error('Slow whole-project scan');};
 assert.equal(f.ctx.SLCopyPaste.item(String(f.media.id)),f.media);assert.equal(f.ctx.SLCopyPaste.item(999999),null);assert.equal(lookups,2);
});
test('legacy item lookup remains correct after removal without a stale project cache',()=>{
 const f=fixture();assert.equal(f.ctx.SLCopyPaste.item(f.media.id),f.media);f.all.splice(f.all.indexOf(f.media),1);assert.equal(f.ctx.SLCopyPaste.item(f.media.id),null);
});
test('holder scanning never evaluates unrelated title and paragraph text',()=>{
 const f=fixture();let reads=0;class Text{constructor(){this.name='Documentary body';this.source=null;}property(){reads++;return {property:()=>({value:{text:'Long irrelevant paragraph'}})};}}
 f.ctx.TextLayer=Text;f.root.children.push(new Text());f.ctx.SLCopyPaste.graph(f.root);assert.equal(reads,0);
});
test('Paste defers preview rendering temporarily and restores the owner setting on success or error',()=>{
 for(const locked of [false,true]){const f=fixture(),writes=[];let value=false;Object.defineProperty(f.ctx.app,'disableRendering',{get:()=>value,set:v=>{writes.push(v);value=v;}});f.call({action:'copy'});assert.deepEqual(writes,[]);f.target.locked=locked;const result=f.call({action:'paste'});assert.equal(!!result.error,locked);assert.deepEqual(writes,[true,false]);assert.equal(value,false);}
});
test('copy + consecutive image/video pastes isolate the instance and preserve original holders',()=>{
 const f=fixture();assert.ok(f.call({action:'copy'}).copied);assert.equal(f.call({action:'inspect'}).total,2);
 let r=f.call({action:'paste'});assert.equal(r.error,undefined);assert.equal(r.pasted.number,1);assert.equal(r.next,1);assert.notEqual(f.target.source,f.root);assert.equal(f.other.source,f.root);assert.equal(f.a.layer(1).source.name,'placeholder.jpg');assert.equal(f.target.name,'Owner template');assert.ok(f.target.comment.startsWith('Storylens Template Aliner v1'));
 const clone=f.target.source,rootCount=f.all.length;f.project.selection=[f.video];f.call({action:'copy'});r=f.call({action:'paste'});
 assert.equal(r.pasted.number,2);assert.equal(r.complete,true);assert.equal(r.pasted.short_video,'hold-last-frame');assert.equal(f.target.source,clone);
 assert.equal(f.all.length,rootCount+2,'reuse the exclusive root and scene; copy the shared holder and media wrapper');
 assert.equal(f.b.layer(1).source.name,'placeholder.jpg','the source instance retains its still-unfilled second holder');assert.equal(f.other.source,f.root);assert.equal(f.undo,0);
 assert.equal(f.call({action:'paste'}).code,'copy_paste_full');
});
test('missing copied file never advances cursor or changes a template',()=>{const f=fixture();f.call({action:'copy'});f.media.file.exists=false;const n=f.all.length,r=f.call({action:'paste'});assert.equal(r.code,'copy_paste_media');assert.equal(f.all.length,n);assert.equal(f.target.source,f.root);assert.equal(f.call({action:'inspect'}).next,0)});
test('plugin Undo refuses an unrelated native edit and never calls generic Undo',()=>{const f=fixture();f.call({action:'copy'});f.call({action:'paste'});const calls=[];f.ctx.app.findMenuCommandId=()=>0;f.ctx.app.executeCommand=id=>calls.push(id);const r=f.call({action:'undo'});assert.equal(r.code,'copy_paste_stale');assert.equal(calls.length,0);assert.equal(f.call({action:'inspect'}).next,1)});
test('AE menu IDs can remain cached; any later project revision blocks plugin Undo',()=>{const f=fixture();f.call({action:'copy'});f.call({action:'paste'});let calls=0;f.ctx.app.findMenuCommandId=()=>16;f.ctx.app.executeCommand=()=>calls++;f.project.revision++;assert.equal(f.call({action:'undo'}).code,'copy_paste_stale');assert.equal(calls,0)});
test('plugin Undo requires its own unchanged instance and exact native Undo title',()=>{const f=fixture(),before=f.target.comment;f.call({action:'copy'});f.call({action:'paste'});let executions=0;f.ctx.app.findMenuCommandId=label=>label==='Undo Copy Paste - next media slot'?16:0;f.ctx.app.executeCommand=id=>{assert.equal(id,16);executions++;f.target.source=f.root;f.target.comment=before};const r=f.call({action:'undo'});assert.equal(r.undone,true);assert.equal(r.next,0);assert.equal(executions,1);assert.equal(f.call({action:'undo'}).code,'copy_paste_stale');assert.equal(executions,1)});
test('project switch clears the private clipboard even if item IDs match',()=>{const f=fixture();f.call({action:'copy'});f.ctx.app.project={...f.project};assert.equal(f.call({action:'paste'}).code,'copy_paste_media')});
test('locked layer and ambiguous selection cannot modify project',()=>{const f=fixture();f.call({action:'copy'});f.target.locked=true;assert.equal(f.call({action:'paste'}).code,'copy_paste_target');f.target.locked=false;f.master.selectedLayers=[f.target,f.other];assert.equal(f.call({action:'paste'}).code,'copy_paste_target');assert.equal(f.target.source,f.root)});
test('unexpected target receipt is rejected before cloning',()=>{const f=fixture();f.call({action:'copy'});const n=f.all.length;assert.equal(f.call({action:'paste',expected:{layer_id:999,source_id:999,next:0}}).code,'copy_paste_stale');assert.equal(f.all.length,n)});
test('failure rolls back source, comment, created objects and cursor',()=>{const f=fixture();f.call({action:'copy'});const n=f.all.length,comment=f.target.comment;f.failNext(3);const r=f.call({action:'paste'});assert.equal(r.code,'copy_paste_native');assert.equal(r.rollback_complete,true);assert.equal(f.target.source,f.root);assert.equal(f.target.name,'Owner template');assert.equal(f.target.comment,comment);assert.equal(f.all.length,n);assert.equal(f.undo,0);assert.equal(f.call({action:'inspect'}).next,0)});

test('ambiguous holder refusal occurs before cloning and keeps pointer and source untouched',()=>{const f=fixture();f.a.layer(1).name='0001.jpg';f.a.layer(1).source.name='0001.jpg';f.media.name='0002.jpg';f.a.layers.add(f.media).name='0002.jpg';f.call({action:'copy'});const n=f.all.length,comment=f.target.comment,r=f.call({action:'paste'});assert.equal(r.code,'copy_paste_template');assert.equal(f.all.length,n);assert.equal(f.target.source,f.root);assert.equal(f.target.comment,comment);assert.equal(f.ctx.SLCopyPaste.history.length,0)});
test('duplicated filled instance forks before advancing another picture',()=>{const f=fixture();f.call({action:'copy'});f.call({action:'paste'});const filled=f.target.source;f.other.replaceSource(filled);f.other.comment=f.target.comment;f.master.selectedLayers=[f.other];const r=f.call({action:'paste'});assert.equal(r.pasted.number,2);assert.notEqual(f.other.source,filled);assert.equal(f.target.source,filled);assert.equal(f.call({action:'inspect'}).next,2)});
test('reset selects an earlier slot without replacing any media',()=>{const f=fixture();f.call({action:'copy'});f.call({action:'paste'});const n=f.all.length;let r=f.call({action:'reset',next:0});assert.equal(r.next,0);assert.equal(f.all.length,n);r=f.call({action:'paste'});assert.equal(r.pasted.number,1)});
test('structure change requires explicit reset and retains existing media',()=>{const f=fixture();f.call({action:'copy'});f.call({action:'paste'});f.target.source.layers.add(f.scene);assert.equal(f.call({action:'paste'}).code,'copy_paste_stale')});
test('Premiere receives an actionable limitation and never a host launch',()=>{const f=fixture();delete f.ctx.CompItem;assert.equal(f.call({action:'inspect'}).code,'copy_paste_host')});
test('a copied nested holder used elsewhere is forked while the exclusive root can be reused',()=>{const f=fixture();f.call({action:'copy'});f.call({action:'paste'});const before=f.target.source,r=f.call({action:'inspect'});const holder=f.all.find(c=>String(c.id)===r.slots[1].comp);f.root.layers.add(holder);const result=f.call({action:'paste'});assert.equal(result.error,undefined);assert.equal(f.target.source,before);assert.equal(f.root.layer(1).source,holder);const after=f.call({action:'inspect'});assert.notEqual(after.slots[1].comp,String(holder.id));assert.equal(holder.layer(1).source.name,'placeholder.jpg')});
test('nested locked holders keep their lock and animated outer properties',()=>{const f=fixture();f.a.layer(1).locked=true;f.a.layer(1).keys={scale:[[0,10],[5,120]],position:[[0,[1,2]],[5,[8,9]]]};f.scene.layer(3).locked=true;f.call({action:'copy'});const r=f.call({action:'paste'});assert.equal(r.error,undefined);const slot=f.call({action:'inspect'}).slots[0],owner=f.all.find(c=>String(c.id)===slot.comp);assert.equal(owner.layer(1).locked,true);assert.deepEqual(owner.layer(1).keys,f.a.layer(1).keys);assert.equal(f.a.layer(1).source.name,'placeholder.jpg')});

test('Explorer file paste imports media and retains the timeline target when import changes activeItem',()=>{
 const f=fixture();f.ctx.File=function(path){this.fsName=path;this.exists=true};f.ctx.ImportOptions=function(file){this.file=file};
 f.project.importFile=()=>{const media=new f.ctx.FootageItem('outside.png');f.project.activeItem=media;return media};
 const r=f.call({action:'pasteFiles',paths:['D:/outside.png'],request_id:'file-one'});assert.equal(r.error,undefined);assert.equal(r.pasted.number,1);assert.equal(f.other.source,f.root);
 const count=f.all.length,again=f.call({action:'pasteFiles',paths:['D:/outside.png'],request_id:'file-one'});assert.equal(again.pasted.number,1);assert.equal(f.all.length,count);
});

test('unexpected native failures return an action message with diagnostics kept separately',()=>{
 const f=fixture();Object.defineProperty(f.project,'selection',{get(){throw Error('TypeError: corrupt native media')}});
 const r=f.call({action:'copy'});assert.doesNotMatch(r.error,/TypeError/);assert.match(r.details,/TypeError/);
});

test('non-picture text and decorative comps are isolated so named expressions use this instance',()=>{
 const f=fixture(),text=new f.ctx.CompItem('Titles'),art=new f.ctx.CompItem('Texture Background');
 const title=text.layers.add(f.media);title.expressions=[{canSetExpression:true,expression:'comp("Final").width',expressionEnabled:true}];
 art.layers.add(text);f.root.layers.add(art);f.call({action:'copy'});const result=f.call({action:'paste'});assert.equal(result.error,undefined);
 const clonedArt=f.target.source.layer(1).source;assert.notEqual(clonedArt,art);const clonedText=clonedArt.layer(1).source;assert.notEqual(clonedText,text);
 assert.match(clonedText.layer(1).expressions[0].expression,/Final \[Copy Paste/);assert.equal(title.expressions[0].expression,'comp("Final").width');
});
test('legacy isolated templates also remap their unsuffixed controller names',()=>{
 const f=fixture();f.root.name='Final [Copy Paste 123]';const title=f.root.layer(1);title.expressions=[{canSetExpression:true,expression:'comp("Final").width',expressionEnabled:true}];
 f.call({action:'copy'});f.call({action:'paste'});const expression=f.target.source.layer(1).expressions[0].expression,calls=[];vm.runInNewContext(expression,{comp:name=>{calls.push(name);return {width:1920}}});
 assert.deepEqual(calls,[f.target.source.name]);
});
test('native source capture reuses the selected item ID for image and video without importing',()=>{
 const f=fixture(),before=f.all.filter(x=>x instanceof f.ctx.FootageItem).map(x=>x.id);
 for(const item of [f.media,f.video]){f.project.selection=[item];assert.equal(f.call({action:'copy'}).clipboard.id,item.id);const r=f.call({action:'paste'});const holder=f.all.find(x=>String(x.id)===r.slots[r.next-1].comp);assert.equal(holder.layer(1).source.layer(1).source,item);}
 assert.deepEqual(f.all.filter(x=>x instanceof f.ctx.FootageItem).map(x=>x.id),before);
});
test('failed native source capture invalidates a previously copied image',()=>{const f=fixture();f.call({action:'copy'});f.project.selection=[f.root];assert.equal(f.call({action:'copy'}).code,'copy_paste_media');assert.equal(f.call({action:'paste'}).code,'copy_paste_media');});

test('busy native Undo keeps its record and reports no confirmed change',()=>{const f=fixture();f.call({action:'copy'});f.call({action:'paste'});f.ctx.app.findMenuCommandId=()=>16;f.ctx.app.executeCommand=()=>{};const r=f.call({action:'undo'});assert.equal(r.code,'copy_paste_native');assert.match(r.error,/did not undo/);assert.equal(f.ctx.SLCopyPaste.history.length,1)});

test('owned Undo activates the saved composition before executing native Undo',()=>{const f=fixture(),before=f.target.comment;f.call({action:'copy'});f.call({action:'paste'});let active=false;f.master.openInViewer=()=>{active=true};f.ctx.app.findMenuCommandId=()=>16;f.ctx.app.executeCommand=()=>{if(active){f.target.source=f.root;f.target.comment=before}};const r=f.call({action:'undo'});assert.equal(r.undone,true)});


test('variable frame rate short video keeps a real-time end key before the held tail',()=>{const f=fixture();f.video.duration=3.1376064545;f.video.frameRate=26.72;f.project.selection=[f.video];f.call({action:'copy'});const r=f.call({action:'paste'});assert.equal(r.error,undefined);const wrapper=f.all.find(c=>String(c.comment).startsWith('Storylens Copy Paste media v1|'));const keys=wrapper.layer(1).remap.keys;assert.equal(keys.length,3);assert.ok(keys[1][0]>3.08&&keys[1][0]<3.12);assert.equal(keys[1][1],keys[2][1]);assert.equal(keys[2][0],10)});


test('copied Project footage leaves the placed template recoverable without opening nested comps',()=>{
 const f=fixture();f.call({action:'copy'});f.project.activeItem=f.media;
 const r=f.call({action:'paste'});assert.equal(r.error,undefined);assert.equal(r.layer_id,f.target.id);assert.equal(r.pasted.number,1);assert.equal(f.other.source,f.root);
});

test('ambiguous background timeline selections refuse before any template changes',()=>{
 const f=fixture();f.call({action:'copy'});f.other.comment=f.target.comment;f.master.selectedLayers=[f.target,f.other];f.project.activeItem=f.media;const n=f.all.length;
 const r=f.call({action:'paste'});assert.equal(r.code,'copy_paste_target');assert.equal(f.all.length,n);assert.equal(f.target.source,f.root);
});

test('Project template selection resolves its placed instance by source identity',()=>{
 const f=fixture();f.call({action:'copy'});f.project.activeItem=f.root;const r=f.call({action:'paste'});assert.equal(r.layer_id,f.target.id);assert.equal(r.error,undefined);
});

test('remembered template cannot override a different explicit Project comp',()=>{
 const f=fixture();f.call({action:'inspect'});f.call({action:'copy'});f.project.activeItem=f.a;const n=f.all.length;
 const r=f.call({action:'paste'});assert.equal(r.code,'copy_paste_target');assert.equal(f.all.length,n);
});

test('legacy Fit request still covers the whole placeholder without changing authored outer transforms',()=>{
 const f=fixture();f.call({action:'copy'});const r=f.call({action:'paste',fit:'fit'});assert.equal(r.pasted.fit,'fill');
 const wrapper=f.all.find(c=>String(c.comment).startsWith('Storylens Copy Paste media v1|'));
 const scale=wrapper.layer(1).keys['ADBE Scale'];assert.ok(scale);const bg=wrapper.layer(wrapper.numLayers),fill=bg.keys['ADBE Scale'];assert.ok(f.media.width*fill[0]/100>=wrapper.width);assert.ok(f.media.height*fill[1]/100>=wrapper.height);
});


test('face bounds stay with the captured media and cannot attach after another Copy',()=>{
 const f=fixture(),first=f.call({action:'copy'});f.project.selection=[f.video];f.call({action:'copy'});
 const r=f.call({action:'rememberFraming',clipboard:first.clipboard,framing:{version:1,width:1000,height:600,faces:[]}});assert.equal(r.code,'copy_paste_stale');assert.equal(f.ctx.SLCopyPaste.clipboard.id,f.video.id);
});


test('optional framing failures cannot block paste or core Copy and Undo commands',()=>{
 const f=fixture();delete f.ctx.SLCopyPasteFramingModel;f.ctx.SLCopyPasteViewport={measure(){throw Error('bad optional probe')}};
 assert.equal(f.call({action:'copy'}).copied,true);const r=f.call({action:'paste'});assert.equal(r.error,undefined);assert.equal(r.framing.method,'whole-image');assert.match(r.framing.warnings.join(' '),/holder framing/);
 const before=f.ctx.SLCopyPaste.history.at(-1).before;f.ctx.app.findMenuCommandId=()=>16;f.ctx.app.executeCommand=()=>{f.target.source=before.root;f.target.comment=before.comment;f.target.name=before.name};assert.equal(f.call({action:'undo'}).undone,true);
});

test('native core contains no optional framing math or AE reserved property key',()=>{
 const core=fs.readFileSync('editor_plugins/copy-paste/model.js','utf8');assert.doesNotMatch(core,/function reframe|protected\s*:/);
 const optional=fs.readFileSync('editor_plugins/copy-paste/framing-model.js','utf8');assert.doesNotMatch(optional,/\b(?:protected|private|public)\s*:/);assert.match(optional,/subject_bounds/);
});


test('Undo explicitly activates the returned composition viewer while CEP has focus',()=>{
 const f=fixture(),before=f.target.comment;f.call({action:'copy'});f.call({action:'paste'});let active=false;
 f.master.openInViewer=()=>({setActive:()=>{active=true}});f.ctx.app.findMenuCommandId=()=>16;f.ctx.app.executeCommand=()=>{if(active){f.target.source=f.root;f.target.comment=before}};
 const r=f.call({action:'undo'});assert.equal(active,true);assert.equal(r.undone,true);
});


test('unnamed layer labels retain explicit image roles in footage source names',()=>{
 const g={1:{name:'Images',layers:[{index:1,name:'001',sourceName:'Photo Placeholder 1.jpg',source:2,kind:'media',start:0},{index:2,name:'002',sourceName:'Photo Placeholder 2.jpg',source:3,kind:'media',start:1}]}};
 assert.equal(M.scan(g,1).slots.length,2);
});

test('picture plus a control solid is not incorrectly rejected as multiple picture sources',()=>{
 const g={1:{name:'Image 1',layers:[{index:1,name:'0001.jpg',source:2,kind:'media',start:0},{index:2,name:'Black Solid 1',source:3,kind:'media',solid:true,start:0}]}};
 const r=M.scan(g,1);assert.equal(r.slots.length,1);assert.deepEqual(r.slots[0].layers,[1]);
});

test('new media wrappers are created directly in their existing template folder, avoiding root insertion',()=>{
 const f=fixture();let added=0;const add=f.project.items.addComp;f.a.parentFolder={id:23,items:{addComp(...args){added++;const c=add(...args);c.parentFolder=f.a.parentFolder;return c}}};f.b.parentFolder=f.a.parentFolder;
 f.call({action:'copy'});const r=f.call({action:'paste'});assert.equal(r.error,undefined);assert.equal(added,1);
});


test('real matte brush assets are not picture slots and named inner image remains selectable',()=>{
 const g={1:{name:'Image_Matte_09',layers:[{index:1,name:'Brush 05.png',source:7,kind:'media',start:0},{index:2,name:'Brush 07.png',source:8,kind:'media',start:0},{index:3,name:'Image 09',source:2,kind:'comp',start:0}]},2:{name:'Image 09',layers:[]}};
 const r=M.scan(g,1);assert.equal(r.slots.length,1);assert.equal(r.slots[0].comp,'2');
});

test('real text-and-control-solid photo comp is not mistaken for an ambiguous picture holder',()=>{
 const g={1:{name:'Photo 04',hasText:true,layers:[{index:2,name:'Pale Green Solid 1',source:7,kind:'media',solid:true,start:0},{index:3,name:'Dark Green Solid 1',source:8,kind:'media',solid:true,start:0}]}};
 assert.equal(M.scan(g,1).slots.length,0);
});

test('labelled photo canvases are one slot and remain one after a wrapper is inserted',()=>{const g={1:{name:'Photo 04',hasText:true,placeholderCanvas:true,layers:[{index:2,name:'Pale Green Solid 1',source:2,kind:'media',solid:true,start:0},{index:3,name:'Dark Green Solid 1',source:3,kind:'media',solid:true,start:0}]}};let s=M.scan(g,1);assert.equal(s.slots.length,1);assert.equal(s.slots[0].empty,true);const key=s.slots[0].key;g[1].layers.unshift({index:1,name:'Copy Paste 1 - image',source:4,kind:'media',wrapped:true,start:0});s=M.scan(g,1);assert.equal(s.slots.length,1);assert.equal(s.slots[0].empty,false);assert.equal(s.slots[0].key,key);});
test('photo controllers and decorative clouds/paper do not become picture slots',()=>{const g={1:{name:'Image scene',layers:[{index:1,name:'Photo Controller',source:2,kind:'media',solid:true,nullLayer:true,start:0},{index:2,name:'Paper_2.jpg',source:3,kind:'media',start:0},{index:3,name:'Image Holder',source:4,kind:'comp',start:0},{index:4,name:'Cloud_1',source:5,kind:'comp',start:0}]},4:{name:'Image Holder',layers:[{index:1,name:'Image Holder.jpg',source:6,kind:'media',start:0}]},5:{name:'Cloud_1',structuralHolder:true,layers:[{index:1,name:'Cloud_1.png',source:7,kind:'media',start:0}]}};assert.deepEqual(M.scan(g,1).slots.map(x=>x.comp),['4']);});
test('a detector-only removal preserves native slot progress without rewriting an earlier picture',()=>{const f=fixture();f.call({action:'copy'});let r=f.call({action:'paste'});assert.equal(r.error,undefined);const saved=M.state(f.target.comment);f.target.comment=M.writeState(f.target.comment,{...saved,signature:'999:1;'+saved.signature,next:saved.next+1});r=f.call({action:'inspect'});assert.equal(r.error,undefined);assert.equal(r.next,1);assert.equal(r.total,2);});

test('exclusive feature-owned title branches are reused while the shared picture holder is forked',()=>{
 const f=fixture();f.other.replaceSource(f.b);const owner=f.target.id;
 f.root.name+=' [SLTT '+owner+'-123-root]';f.scene.name+=' [SLTT '+owner+'-123-1]';
 const before=f.all.length;f.call({action:'copy'});const r=f.call({action:'paste'});
 assert.equal(r.error,undefined);assert.equal(f.target.source,f.root);assert.equal(f.root.layer(1).source,f.scene);
 assert.equal(f.all.length,before+2,'only the untouched holder and media wrapper need allocation');
 assert.equal(f.a.layer(1).source.name,'placeholder.jpg');assert.notEqual(f.scene.layer(3).source,f.a);
 assert.equal(r.performance.reused_private_comps,2);
});

test('an owner marker cannot reuse a branch that another timeline also uses',()=>{
 const f=fixture(),owner=f.target.id;f.root.name+=' [SLTT '+owner+'-123-root]';f.scene.name+=' [SLTT '+owner+'-123-1]';
 f.call({action:'copy'});const r=f.call({action:'paste'});assert.equal(r.error,undefined);
 assert.notEqual(f.target.source,f.root);assert.equal(f.other.source,f.root);assert.equal(f.root.layer(1).source,f.scene);
});

test('a failure restores reused native edges, expressions and root metadata',()=>{
 const f=fixture();f.other.replaceSource(f.b);const owner=f.target.id;
 f.root.name+=' [SLTT '+owner+'-123-root]';f.scene.name+=' [SLTT '+owner+'-123-1]';
 const originalComment=f.root.comment,expression='comp("Image_01").width';f.scene.layer(1).expressions=[{canSetExpression:true,expression,expressionEnabled:true}];
 const before=f.all.length;f.call({action:'copy'});f.failNext(2);const r=f.call({action:'paste'});
 assert.equal(r.rollback_complete,true);assert.equal(f.target.source,f.root);assert.equal(f.root.comment,originalComment);
 assert.equal(f.scene.layer(3).source,f.a);assert.equal(f.scene.layer(1).expressions[0].expression,expression);assert.equal(f.all.length,before);
});
