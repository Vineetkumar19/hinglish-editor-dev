const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),os=require('os'),path=require('path'),vm=require('vm');
const {createLibrary,nativeRequest}=require('../editor_plugins/animation-presets/bridge.cjs');
test('CC classification follows dedicated folders and names in mixed packs; everything else is Effects',()=>{
 const {category}=require('../editor_plugins/animation-presets/bridge.cjs');
 for(const name of ['cc/bg glow.ffx','cc1/cloudy.ffx','vineet fav cc/sharp + glow.ffx',"Pack/CC's/BROWN.ffx",'Pack/CCs/1.ffx','vineet preset cc.ffx','Premium CC1.ffx','Pack/Color Correction/Warm.ffx','LUTs/Cinema.ffx'])assert.equal(category(name),'cc',name);
 for(const name of ['slide down.ffx','zoom in.ffx','success.ffx','Pack/Zooms/Zoom.ffx','Pack/Text Glow.ffx','account.ffx'])assert.equal(category(name),'effects',name);
});
test('mixed folders and Extras retain separate CC and Effects entries on every fresh scan',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'sl-cc-'));
 try{fs.mkdirSync(path.join(root,'Mixed'));for(const name of ['vineet preset cc.ffx','slide down.ffx','Mixed/JE Cream CC.ffx','Mixed/Zoom In.ffx'])fs.writeFileSync(path.join(root,name),'x');const lib=createLibrary(root),first=lib.prepare({action:'catalog'}).result.tree;for(const folder of first.folders){assert.equal(folder.presets.filter(p=>p.category==='cc').length,1);assert.equal(folder.presets.filter(p=>p.category==='effects').length,1);}fs.writeFileSync(path.join(root,'Mixed','New CC.ffx'),'x');assert.equal(lib.prepare({action:'catalog'}).result.tree.folders[0].presets.filter(p=>p.category==='cc').length,2);}finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('folder names, Extras, nested presets, duplicates, new files and stale signatures',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'sl-ffx-'));
 try{
  fs.mkdirSync(path.join(root,'Pack 10','Sub'),{recursive:true});fs.mkdirSync(path.join(root,'Pack 2'));
  fs.writeFileSync(path.join(root,'slide down.ffx'),'one');fs.writeFileSync(path.join(root,'pack.zip'),'zip');fs.writeFileSync(path.join(root,'Pack 10','Sub','slide down.FFX'),'two');
  const lib=createLibrary(root),first=lib.prepare({action:'catalog'}).result;
  assert.equal(first.total,2);assert.deepEqual(first.tree.folders.map(f=>f.name),['Pack 2','Pack 10','Extras']);
  const preset=first.tree.folders[2].presets[0];assert.equal(first.tree.folders[2].other[0].name,'pack.zip');
  assert.notEqual(preset.id,first.tree.folders[1].folders[0].presets[0].id);
  assert.equal(lib.prepare({action:'apply',...preset,target:'selected'}).payload.name,'slide down');
  fs.writeFileSync(path.join(root,'slide down.ffx'),'modified-longer');assert.throws(()=>lib.prepare({action:'apply',...preset,target:'selected'}),/changed/);
  fs.writeFileSync(path.join(root,'Pack 2','zoom in.ffx'),'new');assert.equal(lib.prepare({action:'catalog'}).result.total,3);
  assert.throws(()=>lib.prepare({action:'apply',id:'../bad',target:'selected'}),/changed/);
  assert.throws(()=>lib.prepare({action:'apply',...preset,target:'anything'}),/Choose/);
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
function nativeFixture(){
 const all=[],calls=[];class AVLayer{constructor(name){this.name=name;this.selected=true;this.locked=false;all.push(this);}applyPreset(f){calls.push({file:f.path,targets:all.filter(l=>l.selected).map(l=>l.name),time:comp.time});}moveBefore(layer){this.before=layer;}}
 class CompItem{constructor(){this.width=1920;this.height=1080;this.duration=30;this.pixelAspect=1;this.time=7;this.layers={addSolid:(color,name,w,h,pa,duration)=>{const l=new AVLayer(name);l.sourceArgs={w,h,pa,duration};return l;}};}get selectedLayers(){return all.filter(l=>l.selected);}get numLayers(){return all.length;}layer(i){return all[i-1];}}
 const comp=new CompItem(),one=new AVLayer('video'),two=new AVLayer('text');let begins=0,ends=0;
 const ctx={JSON,Error,String,CompItem,AVLayer,File:function(p){this.path=p;this.exists=true;},app:{project:{activeItem:comp},beginUndoGroup(){begins++;},endUndoGroup(){ends++;}},storylensProjectId:()=> 'test-project'};vm.createContext(ctx);vm.runInContext(fs.readFileSync('editor_plugins/animation-presets/host.jsx','utf8'),ctx);
 return {comp,one,two,all,calls,ctx,run:p=>JSON.parse(ctx.storylensAnimationPresets(p)),groups:()=>[begins,ends]};
}
const apply={action:'apply',path:'D:/Editing/after effects presets/slide down.ffx',name:'slide down',target:'selected'};
test('one native call applies once to selected targets at playhead and retains selection',()=>{const f=nativeFixture(),r=f.run(apply);assert.equal(r.ok,true);assert.equal(f.calls.length,1);assert.deepEqual(f.calls[0].targets,['video','text']);assert.equal(f.calls[0].time,7);assert.equal(f.one.selected,true);assert.equal(f.two.selected,true);assert.deepEqual(f.groups(),[1,1]);});
test('new adjustment isolates selection, matches comp, starts at playhead above selected layer',()=>{const f=nativeFixture(),r=f.run({...apply,target:'adjustment'}),made=f.all[2];assert.equal(r.adjustment,true);assert.equal(made.adjustmentLayer,true);assert.equal(made.inPoint,7);assert.equal(made.outPoint,30);assert.equal(made.before,f.one);assert.deepEqual(f.calls[0].targets,['Adjustment - slide down']);assert.equal(f.one.selected,false);assert.equal(made.selected,true);});
test('standalone adjustment does not apply a preset',()=>{const f=nativeFixture(),r=f.run({action:'adjustment'});assert.equal(r.ok,true);assert.equal(f.calls.length,0);assert.equal(f.all[2].selected,true);});
test('locked, empty selection, invalid path and unsupported targets fail before mutation',()=>{for(const kind of ['locked','empty','path','target','action']){const f=nativeFixture();if(kind==='locked')f.one.locked=true;if(kind==='empty'){f.one.selected=false;f.two.selected=false;}const p={...apply,...(kind==='path'?{path:'D:/Editing/after effects presets/../outside.ffx'}:{}),...(kind==='target'?{target:'all'}:{}),...(kind==='action'?{action:'bad'}:{})};const r=f.run(p);assert.equal(r.code,'animation_presets');assert.deepEqual(f.groups(),[0,0]);assert.equal(f.calls.length,0);assert.equal(f.comp.time,7);if(kind!=='empty')assert.equal(f.two.selected,true);}});
test('native partial failure is explicit, restores selection and closes undo group',()=>{const f=nativeFixture();f.one.applyPreset=()=>{throw Error('third party plugin unavailable');};const r=f.run(apply);assert.equal(r.partial,true);assert.match(r.error,/Check the timeline/);assert.match(r.details,/third party/);assert.deepEqual(f.groups(),[1,1]);assert.equal(f.one.selected,true);});
test('generated native request parses and shell and panel wire only named operation',()=>{new vm.Script(nativeRequest(process.cwd(),apply));for(const name of ['editor_plugins/shared/cep-shell.js','editor_plugins/after-effects-cep/js/main.js','hinglish_app/static/animation-presets.js','hinglish_app/static/editor-panel.js']){const code=fs.readFileSync(name,'utf8');new vm.Script(code);assert.match(code,/animationPresets/);}const html=fs.readFileSync('hinglish_app/static/editor-panel.html','utf8');assert.match(html,/id="animationPresetSection"/);assert.ok(html.indexOf('animation-presets.js')<html.indexOf('editor-panel.js'));});
test('UI browses folders and Extras without native mutations; preset click and adjustment button use correct targets',async()=>{
 const nodes={},calls=[],errors=[];let timer,focus;
 function el(id){return nodes[id]||(nodes[id]={value:id==='animationPresetTarget'?'selected':'',children:[],setAttribute(k,v){this[k]=v;},replaceChildren(...x){this.children=x;}});}
 let n=0;const ctx={document:{getElementById:el,createElement:()=>el('b'+(++n))},window:{addEventListener:(type,fn)=>{if(type==='focus')focus=fn;}},setInterval:(fn,ms)=>{assert.equal(ms,5000);timer=fn;}};
 vm.runInNewContext(fs.readFileSync('hinglish_app/static/animation-presets.js','utf8'),ctx);
 const catalog={tree:{id:'root',name:'Presets',presets:[],other:[],folders:[{id:'@extras',name:'Extras',folders:[],other:[],presets:[{id:'x',signature:'s',name:'slide down',category:'effects'}]}]},total:1};
 const view=ctx.window.storylensAnimationPresets({native:async(action,p)=>{calls.push(p);return p.action==='catalog'?catalog:{ok:true,time:7,layers:1,adjustment:p.target==='adjustment'};},isBusy:()=>false,clearError(){},showError:e=>errors.push(e)});
 view.open();await new Promise(r=>setImmediate(r));assert.equal(calls.length,1);assert.equal(calls[0].action,'catalog');assert.equal(nodes.animationPresetFiles.children.length,0);assert.equal(nodes.animationPresetCC['aria-pressed'],'true');assert.match(nodes.animationPresetCount.textContent,/0 CC/);
 nodes.animationPresetEffects.onclick();assert.match(nodes.animationPresetCount.textContent,/1 Effects/);assert.equal(nodes.animationPresetEffects['aria-pressed'],'true');nodes.animationPresetFiles.children[0].onclick();assert.equal(calls.length,1);
 await nodes.animationPresetFiles.children[0].onclick();assert.equal(calls[1].target,'selected');assert.match(nodes.animationPresetStatus.textContent,/applied/);
 nodes.animationPresetTarget.value='adjustment';await nodes.animationPresetFiles.children[0].onclick();assert.equal(calls[2].target,'adjustment');
 await nodes.animationPresetCreate.onclick();assert.equal(calls[3].action,'adjustment');assert.equal(nodes.animationPresetTarget.value,'selected');
 await focus();await timer();assert.equal(calls.length,6);view.hide();await timer();assert.equal(calls.length,6);assert.equal(errors.length,0);
});
test('CEP reads real library without native eval; rejects foreign origins and nonce',async()=>{
 let receive;const responses=[],scripts=[],bridge=require('../editor_plugins/animation-presets/bridge.cjs'),nodes={storylensPanel:{contentWindow:{postMessage:r=>responses.push(r)}},shellStatus:{},reconnect:{}};
 const c={URL,Date,Math,JSON,String,Error,require:name=>name==='path'?path:bridge,fetch:async()=>({ok:true}),document:{getElementById:id=>nodes[id],documentElement:{dataset:{host:'aftereffects'}}},window:{HINGLISH_APP_ROOT:process.cwd(),HINGLISH_BRIDGE:'http://127.0.0.1:8765',addEventListener:(kind,fn)=>{if(kind==='message')receive=fn;},__adobe_cep__:{evalScript:(s,cb)=>{scripts.push(s);cb('{"ok":true}');}}}};
 vm.runInNewContext(fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8'),c);await new Promise(r=>setImmediate(r));
 const nonce=decodeURIComponent(/nonce=([^&]+)/.exec(nodes.storylensPanel.src)[1]),e={source:nodes.storylensPanel.contentWindow,origin:'http://127.0.0.1:8765',data:{type:'storylens-host-request',id:'read',nonce,action:'animationPresets',payload:{action:'catalog'}}};
 await receive(e);assert.ok(responses[0].result.total>0);assert.equal(scripts.length,0);
 await receive({...e,origin:'https://foreign.invalid'});await receive({...e,data:{...e.data,nonce:'wrong'}});assert.equal(responses.length,1);
 const preset=responses[0].result.tree.folders.find(f=>f.name==='Extras').presets[0];await receive({...e,data:{...e.data,payload:{action:'apply',...preset,target:'selected'}}});assert.equal(scripts.length,1);assert.match(scripts[0],/storylensAnimationPresets/);
});
