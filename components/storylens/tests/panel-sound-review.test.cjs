const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(){
 const source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8'),start=source.indexOf('async function listenSound('),end=source.indexOf('function cards(');
 function element(tag){return {tag,children:[],append(...items){this.children.push(...items)},replaceChildren(){this.children=[]},play:async()=>{}};}
 const nodes={choices:element('div'),receipt:element('p')},calls=[],imports=[],captures=[];
 const state={document:{createElement:element},$:id=>nodes[id],context:{id:'owner-context'},token:'private',URLSearchParams,
  api:async(path,body)=>{calls.push({path,body});return path.endsWith('sound-original')?{manifest:{type:'assets',insert:false,paths:['original.wav']}}:{status:'ready',id:'audition-fixture'}},
  capture:async()=>captures.push(true),importManifest:async m=>{imports.push(m);return {ok:true}},error:e=>{throw e}};
 vm.createContext(state);if(start>=0)vm.runInContext(source.slice(start,end),state);
 return {state,nodes,calls,imports,captures,element};
}
test('rendering sound alternatives never picks or imports a winner',()=>{
 const f=fixture();f.state.soundCards({job_id:'actual-engine',groups:[{kind:'music',role:'bed',timeline:{start:0,end:2},candidates:[]}]});
 assert.equal(f.calls.length,0);assert.equal(f.imports.length,0);
});
test('explicit audition stays bound to job and candidate without importing preview audio',async()=>{
 const f=fixture(),audio=f.element('audio');await f.state.listenSound({job_id:'actual-engine',id:'candidate'},audio);
 assert.equal(f.calls[0].body.job_id,'actual-engine');assert.equal(f.calls[0].body.candidate_id,'candidate');
 assert.match(audio.src,/sound-audition-media/);assert.match(audio.src,/audition_id=audition-fixture/);
 assert.equal(f.imports.length,0);
});
test('original audio import captures current project and uses only checked bin manifest',async()=>{
 const f=fixture();await f.state.importOriginalSound({job_id:'actual-engine',id:'candidate'});
 assert.equal(f.captures.length,1);assert.equal(f.calls[0].body.context_id,'owner-context');
 assert.equal(f.imports[0].insert,false);assert.deepEqual(f.imports[0].paths,['original.wav']);
});
test('opening a saved review fetches ranked alternatives without importing or starting inference',async()=>{
 const source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8');
 const start=source.indexOf('async function openSoundReview('),end=source.indexOf('async function refreshSound(',start);
 assert.ok(start>=0,'saved Sound reviews need an explicit open operation');
 const calls=[],nodes={importResult:{},status:{}},state={$:id=>nodes[id],clearError:()=>{},soundCards:r=>{state.review=r},api:async path=>{calls.push(path);return {job_id:'actual-sound',groups:[]}}};
 vm.createContext(state);vm.runInContext(source.slice(start,end),state);await state.openSoundReview('actual-sound');
 assert.deepEqual(calls,['/api/panel/sound-review?job_id=actual-sound']);assert.equal(state.review.job_id,'actual-sound');assert.equal(nodes.importResult.hidden,true);
});
