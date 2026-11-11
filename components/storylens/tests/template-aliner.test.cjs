const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture({duration=840,templates=[{name:'Template 10',duration:5},{name:'Template 2',duration:4}],selected=[],failAdd=0}={}){
 let id=1,adds=0,undo=0;const all=[];
 class FolderItem{constructor(name,parent){this.id=id++;this.name=name;this.parentFolder=parent;this.children=[];all.push(this);if(parent)parent.children.push(this)}get numItems(){return this.children.length}item(i){return this.children[i-1]}}
 class CompItem{constructor(name,seconds,parent){this.id=id++;this.name=name;this.duration=seconds;this.frameRate=30;this.width=1920;this.height=1080;this.pixelAspect=1;this.parentFolder=parent;this.usedIn=[];this.children=[];all.push(this);if(parent)parent.children.push(this);this.layers={add:source=>{adds++;if(failAdd&&adds===failAdd)throw Error('TEST NATIVE ADD FAILURE');const layer={source,name:source.name,comment:'',enabled:true,audioEnabled:true,inPoint:0,outPoint:source.duration,startTime:0,property:()=>({property:name=>({setValue:value=>{layer[name]=value}})}),moveToBeginning:()=>{},remove:()=>{this.children.splice(this.children.indexOf(layer),1)}};this.children.unshift(layer);return layer}}}get numLayers(){return this.children.length}layer(i){return this.children[i-1]}}
 const root=new FolderItem('Root',null),baseFolder=new FolderItem('Untitled 1',root),target=new CompItem('Owner linked video',duration,baseFolder);
 const base={name:'Owner source audio/video',source:{name:'Raw.mp4'},inPoint:0,outPoint:duration,startTime:0,audioEnabled:true,enabled:true,comment:'OWNER'};target.children.push(base);
 const folders=templates.map(spec=>{const folder=new FolderItem(spec.name,root);for(const name of spec.comps||['Main'])new CompItem(name,spec.duration,folder);return folder});
 const app={project:{rootFolder:root,file:{fsName:'owner.aep'},activeItem:target,selection:selected.map(i=>folders[i]),get numItems(){return all.length},item:i=>all[i-1]},beginUndoGroup:()=>{undo++},endUndoGroup:()=>{undo--}};
 const context={Math:Object.assign(Object.create(Math),{random:()=>.999999}),app,FolderItem,CompItem,hJSON:JSON.stringify,storylensCurrentComp:()=>target,storylensProjectId:()=> 'owner.aep'};
 vm.createContext(context);vm.runInContext(fs.readFileSync('editor_plugins/template-assembler/model.js','utf8'),context);vm.runInContext(fs.readFileSync('editor_plugins/shared/template-aliner-model.js','utf8'),context);vm.runInContext(fs.readFileSync('editor_plugins/shared/aftereffects-template-aliner.jsx','utf8'),context);
 return {context,target,base,folders,all,get adds(){return adds},get undo(){return undo}};
}
test('active video keeps its ID, duration and original audio; natural folder order runs once and leaves a tail',()=>{
 const f=fixture(),before=f.target.id,r=JSON.parse(f.context.storylensPanelTemplateAlign({}));
 assert.equal(r.ok,true);assert.equal(r.composition_id,String(before));assert.equal(f.target.duration,840);assert.equal(f.base.audioEnabled,true);assert.equal(f.base.outPoint,840);
 assert.deepEqual(r.placements.map(p=>p.folder),['Template 2','Template 10']);assert.deepEqual(r.placements.map(p=>[p.start,p.end]),[[0,4],[4,9]]);assert.equal(r.uncovered_duration,831);assert.equal(r.repeated,false);
 assert.equal(f.target.children.length,3);assert.ok(f.target.children.filter(l=>l!==f.base).every(l=>l.audioEnabled===false));assert.equal(f.undo,0);
});
test('last template clips to the current video end without changing source duration',()=>{
 const f=fixture({duration:8.5,templates:[{name:'01 First',duration:6},{name:'02 Last',duration:9}]}),r=JSON.parse(f.context.storylensPanelTemplateAlign({}));
 assert.deepEqual(r.placements.map(p=>[p.start,p.end]),[[0,6],[6,8.5]]);assert.equal(r.placements[1].trimmed,true);assert.equal(f.folders[1].children[0].duration,9);assert.equal(r.uncovered_duration,0);
});

