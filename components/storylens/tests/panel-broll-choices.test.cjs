const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(){
 const source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8');
 const start=source.indexOf('async function chooseBroll('),end=source.indexOf('function cards(');
 function element(tag){return {tag,children:[],append(...items){this.children.push(...items)},replaceChildren(){this.children=[]}};}
 const nodes={choices:element('div'),receipt:element('p')},calls=[],imports=[],captures=[];
 const state={document:{createElement:element},$:id=>nodes[id],current:{result:{folder:'actual-result'}},context:{id:'owner-context'},
  token:'test-token',host:'premiere',hostNames:{premiere:'Premiere Pro'},
  api:async(path,body)=>{calls.push({path,body});return path.includes('broll-choice')?{choice_saved:true,manifest:body.state==='selected'?{type:'files'}:null}:{choices:[]}},
  capture:async()=>{captures.push(true)},importManifest:async m=>imports.push(m),error:e=>{throw e}};
 vm.createContext(state);if(start>=0)vm.runInContext(source.slice(start,end),state);
 return {state,nodes,calls,imports,captures};
}
test('rendering genuine options never selects or imports one automatically',()=>{
 const f=fixture();f.state.brollCards([{id:'candidate',slot_id:'slot',project:'bank/broll-project.json',keyword:'room',start:2,end:3,path:'preview.mp4',selectable:false}]);
 assert.equal(f.calls.length,0);assert.equal(f.imports.length,0);
 const buttons=f.nodes.choices.children.flatMap(n=>n.children).filter(n=>n.tag==='button');
 assert.ok(buttons.some(b=>b.disabled));
});
test('explicit use preserves stable IDs and imports only the server-validated manifest',async()=>{
 const f=fixture();await f.state.chooseBroll({project:'bank/broll-project.json',slot_id:'slot',candidate_id:'candidate'},'selected');
 assert.equal(f.calls[0].body.state,'selected');assert.equal(f.calls[0].body.candidate_id,'candidate');
 assert.equal(f.calls[0].body.context_id,'owner-context');assert.equal(f.imports.length,1);
 assert.equal(f.captures.length,1);
});
test('No B-roll persists the manual decision without an import',async()=>{
 const f=fixture();await f.state.chooseBroll({project:'bank/broll-project.json',slot_id:'slot'},'no_broll');
 assert.equal(f.calls[0].body.state,'no_broll');assert.equal(f.imports.length,0);
});
