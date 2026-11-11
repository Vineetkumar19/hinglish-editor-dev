const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
function fixture(){
 const layers=[];let next=1,imports=0;
 function CompItem(){} function FootageItem(){}
 function File(path){this.fsName=path;this.exists=true;}
 const comp=new CompItem();Object.assign(comp,{id:10,width:1080,height:1920,duration:20,frameRate:30});
 comp.layer=i=>layers[i-1];Object.defineProperty(comp,'numLayers',{get:()=>layers.length});
 comp.layers={add(source){const layer={id:next++,source,startTime:0,inPoint:0,outPoint:source.duration,
  stretch:100,timeRemapEnabled:false,comment:'',effects:['owner-effect'],replaceSource(s){this.source=s;}};layers.push(layer);return layer;}};
 const project={activeItem:comp};
 const c={app:{project,beginUndoGroup(){},endUndoGroup(){}},File,CompItem,FootageItem,
  storylensProjectId:()=>'/owner.aep',storylensFolder:()=>({}),
  storylensFootage(path){imports++;return Object.assign(new FootageItem(),{file:new File(path),duration:8,width:1080,height:1920});}};
 vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/shared/timed-choice.jsx','utf8'),c);
 const op={type:'timed_choice',version:1,operation_id:'a'.repeat(32),binding_id:'b'.repeat(64),
  action:'insert',feature:'broll',asset_id:'first',asset_sha256:'c'.repeat(64),path:'/checked.mp4',
  expected:{host:'aftereffects',project_id:'/owner.aep',sequence_id:'10'},expected_item_id:null,
  start_frame:64,end_frame:93,fps:'30',source_in:3,source_duration:8,width:1080,height:1920,preserve_host_edits:true};
 return {c,comp,layers,op,imports:()=>imports};
}
test('AE inserts at the spoken frame and repeat operation reuses the same layer',()=>{
 const f=fixture(),r=f.c.SLTimedChoice.ae(f.op);
 assert.equal(r.ok,true);assert.equal(r.start,64/30);assert.equal(r.end,93/30);assert.equal(r.source_in,3);
 assert.equal(f.layers.length,1);assert.equal(f.layers[0].audioEnabled,false);
 assert.equal(f.c.SLTimedChoice.ae(f.op).item_id,r.item_id);assert.equal(f.layers.length,1);
});
test('AE replacement preserves owner timing, stretch and effects on the bound layer',()=>{
 const f=fixture(),first=f.c.SLTimedChoice.ae(f.op),layer=f.layers[0];
 layer.inPoint=5;layer.outPoint=6.5;layer.startTime=2;layer.stretch=125;
 const swap={...f.op,action:'replace',operation_id:'d'.repeat(32),previous_operation_id:f.op.operation_id,
  expected_item_id:first.item_id,asset_id:'second',path:'/second.mp4',asset_sha256:'e'.repeat(64)};
 const r=f.c.SLTimedChoice.ae(swap);assert.equal(r.item_id,first.item_id);
 assert.equal(layer.inPoint,5);assert.equal(layer.outPoint,6.5);assert.equal(layer.startTime,2);
 assert.equal(layer.stretch,125);assert.deepEqual(layer.effects,['owner-effect']);assert.equal(f.layers.length,1);
});
test('ambiguous binding and changed composition fail before importing a new source',()=>{
 const f=fixture();f.c.SLTimedChoice.ae(f.op);f.layers.push({...f.layers[0],id:99});
 const count=f.imports();assert.throws(()=>f.c.SLTimedChoice.ae(f.op),/ambiguous|more than one/i);assert.equal(f.imports(),count);
 const g=fixture();g.op.expected.sequence_id='other';assert.throws(()=>g.c.SLTimedChoice.ae(g.op),/composition/i);assert.equal(g.layers.length,0);
});
function premiereFixture(){
 const items=[],tracks=[{clips:[]},{clips:[]}];let next=1;
 const sequence={sequenceID:'seq',timebase:String(254016000000/30),videoTracks:tracks,audioTracks:[]};
 tracks.numTracks=2;sequence.audioTracks.numTracks=0;
 const children={numItems:0},root={children,createBin(){return root;}};
 const project={path:'/owner.prproj',activeSequence:sequence,rootItem:root,sequences:[sequence],
  importFiles(paths){for(const path of paths){const item={type:1,nodeId:'p'+next++,name:'media',path,
   getMediaPath(){return this.path;},canChangeMediaPath(){return true;},changeMediaPath(path){this.path=path;return 0;},
   setInPoint(n){this.input=n;return 0;},setOutPoint(n){this.output=n;return 0;}};
   items.push(item);children[children.numItems++]=item;}return true;}};
 project.sequences.numSequences=1;
 function time(seconds){return {seconds,ticks:String(Math.round(seconds*254016000000))};}
 tracks[1].overwriteClip=(item,ticks)=>{const start=Number(ticks)/254016000000,clip={nodeId:'t'+next++,projectItem:item,
  start:time(start),end:time(start+item.output-item.input),inPoint:time(item.input),outPoint:time(item.output),
  effects:['owner-effect'],getSpeed(){return 1;},isSpeedReversed(){return false;}};tracks[1].clips.push(clip);tracks[1].clips.numItems=tracks[1].clips.length;};
 for(const track of tracks)track.clips.numItems=0;
 const c={app:{project},File:function(path){this.fsName=path;this.exists=true;},ProjectItemType:{BIN:2},
  Time:function(){this._seconds=0;Object.defineProperty(this,'seconds',{get:()=>this._seconds,set:v=>{this._seconds=v;this.ticks=String(Math.round(v*254016000000));}});}};
 vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/shared/timed-choice.jsx','utf8'),c);
 const op={...fixture().op,expected:{host:'premiere',project_id:'/owner.prproj',sequence_id:'seq'},path:'/private/first.mp4'};
 return {c,project,sequence,tracks,items,op,time};
}
test('Premiere individual insert uses speech time; swap keeps same clip and owner effects',()=>{
 const f=premiereFixture(),first=f.c.SLTimedChoice.premiere(f.op),clip=f.tracks[1].clips[0];
 assert.ok(Math.abs(first.start-64/30)<1e-9);assert.ok(Math.abs(first.end-93/30)<1e-9);assert.equal(f.tracks[1].clips.length,1);
 f.c.SLTimedChoice.premiere(f.op);assert.equal(f.tracks[1].clips.length,1);
 clip.start=f.time(5);clip.end=f.time(6.5);clip.inPoint=f.time(2);clip.outPoint=f.time(3.5);
 const swap={...f.op,action:'replace',operation_id:'d'.repeat(32),previous_operation_id:f.op.operation_id,
  previous_path:f.op.path,expected_item_id:first.item_id,path:'/private/second.mp4',asset_id:'second',asset_sha256:'e'.repeat(64)};
 const result=f.c.SLTimedChoice.premiere(swap);assert.equal(result.item_id,first.item_id);
 assert.equal(clip.start.seconds,5);assert.equal(clip.end.seconds,6.5);assert.equal(clip.inPoint.seconds,2);
 assert.deepEqual(clip.effects,['owner-effect']);assert.equal(clip.projectItem.getMediaPath(),swap.path);
});
test('Premiere refuses to overwrite owner footage or relink a shared project item',()=>{
 const f=premiereFixture();f.tracks[1].clips.push({start:f.time(1),end:f.time(4)});f.tracks[1].clips.numItems=1;
 assert.throws(()=>f.c.SLTimedChoice.premiere(f.op),/spare|empty|occupied/i);
 const g=premiereFixture(),first=g.c.SLTimedChoice.premiere(g.op),clip=g.tracks[1].clips[0];
 g.tracks[0].clips.push({...clip,nodeId:'duplicate'});g.tracks[0].clips.numItems=1;
 assert.throws(()=>g.c.SLTimedChoice.premiere({...g.op,action:'replace',expected_item_id:first.item_id,
  operation_id:'d'.repeat(32),previous_operation_id:g.op.operation_id,previous_path:g.op.path,path:'/second.mp4'}),/shared|more than one/i);
});