test('native layout defers rendering until the whole arrangement or rollback is complete',()=>{
 for(const failAdd of [0,1]){
  const f=fixture({failAdd}),writes=[];let rendering=false;
  Object.defineProperty(f.context.app,'disableRendering',{get:()=>rendering,set:v=>{writes.push(v);rendering=v}});
  const add=f.target.layers.add;f.target.layers.add=source=>{assert.equal(rendering,true);return add(source)};
  const result=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(!!result.error,failAdd===1);assert.deepEqual(writes,[true,false]);assert.equal(rendering,false);
 }
});
test('a highlighted folder does not restrict automatic discovery; containing video folder is excluded',()=>{
 const f=fixture({selected:[0]}),r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.placements.length,2);assert.equal(r.placements[0].folder,'Template 2');
});
test('multiple main candidates are resolved automatically without questions',()=>{
 const f=fixture({templates:[{name:'Template',duration:15,comps:['Main','Final']}]}),r=JSON.parse(f.context.storylensPanelTemplateAlign({}));
 assert.equal(r.ok,true);assert.equal(r.needs_choices,undefined);assert.equal(r.placements.length,1);assert.equal(f.adds,1);
});

test('graph identifies an outer color wrapper over its named Final child and unused holders',()=>{
 const f=fixture({templates:[{name:'New template',duration:65,comps:['Color_Edit','//Final Output','Image holder','Text 3']}]}),c=f.folders[0].children;
 c[0].children.push({source:c[1]});c[1].usedIn.push(c[0]);c[1].children.push({source:c[2]});c[2].usedIn.push(c[1]);
 c[3].width=800;c[3].height=100;c[3].children.push({source:null});
 const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.placements[0].source_comp_id,c[0].id);
});

test('deep composition ranking reads each native edge once instead of walking every subtree again',()=>{
 const names=['Main',...Array.from({length:35},(_,i)=>'Scene '+i)],f=fixture({templates:[{name:'Documentary',duration:65,comps:names}]}),comps=f.folders[0].children;let reads=0;
 for(let i=0;i<comps.length-1;i++){comps[i].children.push({source:comps[i+1]});comps[i+1].usedIn.push(comps[i]);}
 for(const c of comps){const layer=c.layer;c.layer=function(i){reads++;return layer.call(this,i)};}
 const result=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(result.ok,true);assert.equal(result.placements[0].source_comp_id,comps[0].id);assert.ok(reads<110,'Repeated native subtree reads: '+reads);
});

test('long render version beats the short variant without choosing a text helper',()=>{
 const f=fixture({templates:[{name:'New template',duration:65,comps:['Long_Version Rander','Short_Version Rander','Randam Script']}]}),c=f.folders[0].children;
 c[0].children.push({source:{}});c[1].children.push({source:{}});c[2].children.push({source:{}});c[1].duration=15;c[2].width=800;c[2].height=100;
 const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.placements[0].source_comp_id,c[0].id);
});
test('foreign composition choice and stale target are rejected before mutation',()=>{
 const f=fixture(),choices={};choices[String(f.folders[0].id)]=f.target.id;
 assert.match(JSON.parse(f.context.storylensPanelTemplateAlign({choices})).error,/composition.*folder/i);assert.equal(f.adds,0);
 assert.match(JSON.parse(f.context.storylensPanelTemplateAlign({expected:{project_id:'other.aep',composition_id:String(f.target.id)}})).error,/project changed/i);assert.equal(f.adds,0);
});
test('a second press creates fresh layers, removes only the old generated set, and changes the opening',()=>{
 const f=fixture(),first=JSON.parse(f.context.storylensPanelTemplateAlign({})),old=f.target.children.filter(l=>l!==f.base),count=f.target.numLayers;
 const second=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(second.ok,true);assert.equal(second.replaced_layers,2);assert.notEqual(second.placements[0].folder,first.placements[0].folder);assert.equal(f.target.numLayers,count);assert.ok(old.every(l=>!f.target.children.includes(l)));assert.equal(f.base.audioEnabled,true);
});
test('native add failure rolls back only newly created layers and keeps source/audio intact',()=>{
 const f=fixture({failAdd:2}),r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.ok(r.error);assert.equal(r.rollback_complete,true);assert.equal(f.target.numLayers,1);assert.equal(f.target.layer(1),f.base);assert.equal(f.undo,0);
});
test('a source that depends on the target cannot create a composition cycle',()=>{
 const f=fixture({templates:[{name:'Circular',duration:20}]}),source=f.folders[0].children[0];source.children.push({source:f.target});
 const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.match(r.error,/circular|depends on/i);assert.equal(f.adds,0);
});
test('unused later folders do not demand composition choices after the video is covered',()=>{
 const f=fixture({duration:2,templates:[{name:'01 First',duration:10},{name:'02 Unused',duration:10,comps:['Main','Final']}]}),r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.placements.length,1);assert.equal(r.unused_folders,1);
});

test('missing fonts remain usable with AE substitution and are reported without rewriting source text',()=>{
 const f=fixture(),source=f.folders[0].children[0],textLayer={id:900,containingComp:source};
 f.context.app.fonts={};f.context.app.project.layerByID=id=>id===900?textLayer:null;
 f.context.app.project.usedFonts=[{font:{postScriptName:'FutureMissing-Bold',familyName:'Future Missing',styleName:'Bold',isSubstitute:true},usedAt:[{layerID:900}]}];
 const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);
 assert.equal(r.font_report.missing[0].name,'FutureMissing-Bold');assert.equal(r.font_report.policy,'native-substitution');
 assert.equal(r.font_report.missing[0].occurrences,1);assert.equal(source.numLayers,0);
});

