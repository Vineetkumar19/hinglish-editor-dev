'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(){
 let begins=0,ends=0;
 class Property{
  constructor(keys=[],spatial=false){this.keys=keys.map(([t,v,selected=true])=>({t,v,selected,inType:'BEZIER',outType:'BEZIER',inEase:[{speed:10,influence:40}],outEase:[{speed:20,influence:60}],inT:[-2,0],outT:[3,0],label:2}));this.isSpatial=spatial;this.canVaryOverTime=true;this.canSetExpression=true;this.expression='';this.propertyType='PROPERTY';this.propertyValueType=spatial?'TwoD_SPATIAL':'OneD';this.value=0;this.name='Property';}
  get numKeys(){return this.keys.length;}get selectedKeys(){return this.keys.map((k,i)=>k.selected?i+1:0).filter(Boolean);}
  keyTime(k){return this.keys[k-1].t;}keyValue(k){return this.keys[k-1].v;}
  keyInInterpolationType(k){return this.keys[k-1].inType;}keyOutInterpolationType(k){return this.keys[k-1].outType;}
  keyInTemporalEase(k){return this.keys[k-1].inEase;}keyOutTemporalEase(k){return this.keys[k-1].outEase;}
  keyTemporalAutoBezier(){return false;}keyTemporalContinuous(){return false;}
  keySpatialAutoBezier(){return false;}keySpatialContinuous(){return false;}keyRoving(){return false;}
  keyInSpatialTangent(k){return this.keys[k-1].inT;}keyOutSpatialTangent(k){return this.keys[k-1].outT;}keyLabel(k){return this.keys[k-1].label;}
  setInterpolationTypeAtKey(k,a,b){this.keys[k-1].inType=a;this.keys[k-1].outType=b;}
  setTemporalEaseAtKey(k,a,b){this.keys[k-1].inEase=a;this.keys[k-1].outEase=b;}
  setTemporalContinuousAtKey(){}setTemporalAutoBezierAtKey(){}setSpatialContinuousAtKey(){}setSpatialAutoBezierAtKey(){}setRovingAtKey(){}
  setSpatialTangentsAtKey(k,a,b){this.keys[k-1].inT=a;this.keys[k-1].outT=b;}
  setLabelAtKey(k,v){this.keys[k-1].label=v;}setSelectedAtKey(k,v){this.keys[k-1].selected=v;}
  removeKey(k){this.keys.splice(k-1,1);}setValue(v){this.value=v;}
  setValueAtTime(t,v){let k=this.keys.find(k=>Math.abs(k.t-t)<1e-8);if(k)k.v=v;else this.keys.push({t,v,selected:false});this.keys.sort((a,b)=>a.t-b.t);}
  nearestKeyIndex(t){let best=0;for(let i=1;i<this.keys.length;i++)if(Math.abs(this.keys[i].t-t)<Math.abs(this.keys[best].t-t))best=i;return best+1;}
 }
 class Layer{constructor(properties){this.name='Selected';this.index=1;this.locked=false;this.selectedProperties=properties;this.startTime=0;this.inPoint=0;this.outPoint=10;}}
 class CompItem{constructor(){this.time=0;this.duration=20;this.frameDuration=1/30;this.selectedLayers=[];this.selectedProperties=[];}}
 const comp=new CompItem(),ctx={console,Math,JSON,Error,isFinite,PropertyType:{PROPERTY:'PROPERTY'},PropertyValueType:{OneD:'OneD',TwoD_SPATIAL:'TwoD_SPATIAL'},CompItem,KeyframeEase:function(speed,influence){this.speed=speed;this.influence=influence;},KeyframeInterpolationType:{BEZIER:'BEZIER',LINEAR:'LINEAR',HOLD:'HOLD'},app:{project:{activeItem:comp},beginUndoGroup(){begins++;},endUndoGroup(){ends++;}}};ctx.$={global:ctx};vm.createContext(ctx);
 for(const f of ['quick-motion/model.js','effects-toolkit/model.js','effects-toolkit/host.jsx'])vm.runInContext(fs.readFileSync('editor_plugins/'+f,'utf8'),ctx);
 return {comp,ctx,Property,Layer,select(...ps){comp.selectedProperties=ps;comp.selectedLayers=[new Layer(ps)];},run(id,settings={}){return JSON.parse(ctx.storylensToolkit({id,settings}));},groups(){return [begins,ends];}};
}
test('ease touches only selected keys and keeps times, values, other ease side',()=>{
 const f=fixture(),p=new f.Property([[0,1],[1,9],[3,20,false]]);f.select(p);assert.equal(f.run('ease',{mode:'in',influence:75}).ok,true);assert.deepEqual(p.keys.map(k=>[k.t,k.v]),[[0,1],[1,9],[3,20]]);assert.equal(p.keys[0].inEase[0].influence,75);assert.equal(p.keys[0].outEase[0].influence,60);assert.equal(p.keys[2].inEase[0].influence,40);assert.deepEqual(f.groups(),[1,1]);
});
test('copy ease is nonmutating and paste preserves destination values',()=>{
 const f=fixture(),p=new f.Property([[0,17]]);f.select(p);assert.equal(f.run('ease-copy',{mode:'copy'}).ok,true);assert.deepEqual(f.groups(),[0,0]);const dst=new f.Property([[1,90],[2,100]]);f.select(dst);assert.equal(f.run('ease-copy',{mode:'paste'}).ok,true);assert.equal(dst.keyValue(1),90);assert.equal(dst.keyOutTemporalEase(1)[0].speed,20);
});
test('retime preserves untouched keys, selection, labels and scales velocity',()=>{
 const f=fixture(),p=new f.Property([[0,0],[1,20],[6,30,false]]);f.select(p);assert.equal(f.run('retime',{duration:2}).ok,true);assert.deepEqual(p.keys.map(k=>[k.t,k.v]),[[0,0],[2,20],[6,30]]);assert.equal(p.keys[1].inEase[0].speed,5);assert.equal(p.keys[1].label,2);assert.deepEqual(p.selectedKeys,[1,2]);
});
test('reverse swaps ease and spatial tangents without negating control-point offsets',()=>{
 const f=fixture(),p=new f.Property([[1,[0,0]],[3,[50,20]]],true);f.select(p);assert.equal(f.run('reverse').ok,true);assert.deepEqual(p.keyValue(1),[50,20]);assert.deepEqual(p.keyInSpatialTangent(1),[3,0]);assert.deepEqual(p.keyOutSpatialTangent(1),[-2,0]);assert.equal(p.keyInTemporalEase(1)[0].speed,20);
});
test('collision or locked layer fails before any mutation',()=>{
 for(const mode of ['collision','locked']){const f=fixture(),p=new f.Property([[0,0],[1,20],[2,30,false]]);f.select(p);if(mode==='locked')f.comp.selectedLayers[0].locked=true;const before=JSON.stringify(p.keys);const r=f.run('retime',{duration:2});assert.ok(r.error);assert.equal(JSON.stringify(p.keys),before);assert.deepEqual(f.groups(),[0,0]);}
});
test('no selected keys gives a useful instruction',()=>{
 const f=fixture(),p=new f.Property([[0,0,false],[1,20,false]]);f.select(p);assert.match(f.run('ease').error,/keyframe/i);assert.deepEqual(f.groups(),[0,0]);
});
module.exports={fixture};
