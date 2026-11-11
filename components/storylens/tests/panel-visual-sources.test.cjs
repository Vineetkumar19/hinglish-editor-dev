const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(){
 const source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8');
 const start=source.indexOf('async function chooseVisual('),end=source.indexOf('function cards(');
 function element(tag){return {tag,children:[],append(...items){this.children.push(...items)},replaceChildren(){this.children=[]}};}
 const nodes={choices:element('div'),receipt:element('p')},calls=[],imports=[],captures=[];
 const descriptor={job_id:'engine',project_path:'project.json',manifest_path:'bank.json',manifest_sha256:'frozen',banks:[]};
 const state={document:{createElement:element},$:id=>nodes[id],visualSources:descriptor,
  current:{engine_id:'engine'},visualChoosing:false,URLSearchParams,context:{id:'context'},token:'private',host:'premiere',hostNames:{premiere:'Premiere Pro'},
  api:async(path,body)=>{calls.push({path,body});return {...descriptor,native_manifest:body.import_selected?{type:'assets',insert:false}:null}},
  capture:async()=>captures.push(true),importManifest:async m=>imports.push(m),error:e=>{throw e}};
 vm.createContext(state);if(start>=0)vm.runInContext(source.slice(start,end),state);
 return {state,nodes,calls,imports,captures,descriptor};
}
test('raw visual review does not select or import while rendering; missing matches remain visible',()=>{
 const f=fixture();f.state.visualCards({...f.descriptor,banks:[{slot_index:0,entity:'Dhoni',anchor:{start_seconds:2,end_seconds:3},target:5,choices:[],selection:{state:'unselected'}}]});
 assert.equal(f.calls.length,0);assert.equal(f.imports.length,0);
 const text=f.nodes.choices.children.flatMap(n=>n.children).map(n=>n.textContent||'').join(' ');
 assert.match(text,/No matching source image/);assert.match(text,/No visual/);
});
test('explicit visual choice binds current snapshot and imports only checked native source manifest',async()=>{
 const f=fixture();await f.state.chooseVisual({slot_index:3},'media-a',true);
 const b=f.calls[0].body;assert.equal(b.type,'smart_visuals.source_bank.select');assert.equal(b.version,1);
 assert.equal(b.choices['3'],'media-a');assert.equal(b.base_manifest_sha256,'frozen');
 assert.equal(b.project_path,'project.json');assert.equal(b.context_id,'context');assert.equal(b.import_selected,true);
 assert.equal(f.captures.length,1);assert.equal(f.imports[0].insert,false);
});
test('No visual advances saved decision but never imports or captures the editor',async()=>{
 const f=fixture();await f.state.chooseVisual({slot_index:3},'',false);
 assert.equal(f.calls[0].body.choices['3'],'');assert.equal(f.imports.length,0);assert.equal(f.captures.length,0);
});