test('font check does not include an unrelated composition or block when the font API is unavailable',()=>{
 const f=fixture(),source=f.folders[0].children[0];
 f.context.app.fonts={};f.context.app.project.layerByID=()=>({containingComp:f.target});
 f.context.app.project.usedFonts=[{font:{postScriptName:'OwnerOnly',isSubstitute:true},usedAt:[{layerID:990}]}];
 const report=f.context.storylensTemplateFontReport([source]);assert.equal(report.missing.length,0);assert.equal(report.checked,true);
 delete f.context.app.fonts;assert.equal(f.context.storylensTemplateFontReport([source]).checked,false);
});

test('All Project Files container expands into separate templates rather than one main comp',()=>{const f=fixture(),root=f.context.app.project.rootFolder,bin=new f.context.FolderItem('All Project Files',root);for(const folder of f.folders){root.children.splice(root.children.indexOf(folder),1);folder.parentFolder=bin;bin.children.push(folder)}f.context.app.project.selection=[bin];const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.placements.length,2);assert.deepEqual(r.placements.map(x=>x.folder).sort(),['Template 10','Template 2']);assert.equal(f.base.audioEnabled,true)});

test('refresh build failure keeps the complete previous alignment',()=>{const f=fixture({failAdd:4});const first=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(first.ok,true);const old=f.target.children.slice();const failed=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.ok(failed.error);assert.equal(failed.rollback_complete,true);assert.deepEqual(f.target.children,old)});

// Owner will run these regression cases; no AE timeline is exercised by authoring them.
test('a selected Project folder does not hide the open video composition',()=>{const f=fixture({selected:[0]});f.context.storylensCurrentComp=()=>{throw Error('Project folder is selected')};f.context.app.project.activeItem=f.folders[0];f.context.ViewerType={VIEWER_COMPOSITION:1};f.context.app.activeViewer={type:1,setActive:()=>{f.context.app.project.activeItem=f.target;f.context.app.project.selection=[];return true}};const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.composition_id,String(f.target.id));assert.equal(r.placements.length,2);assert.equal(r.placements[0].folder,'Template 2')});
test('saved refresh target recovers after folder selection when viewer cannot activate',()=>{const f=fixture();assert.equal(JSON.parse(f.context.storylensPanelTemplateAlign({})).ok,true);f.context.storylensCurrentComp=()=>{throw Error('No focused comp')};f.context.app.project.activeItem=f.folders[0];const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.replaced_layers,2);assert.equal(f.target.numLayers,3)});

test('a one-project later batch does not exclude other imported templates',()=>{const f=fixture({selected:[0]});f.folders[0].comment='Storylens template batch|100';f.folders[1].comment='Storylens template batch|200';const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.placements.length,2);assert.equal(r.templates_found,2)});

// Prepared only: owner explicitly requested manual application testing.
test('a nested collection bin is expanded into all imported project roots',()=>{const f=fixture(),root=f.context.app.project.rootFolder,bin=new f.context.FolderItem('All Project Files',root),group=new f.context.FolderItem('All templates',bin);for(const folder of f.folders){root.children.splice(root.children.indexOf(folder),1);folder.parentFolder=group;group.children.push(folder)}const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.templates_found,2);assert.equal(r.placements.length,2)});
test('source tags without a batch tag remain discoverable inside a collection',()=>{const f=fixture(),root=f.context.app.project.rootFolder,bin=new f.context.FolderItem('All Project Files',root);for(const folder of f.folders){root.children.splice(root.children.indexOf(folder),1);folder.parentFolder=bin;bin.children.push(folder);folder.comment='Storylens template library v1|d:/templates/'+folder.name+'/main.aep'}const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.templates_found,2)});

test('separate imported projects nested by AE are not suppressed by their parent project',()=>{const f=fixture(),root=f.context.app.project.rootFolder,a=f.folders[0],b=f.folders[1];root.children.splice(root.children.indexOf(b),1);b.parentFolder=a;a.children.push(b);a.comment='Storylens template library v1|d:/templates/first.aep';b.comment='Storylens template library v1|d:/templates/second.aep';const r=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(r.ok,true);assert.equal(r.templates_found,2)});

test('failed-import quarantine and its nested AEPs never enter automatic alignment',()=>{
 const f=fixture(),root=f.target.parentFolder.parentFolder,F=f.folders[0].constructor,C=f.target.constructor,collection=new F('Import Template',root),bin=new F('Skipped templates',collection);bin.comment='Storylens template failed imports v1';const bad=new F('Broken.aep',bin);new C('Final render',100,bad);const result=JSON.parse(f.context.storylensPanelTemplateAlign({}));assert.equal(result.ok,true);assert.equal(result.templates_found,2);assert.equal(result.placements.some(x=>/Broken|Skipped/.test(x.folder)),false);
});

