const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{test}=require('node:test');
function build(selectedKind){
 const created=[],files={};let nextId=1,saves=0;function CompItem(){} function FootageItem(){}
 function prop(name){return {name,value:{},numKeys:0,keys:[],numProperties:0,_children:{},property(n){return this._children[n]||(this._children[n]=prop(n));},addProperty(n){const p=prop(n);this._children[n]=p;return p;},setValue(v){this.value=v;},setValueAtTime(t,v){this.keys.push({t,v});this.numKeys++;},setInterpolationTypeAtKey(){},keyInTemporalEase(){return [{}];},keyOutTemporalEase(){return [{}];},setTemporalEaseAtKey(){},setSpatialTangentsAtKey(){}};}
 function layer(kind,text=''){
  const props={},transform={property:n=>props[n]||(props[n]=prop(n))};
  return {kind,text,name:'',source:{},props,property:n=>n==='ADBE Transform Group'?transform:(props[n]||(props[n]=prop(n))),sourceRectAtTime(){return {left:0,top:-100,width:Math.max(1,text.length*100),height:110};},moveToEnd(){},moveToBeginning(){}};
 }
 function comp(name,w,h,p,duration,fps){
  const layers=[];const c={id:nextId++,name,width:w,height:h,duration,frameRate:fps,numLayers:0,layers:{
   addText(t){const l=layer('text',t);layers.push(l);c.numLayers++;return l;},addNull(){const l=layer('null');layers.push(l);c.numLayers++;return l;},
   addCamera(){const l=layer('camera');layers.push(l);c.numLayers++;return l;},add(source){const l=layer('av');l.source=source;layers.push(l);c.numLayers++;return l;}
  },layer:i=>layers[i-1],openInViewer(){},get _layers(){return layers;}};Object.setPrototypeOf(c,CompItem.prototype);created.push(c);return c;
 }
 function File(p){this.fsName=p;this.parent={fsName:'output'};this.open=()=>true;this.write=s=>files[p]=s;this.close=()=>{};}
 const selected=selectedKind?Object.assign(new FootageItem(),{hasVideo:selectedKind==='video',width:selectedKind==='video'?1920:0,height:selectedKind==='video'?1080:0}):null;
 const context={CompItem,FootageItem,File,Folder:function(p){this.fsName=p;},$:{fileName:'Create 3D Camera Title.jsx'},
  app:{project:{selection:selected?[selected]:[],items:{addFolder:name=>({name}),addComp:comp},save(){saves++;}},fonts:{getFontsByPostScriptName:()=>[{isSubstitute:false}]},beginUndoGroup(){},endUndoGroup(){}},
  AutoOrientType:{NO_AUTO_ORIENT:0,CAMERA_OR_POINT_OF_INTEREST:1},KeyframeEase:function(){},KeyframeInterpolationType:{BEZIER:1},PropertyValueType:{TwoD:2,ThreeD:3},ParagraphJustification:{CENTER_JUSTIFY:1},alert(){}
 };
 vm.runInNewContext(fs.readFileSync('tools/ae-camera-title/build.jsx','utf8'),context);
 return {created,files,saves};
}
test('editable yellow/white reference titles use a real camera dolly and shared 3D footage',()=>{
 const r=build();assert.equal(r.saves,0);const masters=r.created.filter(c=>c.name.startsWith('TITLE -'));
 assert.equal(masters.length,8);
 assert.equal(masters.filter(c=>c.width===1080&&c.height===1920).length,4);
 assert.equal(masters.filter(c=>c.width===1920&&c.height===1080).length,4);
 for(const c of masters){
  assert.equal(c.renderer,'ADBE Classic 3d');assert.equal(c.duration,8);
  const camera=c._layers.find(l=>l.kind==='camera'),rig=c._layers.find(l=>l.name==='CAMERA MOVE - Edit these keys');
  assert(camera&&rig);assert.equal(camera.parent,rig);assert(rig.props['ADBE Position'].keys.length>=4);
  assert(camera.props['ADBE Anchor Point'].expression.includes('CAMERA TARGET'));
  const footage=c._layers.find(l=>l.name==='YOUR FOOTAGE');assert(footage.threeDLayer);assert(!footage.parent);
  const front=c._layers.filter(l=>l.name.startsWith('EDIT -'));assert.equal(front.length,2);assert(front.every(l=>l.threeDLayer));
  const docs=front.map(l=>l.props['ADBE Text Properties']._children['ADBE Text Document'].value);
  assert.equal(docs.filter(d=>d.fillColor[0]===1&&d.fillColor[1]===.86).length,1);
  const depth=c._layers.filter(l=>l.name.startsWith('DEPTH -'));assert.equal(depth.length,48);assert(depth.every(l=>l.threeDLayer&&l.shy));
  assert(depth.every(l=>l.props['ADBE Text Properties']._children['ADBE Text Document'].expression.includes('.setFillColor')));
  assert(depth.every(l=>l.props['ADBE Text Properties']._children['ADBE Text Document'].expression.includes('.fillColor')));
  const title=c._layers.find(l=>l.name==='TITLE POSITION - Move both lines');
  const control=title.props['ADBE Effect Parade']._children['ADBE Slider Control'];
  assert.equal(control.property('ADBE Slider Control-0001').value,96*c.width/1920);
  const zs=rig.props['ADBE Position'].keys.map(k=>k.v[2]),far=2500-Math.min(...zs),near=2500-Math.max(...zs);
  assert((far+400)/(near+400)>1.25,'video must visibly push in with the camera');
  assert((far-260)/(near-260)>1.34,'title must approach more strongly than the approved original');
  assert(front.every(l=>l.props['ADBE Opacity'].expression==='parent.opacity'));
 }
 assert(masters.some(c=>c.width===1080&&c.height===1920));
});
test('an audio-only Project selection leaves the video placeholders empty',()=>{
 const r=build('audio');assert.equal(r.created.filter(c=>c.name.startsWith('TITLE -')).length,8);
 assert(r.created.filter(c=>c.name.startsWith('YOUR FOOTAGE -')).every(c=>c.numLayers===0));
});
