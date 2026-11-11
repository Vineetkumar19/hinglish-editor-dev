const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
function load(host,extra={}){const state={hJSON:JSON.stringify,hinglishEscape:JSON.stringify,...extra};vm.createContext(state);vm.runInContext(fs.readFileSync(path.join(root,'editor_plugins/shared',host+'-panel.jsx'),'utf8'),state);return state;}
test('AE converts normalized centers and linear gain into native units',()=>{
 const values={};const group={property:name=>({setValue:v=>{values[name]=v}})};
 const layer={property:()=>group};const host=load('aftereffects');
 host.storylensAEMotion(layer,{motion:{scale:{value:125},center:{value:[.1,-.2]},rotation:{value:15},opacity:{value:80},level:{value:.5}}},{width:1000,height:600});
 assert.deepEqual(Array.from(values['ADBE Position']),[600,180]);assert.deepEqual(Array.from(values['ADBE Scale']),[125,125]);
 assert.equal(values['ADBE Rotate Z'],15);assert.equal(values['ADBE Opacity'],80);assert.ok(Math.abs(values['ADBE Audio Levels'][0]+6.020599913)<.000001);
});
test('AE saved-font filename handling accepts Windows and POSIX paths while preserving an exact font name',()=>{
 const host=load('aftereffects');
 assert.equal(host.storylensFontName({font_path:'C:\\Saved fonts\\Caption Bold.ttf'}),'Caption Bold');
 assert.equal(host.storylensFontName({font_path:'/Saved fonts/Caption Bold.otf'}),'Caption Bold');
 assert.equal(host.storylensFontName({font_name:'StorylensCaptionOne-Bold',font_path:'C:\\Other.ttf'}),'StorylensCaptionOne-Bold');
 assert.throws(()=>host.storylensFontName({}),/font/);
});
test('AE photo import needs a project but no active composition',()=>{
 let imports=0;const host=load('aftereffects',{app:{project:{file:{fsName:'owner.aep'}}},storylensPhotoImportAE:m=>{imports++;return {status:'done',collection_id:m.id}}});
 assert.equal(JSON.parse(host.storylensPanelImport({type:'photos',id:'one',panel_project_id:'owner.aep'})).status,'done');assert.equal(imports,1);
 const rejected=JSON.parse(host.storylensPanelImport({type:'photos',id:'one',panel_project_id:'different.aep'}));assert.match(rejected.error,/project changed/);assert.equal(imports,1);
});
test('Premiere rejects photo results for another project before importing',()=>{
 let imports=0;const host=load('premiere',{app:{project:{path:'owner.prproj'}},storylensPhotoImportPremiere:()=>{imports++;return {status:'done'}}});
 assert.equal(JSON.parse(host.storylensPanelImport({type:'photos',panel_project_id:'owner.prproj'})).status,'done');
 assert.match(JSON.parse(host.storylensPanelImport({type:'photos',panel_project_id:'different.prproj'})).error,/project changed/);assert.equal(imports,1);
});
test('installed source packages have both photo adapters and 2026 host ranges',()=>{
 for(const name of ['after-effects-cep','premiere-cep']){
  const folder=path.join(root,'output/editor-suite-20261025',name);
  assert.match(fs.readFileSync(path.join(folder,'CSXS/manifest.xml'),'utf8'),/26\.9/);
  assert.match(fs.readFileSync(path.join(folder,'jsx/host.jsx'),'utf8'),/#include "photo-import.jsx"/);
  assert.match(fs.readFileSync(path.join(folder,'jsx/photo-import.jsx'),'utf8'),/storylensPhotoImportAE/);
 }
});
function premiereImportHost(addSequence){
 const sequences=[{sequenceID:'source-sequence'}];Object.defineProperty(sequences,'numSequences',{get:()=>sequences.length});
 const project={path:'test.prproj',activeSequence:sequences[0],sequences,rootItem:{createBin:()=>({})},
  importFiles:()=>{if(addSequence)sequences.push({sequenceID:'result-sequence'});return true;},openSequence:id=>{project.opened=id}};
 return {project,host:load('premiere',{app:{project},File:function(){this.exists=true}})};
}
test('Premiere confirms the newly imported sequence instead of only file import',()=>{
 const {project,host}=premiereImportHost(true),receipt=JSON.parse(host.storylensPanelImport({type:'files',paths:['test.xml'],activate:true}));
 assert.equal(receipt.ok,true);assert.equal(project.opened,'result-sequence');
 assert.deepEqual(receipt.sequence_ids,['result-sequence']);assert.equal(receipt.prior_sequence_id,'source-sequence');
});
test('Premiere does not claim a new editable timeline when none was added',()=>{
 const {host}=premiereImportHost(false),receipt=JSON.parse(host.storylensPanelImport({type:'files',paths:['test.xml'],activate:true}));
 assert.match(receipt.error,/did not confirm a new timeline/);assert.equal(receipt.ok,undefined);
});
test('retrying an explicit B-roll selection reopens its existing timeline without duplicate import',()=>{
 const {project,host}=premiereImportHost(false);let imports=0;project.importFiles=()=>{imports++;return true};
 project.sequences[0].name='Original - Storylens B-roll abcdef0123456789';
 const result=JSON.parse(host.storylensPanelImport({type:'files',paths:['selection.xml'],activate:true,
  selection_id:'abcdef0123456789',sequence_name:project.sequences[0].name,notice:'External AV1 original; full-original trimming is unavailable.'}));
 assert.equal(result.ok,true);assert.equal(result.reused,true);assert.equal(imports,0);
 assert.equal(project.opened,'source-sequence');
 assert.match(result.message,/full-original trimming is unavailable/);
});

test('original sound sources reuse project items without importing a preview or duplicate bin',()=>{
 const {project,host}=premiereImportHost(false);let imports=0,bins=0;
 project.rootItem.children={0:{type:1,getMediaPath:()=> 'library/original.wav'},numItems:1};
 project.rootItem.createBin=()=>{bins++;return {}};project.importFiles=()=>{imports++;return true};
 host.ProjectItemType={BIN:2};
 const receipt=JSON.parse(host.storylensPanelImport({type:'assets',paths:['library/original.wav'],
  source_assets:true,insert:false,name:'Storylens sound sources'}));
 assert.equal(receipt.ok,true);assert.equal(receipt.reused,true);assert.equal(imports,0);assert.equal(bins,0);
 assert.deepEqual(receipt.files,['library/original.wav']);
});

test('mixed original sound source import adds only missing originals',()=>{
 const {project,host}=premiereImportHost(false);let received;
 project.rootItem.children={0:{type:1,getMediaPath:()=> 'existing.wav'},numItems:1};
 project.importFiles=paths=>{received=Array.from(paths);return true};host.ProjectItemType={BIN:2};
 const receipt=JSON.parse(host.storylensPanelImport({type:'assets',paths:['existing.wav','new.wav'],source_assets:true,insert:false}));
 assert.equal(receipt.ok,true);assert.deepEqual(received,['new.wav']);
});
test('Premiere reports the explicit original-source editability limit of a prepared handoff',()=>{
 const {host}=premiereImportHost(true);
 const result=JSON.parse(host.storylensPanelImport({type:'files',paths:['compatible-selection.xml'],activate:true,
  notice:'Prepared clips are editable; full-original trimming is unavailable for the external AV1 reference.'}));
 assert.equal(result.ok,true);assert.match(result.message,/full-original trimming is unavailable/);
});
