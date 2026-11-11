/* Host-contract tests. These are mocks, not a claim of Premiere validation. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('editor_plugins/premiere-cep/jsx/beats.jsx','utf8');
function clip(scale){return {start:{seconds:0},end:{seconds:10},inPoint:{seconds:5},isSpeedReversed:()=>false,getSpeed:()=>1,components:{numItems:1,0:{matchName:'AE.ADBE Motion',properties:{1:scale}}}}}
function parameter(){const keys=[];return {keys,areKeyframesSupported:()=>true,isTimeVarying:()=>false,getValue:()=>100,setTimeVarying:()=>{},addKey:()=>{},setValueAtKey:(time,value)=>keys.push([time.seconds,value]),setInterpolationTypeAtKey:()=>{}}}
const originalScale=parameter(),copyScale=parameter();
const original={sequenceID:'original',timebase:254016000000/30,name:'Original',videoTracks:{numTracks:1,0:{isLocked:()=>false,clips:{numItems:1,0:clip(originalScale)}}}};
const clone={sequenceID:'clone',timebase:254016000000/30,name:'Copy',videoTracks:{numTracks:1,0:{isLocked:()=>false,clips:{numItems:1,0:clip(copyScale)}}}};
const project={activeSequence:original,sequences:{numSequences:1,0:original},openSequence:id=>{project.activeSequence=id==='clone'?clone:original}};
original.clone=()=>{project.sequences[1]=clone;project.sequences.numSequences=2;return true};
const context={app:{project},Time:function(){this.seconds=0},hinglishEscape:JSON.stringify};
vm.createContext(context);vm.runInContext(source,context);let checkpoints=0;context.storylensBeatCheckpoint=()=>{checkpoints++;return 'verified-test-checkpoint'};
let result=JSON.parse(context.storylensApplyBeatEffects({sequence_id:'original',fps:30,duration:.24,amount:8,style:'punch',video_track:1,beats:[{frame:60}]}));
assert.equal(result.error,undefined);assert.equal(originalScale.keys.length,0);assert.equal(copyScale.keys.length,3);
assert.equal(copyScale.keys[1][0],7);assert.equal(copyScale.keys[1][1],108);assert.equal(checkpoints,2);
assert.match(result.message,/1 zoom pulses/);
result=JSON.parse(context.storylensApplyBeatEffects({sequence_id:'unrelated',fps:30}));assert.match(result.error,/active sequence changed/);
// Replacement removes only Storylens-owned markers and preserves user notes.
project.activeSequence=original;
const user={comments:'User note'},old={comments:'StorylensBeat:old'},removed=[],added=[];
original.markers={getFirstMarker:()=>user,getNextMarker:m=>m===user?old:null,deleteMarker:m=>removed.push(m),createMarker:sec=>{const marker={seconds:sec};added.push(marker);return marker}};
context.storylensMusicInfo=()=>({path:'music.wav',source_in:0,source_out:10,timeline_start:0});
result=JSON.parse(context.storylensMarkBeats({sequence_id:'original',fps:30,path:'music.wav',source_in:0,source_out:10,timeline_start:0,id:'test',density:'light',beats:[{frame:60,strength:.8}]}));
assert.equal(result.error,undefined);assert.deepEqual(removed,[old]);assert.equal(added[0].seconds,2);assert.equal(added[0].comments.startsWith('StorylensBeat:'),true);
context.storylensMusicInfo=()=>({path:'music.wav',source_in:0,source_out:10,timeline_start:5});
result=JSON.parse(context.storylensMarkBeats({sequence_id:'original',fps:30,path:'music.wav',source_in:0,source_out:10,timeline_start:0}));assert.match(result.error,/placement changed/);
console.log('Premiere CEP host contracts passed: source-time keyframes, duplicate preservation, stale-plan rejection, user-marker preservation.');
