const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const M=require('../editor_plugins/copy-paste/framing-model.js');
function protectedPixels(p,sw,sh,par=1){const b=p.subject_bounds,s=p.scale/100;return [p.position[0]+(b[0]-.5)*sw*s*par,p.position[1]+(b[1]-.5)*sh*s,p.position[0]+(b[2]-.5)*sw*s*par,p.position[1]+(b[3]-.5)*sh*s]}
function safe(p,sw,sh,par=1){const q=protectedPixels(p,sw,sh,par),v=p.viewport;assert.ok(q[0]>=v[0]-.001);assert.ok(q[1]>=v[1]-.001);assert.ok(q[2]<=v[2]+.001);assert.ok(q[3]<=v[3]+.001)}
const face=box=>({version:1,faces:[{box}]});
test('portrait player head is protected while the lower helmet may crop',()=>{const p=M.reframe(1280,720,1,800,1200,1,face([.27,.01,.7,.24]));safe(p,800,1200);assert.equal(p.method,'face-safe');assert.ok(p.position[1]>360);assert.equal(p.background,false)});
test('wide champion group in a portrait holder keeps all heads with full blurred edge fill',()=>{const p=M.reframe(720,1280,1,1920,1080,1,{faces:[{box:[.02,.1,.15,.28]},{box:[.8,.05,.98,.3]}]});safe(p,1920,1080);assert.equal(p.background,true);assert.ok(p.scale<p.background_scale)});
test('nested off-centre visible crop determines framing rather than full source canvas',()=>{const p=M.reframe(1920,1080,1,800,1200,1,face([.2,.01,.8,.25]),[700,60,1250,600]);safe(p,800,1200);assert.deepEqual(p.viewport,[700,60,1250,600]);assert.equal(p.background,true)});
test('no detected face keeps the complete image instead of silently guessing a head location',()=>{const p=M.reframe(1280,720,1,800,1200,1,{faces:[]});safe(p,800,1200);assert.equal(p.method,'whole-image');assert.equal(p.background,true)});
test('pixel aspect and moving-video face union are protected',()=>{const p=M.reframe(720,576,1.2,1920,1080,1,{video_sampled:true,faces:[{box:[.1,.1,.3,.4]},{box:[.7,.15,.9,.45]}]});safe(p,1920,1080,1/1.2);assert.equal(p.video_sampled,true)});
test('invalid/non-finite face coordinates stop rather than corrupt native transforms',()=>{assert.throws(()=>M.reframe(1280,720,1,800,1200,1,face([NaN,.1,.8,.3])),e=>e.code==='copy_paste_media')});
test('safe rectangle lies inside a rotated projected viewport',()=>{const c={};vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/copy-paste/framing.jsx','utf8'),c);const poly=[[100,0],[300,100],[200,300],[0,200]],r=c.SLCopyPasteViewport.rect(poly),box=[[r[0],r[1]],[r[2],r[1]],[r[2],r[3]],[r[0],r[3]]];const clipped=c.SLCopyPasteViewport.clip(box,poly);let a=0;for(let i=0;i<clipped.length;i++){const b=clipped[(i+1)%clipped.length];a+=clipped[i][0]*b[1]-b[0]*clipped[i][1];}assert.ok(Math.abs(Math.abs(a/2)-(r[2]-r[0])*(r[3]-r[1]))<.01);assert.ok(r[2]>r[0]&&r[3]>r[1]);});
test('dense mask vertices cannot bias the safe rectangle into a small corner',()=>{
 const c={};vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/copy-paste/framing.jsx','utf8'),c);const polygon=[[0,0],[100,0],[100,100]];for(let x=99;x>=0;x--)polygon.push([x,100]);
 const r=c.SLCopyPasteViewport.rect(polygon);assert.ok(r[0]<.01&&r[1]<.01&&r[2]>99.99&&r[3]>99.99);
});

for(const probeType of ['text','shape'])test(probeType+' viewport expression follows nested transforms, source time and camera mapping then removes its probe',()=>{
 let projectionCalls=0,evaluations=0;
 class Comp{constructor(name,w,h){this.id=name;this.name=name;this.width=w;this.height=h;this.duration=10;this.children=[];this.selectedLayers=[];this.layers={addText:()=>{const probe={remove:()=>this.children.splice(this.children.indexOf(probe),1),property:()=>({property:()=>point})};this.children.unshift(probe);return probe}}}get numLayers(){return this.children.length}layer(i){return this.children[i-1]}}
 const master=new Comp('master',1280,720),root=new Comp('root',1000,1000),holder=new Comp('holder',1000,1000),media={width:1600,height:900};
 function layer(comp,source,offset=[0,0],threeD=false){const l={id:comp.id+'-layer',source,containingComp:comp,startTime:0,inPoint:0,outPoint:10,stretch:100,enabled:true,threeDLayer:threeD,
  get index(){return comp.children.indexOf(this)+1},sourceTime:t=>t,fromComp:p=>[p[0]+offset[0],p[1]+offset[1]],fromCompToSurface:p=>{projectionCalls++;return [p[0]+offset[0],p[1]+offset[1]]},property:name=>name==='ADBE Mask Parade'?{numProperties:0}:{property:()=>({valueAtTime:()=>100})}};comp.children.push(l);return l}
 const top=layer(master,root,[200,100],true);layer(root,holder);layer(holder,media);master.selectedLayers=[top];
 const point={expression:'',expressionError:'',valueAtTime:t=>{evaluations++;const value=vm.runInNewContext(point.expression,{thisComp:master,time:t,createPath:vertices=>({vertices})});return probeType==='shape'?value:{text:value};}};
 if(probeType==='shape'){master.layers.addText=()=>{throw Error('Shape projection must not start the text renderer');};master.layers.addShape=()=>{const probe={remove:()=>master.children.splice(master.children.indexOf(probe),1),property:()=>({addProperty:()=>({property:()=>point})})};master.children.unshift(probe);return probe;};}
 const c={CompItem:Comp,SLCopyPaste:{json:JSON.stringify}};vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/copy-paste/framing.jsx','utf8'),c);
 const result=c.SLCopyPasteViewport.measure({comp:master,root,layer:top},{comp:'holder',layers:[1],ancestors:['root','holder']},1600,900);
 assert.equal(result.method,'native-projected-viewport');assert.equal(result.samples,9);assert.ok(projectionCalls>=9);assert.equal(evaluations,1,'Nine explicit time samples share one native expression evaluation');assert.equal(master.children.length,1);assert.equal(top.selected,true);
 assert.ok(Math.abs(result.rect[0]-200)<.01);assert.ok(Math.abs(result.rect[1]-100)<.01);assert.ok(Math.abs(result.rect[2]-1000)<.01);assert.ok(Math.abs(result.rect[3]-820)<.01);
});

test('ordinary animated 2D holders use native transform math without adding any probe layer',()=>{
 class Comp{constructor(id,w,h){Object.assign(this,{id,name:id,width:w,height:h,pixelAspect:1,duration:10,children:[],selectedLayers:[],layers:{addText:()=>{throw Error('Slow probe must not run for 2D');}}});}get numLayers(){return this.children.length}layer(i){return this.children[i-1]}}
 const master=new Comp('master',1000,1000),holder=new Comp('holder',1000,1000),media={width:1000,height:1000,pixelAspect:1};
 function layer(comp,source,position){const values={'ADBE Anchor Point':[500,500],'ADBE Position':position,'ADBE Scale':[100,100],'ADBE Rotate Z':0,'ADBE Skew':0,'ADBE Opacity':100};const l={source,containingComp:comp,startTime:0,stretch:100,inPoint:0,outPoint:10,enabled:true,threeDLayer:false,autoOrient:0,get index(){return comp.children.indexOf(this)+1},property:n=>n==='ADBE Mask Parade'?{numProperties:0}:n==='ADBE Transform Group'?{property:k=>({valueAtTime:t=>typeof values[k]==='function'?values[k](t):values[k]})}:null};comp.children.push(l);return l;}
 const top=layer(master,holder,t=>[500+t*10,500]);layer(holder,media,[500,500]);master.selectedLayers=[top];
 const context={CompItem:Comp,SLCopyPaste:{json:JSON.stringify}};vm.createContext(context);vm.runInContext(fs.readFileSync('editor_plugins/copy-paste/framing.jsx','utf8'),context);
 const r=context.SLCopyPasteViewport.measure({comp:master,root:holder,layer:top},{comp:'holder',layers:[1],ancestors:['holder']},1000,1000);
 assert.equal(r.method,'native-2d-viewport');assert.equal(r.samples,9);assert.equal(master.children.length,1);assert.ok(Math.abs(r.rect[0])<.1);assert.ok(Math.abs(r.rect[2]-904)<.1,'Keep the moving crop at all nine sample times');
});
