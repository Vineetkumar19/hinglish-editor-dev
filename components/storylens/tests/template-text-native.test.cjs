/* Regression fixtures; no Adobe session is opened or modified by this file. */
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('title decorations follow their own lettering, not photos or the scene backdrop',()=>{
 const f=fixture(),nodes=[
  {id:'t',name:'Title',text:true,enabled:false,rect:{x:100,y:100,w:200,h:50}},
  {id:'line',name:'Underline',rect:{x:100,y:155,w:200,h:5}},
  {id:'paper',name:'Text paper strip',rect:{x:95,y:95,w:210,h:60}},
  {id:'photo',name:'Photo frame',rect:{x:95,y:95,w:210,h:60}},
  {id:'bg',name:'Background',rect:{x:0,y:0,w:1920,h:1080}}];
 const found=f.context.SLTemplateTextModel.decorationOwners(nodes);
 assert.deepEqual(JSON.parse(JSON.stringify(found)),[{id:'line',owners:['t']},{id:'paper',owners:['t']}]);
});
test('shared backplates include all overlapping text owners and unrelated paper stays',()=>{
 const f=fixture(),nodes=[{id:'a',name:'Title',text:true,rect:{x:10,y:10,w:150,h:30}},
 {id:'b',name:'Subtitle',text:true,rect:{x:10,y:45,w:150,h:30}},
 {id:'p',name:'Text backplate',rect:{x:5,y:5,w:165,h:75}},
 {id:'art',name:'Paper artwork',rect:{x:5,y:5,w:165,h:75}}];
 assert.deepEqual(JSON.parse(JSON.stringify(f.context.SLTemplateTextModel.decorationOwners(nodes))),[{id:'p',owners:['a','b']}]);
});
test('unknown 3D decoration needs an explicit owner instead of guessing by distance',()=>{
 const f=fixture();const nodes=[{id:'a',name:'Title',text:true},{id:'p',name:'Text plate',ownerIds:['a']},{id:'unknown',name:'Paper'}];
 assert.deepEqual(JSON.parse(JSON.stringify(f.context.SLTemplateTextModel.decorationOwners(nodes))),[{id:'p',owners:['a']}]);
});
test('dedicated title groups match each anonymous plate to its own text',()=>{
 const f=fixture(),nodes=[{id:'title',text:true,name:'Title',rect:{x:10,y:10,w:200,h:60}},
 {id:'body',text:true,name:'Body',rect:{x:10,y:85,w:200,h:20}},
 {id:'a',name:'Shape Layer 1',dedicatedTitle:true,rect:{x:5,y:5,w:210,h:70}},
 {id:'b',name:'Shape Layer 2',dedicatedTitle:true,rect:{x:5,y:80,w:210,h:30}},
 {id:'paper',name:'Torn Paper 2.png',dedicatedTitle:true,rect:{x:5,y:80,w:210,h:30}}];
 const out=JSON.parse(JSON.stringify(f.context.SLTemplateTextModel.decorationOwners(nodes)));
 assert.deepEqual(out,[{id:'a',owners:['title']},{id:'b',owners:['body']},{id:'paper',owners:['body']}]);
});
test('native decoration cleanup hides and restores a paper label while keeping media',()=>{
 const f=fixture(),Layer=f.title.constructor,c=new f.context.CompItem('Text group'),paper=new Layer('Text paper strip'),photo=new Layer('Photo frame');
 c.rows=[f.title,paper,photo];f.title.enabled=false;
 for(const l of c.rows){const original=l.property.bind(l);l.property=n=>n==='ADBE Transform Group'?{property:key=>({valueAtTime:()=>key==='ADBE Position'?[100,100]:key==='ADBE Scale'?[100,100]:key==='ADBE Anchor Point'?[0,0]:0})}:original(n);l.sourceRectAtTime=()=>({left:0,top:0,width:200,height:50});}
 assert.equal(f.context.SLTemplateText.cleanDecorations([c]).hidden,1);assert.equal(paper.enabled,false);assert.equal(photo.enabled,true);
 f.title.enabled=true;f.context.SLTemplateText.cleanDecorations([c]);assert.equal(paper.enabled,true);
 paper.enabled=false;paper.comment='';f.context.SLTemplateText.cleanDecorations([c]);assert.equal(paper.enabled,false,'owner-disabled decoration stays disabled');
});
test('3D paper strips and their shadow copies follow a dedicated title null, not a photo null',()=>{
 const f=fixture(),Layer=f.title.constructor,c=new f.context.CompItem('Scene 4');
 const titleGroup=new Layer('NULL'),photoGroup=new Layer('NULL 2');titleGroup.nullLayer=photoGroup.nullLayer=true;
 const text=new Layer('Text 7',null,'Mumbai'),paper=new Layer('Paper'),shadow=new Layer('Paper'),photo=new Layer('Media 12',new f.context.FootageItem()),photoPaper=new Layer('Paper');
 text.parent=paper.parent=titleGroup;shadow.parent=paper;photo.parent=photoPaper.parent=photoGroup;text.enabled=false;
 c.rows=[titleGroup,text,paper,shadow,photoGroup,photo,photoPaper];
 const result=f.context.SLTemplateText.cleanDecorations([c]);assert.equal(result.hidden,2);assert.equal(paper.enabled,false);assert.equal(shadow.enabled,false);assert.equal(photoPaper.enabled,true);assert.equal(photo.enabled,true);
 text.enabled=true;f.context.SLTemplateText.cleanDecorations([c]);assert.equal(paper.enabled,true);assert.equal(shadow.enabled,true);
});
function fixture(){let next=0,undos=0;const all=[],root={id:0};
 class FolderItem{constructor(name){this.id=++next;this.name=name;this.parentFolder=root;this.comment='';all.push(this)}get numItems(){return all.filter(i=>i.parentFolder===this).length}remove(){all.splice(all.indexOf(this),1)}}
 class FootageItem{}
 class TextProperty{constructor(text){this.doc={text,fontSize:60,font:'Owner Font'};this.numKeys=0;this.expression='';this.expressionEnabled=false}get value(){return {...this.doc}}valueAtTime(){return this.value}setValue(d){this.doc={...d}}}
 class Layer{constructor(name,source,text){this.id=++next;this.name=name;this.source=source;this.enabled=true;this.audioEnabled=false;this.locked=false;this.startTime=0;this.inPoint=0;this.outPoint=20;this.stretch=100;this.comment='';this.numProperties=0;this.text=text===undefined?null:new TextProperty(text)}property(key){if(key==='ADBE Text Properties')return this.text?{property:()=>this.text}:null;return {numProperties:0}}sourceRectAtTime(){return {width:this.text.value.text.length*this.text.value.fontSize*.5,height:this.text.value.fontSize}}replaceSource(source){this.source=source}}
 class CompItem{constructor(name,duration=20){this.id=++next;this.name=name;this.duration=duration;this.frameRate=30;this.parentFolder=root;this.comment='';this.rows=[];all.push(this)}get numLayers(){return this.rows.length}layer(i){return this.rows[i-1]}duplicate(){const c=new CompItem(this.name,this.duration);c.rows=this.rows.map(l=>{const d=new Layer(l.name,l.source,l.text?.value.text);Object.assign(d,{inPoint:l.inPoint,outPoint:l.outPoint,startTime:l.startTime,stretch:l.stretch,comment:l.comment,enabled:l.enabled});if(l.text){d.text.doc=l.text.value;d.text.expression=l.text.expression;d.text.expressionEnabled=l.text.expressionEnabled}return d});return c}remove(){all.splice(all.indexOf(this),1)}}
 const template=new CompItem('Main Template'),title=new Layer('Heading',null,'Lorem Ipsum');title.inPoint=5;title.outPoint=9;template.rows.push(title);const target=new CompItem('Final video',60),placed=new Layer('Placed template',template);placed.startTime=10;placed.inPoint=10;placed.outPoint=30;target.rows.push(placed);
 const project={rootFolder:root,activeItem:target,get numItems(){return all.length},item:i=>all[i-1],items:{addFolder:name=>new FolderItem(name)}};
 const context={app:{project,beginUndoGroup:()=>undos++,endUndoGroup(){}},CompItem,FolderItem,FootageItem,storylensProjectId:()=> 'owner.aep',hJSON:JSON.stringify,JSON,Math,Date};vm.createContext(context);for(const name of ['model.js','host.jsx'])vm.runInContext(fs.readFileSync('editor_plugins/template-text/'+name,'utf8'),context);
 const scan=()=>JSON.parse(context.storylensPanelTemplateText({action:'scan'}));
 function apply(snapshot,text='Mumbai won'){return JSON.parse(context.storylensPanelTemplateText({action:'apply',plan:{job_id:'owner-job',project_id:snapshot.project_id,composition_id:snapshot.composition_id,fingerprint:snapshot.fingerprint,actions:[{template_layer_id:String(placed.id),text_id:'1',action:'replace',text}]}}))}
 return {context,all,template,title,target,placed,scan,apply,undos:()=>undos};
}
test('essential text overrides follow the private replacement, leaving media overrides intact',()=>{
 const f=fixture(),Layer=f.title.constructor,original=new f.context.CompItem('Text'),copy=new f.context.CompItem('Text [SLTT test]');
 original.rows=[new Layer('Title',null,'Original title')];copy.rows=[new Layer('Title',null,'Rohit Sharma')];
 const source={matchName:'ADBE Text Document',propertyDepth:1,propertyGroup:()=>({index:1,containingComp:original})};
 let output=null,mediaReads=0;
 const ep={essentialPropertySource:source,numKeys:0,setValue:d=>output=d.text};
 const media={get essentialPropertySource(){return {matchName:'ADBE Layer Source Alternate'}},get value(){mediaReads++;throw Error('NO_VALUE')}};
 const group={numProperties:2,property:n=>n===1?ep:media};
 const result=f.context.SLTemplateText.syncOverrides(group,[{original,copy}]);
 assert.equal(output,'Rohit Sharma');assert.equal(mediaReads,0);assert.equal(result.changed,1);
 copy.rows[0].enabled=false;f.context.SLTemplateText.syncOverrides(group,[{original,copy}]);assert.equal(output,'');
});
test('essential text remapping refuses ambiguous repeated template branches',()=>{
 const f=fixture(),original=f.template,a=original.duplicate(),b=original.duplicate(),source={matchName:'ADBE Text Document',propertyDepth:1,propertyGroup:()=>({index:1,containingComp:original})};
 let writes=0;const ep={essentialPropertySource:source,numKeys:0,setValue:()=>writes++};
 const result=f.context.SLTemplateText.syncOverrides({numProperties:1,property:()=>ep},[{original,copy:a},{original,copy:b}]);
 assert.equal(writes,0);assert.equal(result.unresolved.length,1);
});
test('nested lettering is located at its final master interval after trim',()=>{const f=fixture(),s=f.scan().snapshot;assert.equal(s.templates[0].texts[0].runs[0].start,15);assert.equal(s.templates[0].texts[0].runs[0].end,19)});

test('static vertical background lettering and ancillary labels are not main heading candidates',()=>{
 const f=fixture(),Layer=f.title.constructor,nested=new f.context.CompItem('Text 3');nested.rows=[f.title];
 const layer=new Layer('Text 3',nested),original=layer.property.bind(layer);
 layer.property=n=>n==='ADBE Transform Group'?{property:k=>k==='ADBE Rotate Z'?{numKeys:0,expressionEnabled:false,value:90}:null}:original(n);
 f.template.rows=[layer];assert.equal(f.scan().snapshot.templates[0].texts[0].background_text,true);
 layer.property=original;layer.name='Edit_additional_text01';assert.equal(f.scan().snapshot.templates[0].texts[0].background_text,true);
});

test('an authored Text Effect precomp can contain the main readable heading',()=>{
 const f=fixture(),Layer=f.title.constructor,nested=new f.context.CompItem('Text_Effect_6');nested.rows=[f.title];
 f.template.rows=[new Layer('Text_Effect_6',nested)];assert.equal(f.scan().snapshot.templates[0].texts[0].background_text,false);
});

test('guide title branches cannot consume a visible heading slot',()=>{
 const f=fixture(),Layer=f.title.constructor,guide=new f.context.CompItem('Light Leak');guide.rows=[f.title];
 const layer=new Layer('Guide',guide);layer.guideLayer=true;f.template.rows=[layer];
 assert.equal(f.scan().snapshot.templates.length,0);
});
test('disabled precomp used as an active matte still exposes its authored title',()=>{
 const f=fixture(),Layer=f.title.constructor,matte=new f.context.CompItem('Title matte');matte.rows=[f.title];
 const layer=new Layer('Title matte',matte),fill=new Layer('Gold texture',new f.context.FootageItem());
 layer.enabled=false;layer.isTrackMatte=true;fill.trackMatteLayer=layer;f.template.rows=[layer,fill];
 assert.equal(f.scan().snapshot.templates[0].texts[0].id,'1/1');
});
test('a foreground text matte keeps its owned title strip visible',()=>{
 const f=fixture(),Layer=f.title.constructor,c=new f.context.CompItem('Text group'),nested=new f.context.CompItem('Title');nested.rows=[f.title];
 const matte=new Layer('Title matte',nested),strip=new Layer('Text paper strip');matte.enabled=false;matte.isTrackMatte=true;c.rows=[matte,strip];
 assert.equal(f.context.SLTemplateText.cleanDecorations([c]).hidden,0);assert.equal(strip.enabled,true);
});

test('text outside the placed interval is not evaluated or measured',()=>{const f=fixture();f.title.inPoint=80;f.title.outPoint=90;f.title.text.valueAtTime=()=>{throw Error('Invisible expression must not execute')};f.title.sourceRectAtTime=()=>{throw Error('Invisible lettering must not render')};const s=f.scan();assert.equal(s.ok,true);assert.equal(s.snapshot.templates.length,0)});

test('expression-controlled text uses its authored value and never renders its expression',()=>{const f=fixture();f.title.text.expressionEnabled=true;f.title.text.expression='comp("Missing original").layer(1).text.sourceText';f.title.text.valueAtTime=(time,pre)=>{assert.equal(pre,true);return f.title.text.value};f.title.sourceRectAtTime=()=>{throw Error('Expression rendering must not execute')};const s=f.scan();assert.equal(s.ok,true);assert.equal(s.snapshot.templates[0].texts[0].expression,f.title.text.expression);assert.match(f.apply(s.snapshot).error,/invalid or stale/)});

test('source-less layers are guarded even when a host type check is permissive',()=>{const f=fixture(),Comp=f.context.CompItem,normal=Function.prototype[Symbol.hasInstance].bind(Comp);Object.defineProperty(Comp,Symbol.hasInstance,{value:item=>item==null||normal(item)});f.template.rows.unshift(new f.title.constructor('Camera without source',null));const s=f.scan();assert.equal(s.ok,true);assert.equal(s.snapshot.templates[0].texts.length,1);assert.equal(f.context.SLTemplateText.containsText(f.template,{}),true)});
test('apply creates private native text and leaves original template and media references intact',()=>{const f=fixture(),scan=f.scan().snapshot,r=f.apply(scan);assert.equal(r.ok,true);assert.notEqual(f.placed.source,f.template);assert.equal(f.title.text.value.text,'Lorem Ipsum');assert.equal(f.placed.source.layer(1).text.value.text,'Mumbai won');assert.equal(f.undos(),1)});
for(const fail of [false,true])test('native preview rendering is suspended only during edits and restored: '+fail,()=>{const f=fixture(),scan=f.scan().snapshot;f.context.app.disableRendering=false;const duplicate=f.template.duplicate;f.template.duplicate=function(){assert.equal(f.context.app.disableRendering,true);if(fail)throw Error('Native duplication failed');return duplicate.call(this)};const result=f.apply(scan);assert.equal(!!result.ok,!fail);assert.equal(f.context.app.disableRendering,false)});
test('interrupted staged copies roll back without changing original sources or preview state',()=>{const f=fixture(),child=new f.context.CompItem('Nested'),Layer=f.title.constructor;child.rows=[f.title];f.template.rows=[new Layer('Nested title',child)];const s=f.scan().snapshot,before=f.all.length;f.context.app.disableRendering=true;f.context.SLTemplateText.progress=p=>{if(p.copies)throw Error('Probe stopped')};const plan={project_id:s.project_id,composition_id:s.composition_id,fingerprint:s.fingerprint,actions:[{template_layer_id:String(f.placed.id),text_id:'1/1',action:'hide',text:''}]};const r=JSON.parse(f.context.storylensPanelTemplateText({action:'apply',plan}));assert.match(r.error,/original template layers are kept/);assert.equal(f.all.length,before);assert.equal(f.placed.source,f.template);assert.equal(f.title.enabled,true);assert.equal(f.context.app.disableRendering,true);});
test('a timeline trim during model work refuses before creating anything',()=>{const f=fixture(),scan=f.scan().snapshot,before=f.all.length;f.placed.outPoint=29;const r=f.apply(scan);assert.match(r.error,/changed/);assert.equal(f.all.length,before);assert.equal(f.undos(),0)});
test('reopening an unchanged saved project does not invalidate its text plan',()=>{const f=fixture();f.context.app.project.revision=908;const scan=f.scan().snapshot;f.context.app.project.revision=1;assert.equal(f.apply(scan).ok,true)});
test('unused empty text is disabled in private templates even outside the visible scan',()=>{const f=fixture(),empty=new f.title.constructor('Empty',null,' \r\n');empty.inPoint=80;empty.outPoint=90;f.template.rows.push(empty);const s=f.scan().snapshot;assert.equal(s.templates[0].texts.length,1);const r=f.apply(s);assert.equal(r.ok,true);assert.equal(f.placed.source.layer(2).enabled,false);assert.equal(empty.enabled,true)});

test('unchanged offscreen branches stay shared, but nested empty text gets a private disabled copy',()=>{
 const f=fixture(),Layer=f.title.constructor,untouched=new f.context.CompItem('Offscreen artwork'),empty=new f.context.CompItem('Offscreen blank');
 untouched.rows=[new Layer('Authored title',null,'Owner lettering')];empty.rows=[new Layer('Blank',null,'   ')];
 const a=new Layer('Art',untouched),b=new Layer('Blank branch',empty);a.inPoint=b.inPoint=80;a.outPoint=b.outPoint=90;f.template.rows.push(a,b);
 const result=f.apply(f.scan().snapshot);assert.equal(result.ok,true);assert.equal(f.placed.source.layer(2).source,untouched);assert.notEqual(f.placed.source.layer(3).source,empty);assert.equal(f.placed.source.layer(3).source.layer(1).enabled,false);assert.equal(empty.layer(1).enabled,true);assert.equal(result.copies,2);
});
test('one operation indexes repeated text-free branches once and a new operation sees edits',()=>{
 const f=fixture(),Layer=f.title.constructor;let reads=0,child=new f.context.CompItem('Empty leaf');
 for(let i=0;i<30;i++){const parent=new f.context.CompItem('Parent '+i);parent.rows=[new Layer('A',child),new Layer('B',child)];const original=parent.layer;parent.layer=function(n){reads++;return original.call(this,n)};child=parent;}
 const hasText=f.context.SLTemplateText.textIndex();for(let i=0;i<100;i++)assert.equal(hasText(child),false);
 assert.ok(reads<=60,'repeated host lookups: '+reads);child.rows.push(f.title);
 assert.equal(f.context.SLTemplateText.textIndex()(child),true);
});
test('text reachability propagates through shared ancestors and cycles without recursion',()=>{
 const f=fixture(),Layer=f.title.constructor,leaf=f.template;let child=leaf;
 for(let i=0;i<100;i++){const c=new f.context.CompItem('Ancestor '+i);c.rows=[new Layer('Child',child),new Layer('Shared',leaf)];child=c;}
 leaf.rows.push(new Layer('Cycle',child));const has=f.context.SLTemplateText.textIndex();assert.equal(has(child),true);assert.equal(has(leaf),true);
 const sibling=new f.context.CompItem('Sibling');sibling.rows=[new Layer('Shared positive',child)];assert.equal(has(sibling),true);
});
for(const different of [false,true])test('repeated precomps share private copies only with identical edits: '+different,()=>{
 const f=fixture(),child=new f.context.CompItem('Repeated text'),Layer=f.title.constructor;child.rows.push(f.title);f.template.rows=[new Layer('Left',child),new Layer('Right',child)];
 const s=f.scan().snapshot,plan={job_id:'owner-job',project_id:s.project_id,composition_id:s.composition_id,fingerprint:s.fingerprint,actions:s.templates[0].texts.map((r,i)=>({template_layer_id:String(f.placed.id),text_id:r.id,action:'replace',text:different&&i?'Chennai won':'Mumbai won'}))};
 const result=JSON.parse(f.context.storylensPanelTemplateText({action:'apply',plan}));assert.equal(result.ok,true);assert.equal(f.placed.source.layer(1).source===f.placed.source.layer(2).source,!different);assert.equal(f.title.text.value.text,'Lorem Ipsum');
});
test('text edits are still rejected after a project session counter resets',()=>{const f=fixture();f.context.app.project.revision=908;const scan=f.scan().snapshot;f.context.app.project.revision=1;f.title.text.doc.text='Owner revised title';assert.match(f.apply(scan).error,/changed/);assert.equal(f.undos(),0)});

for(const keepSecond of [false,true])test('repeated trimmed filler shares copies only when visible kept text is safe: '+keepSecond,()=>{
 const f=fixture(),Layer=f.title.constructor,child=new f.context.CompItem('Shared scene');
 const early=new Layer('Early',null,'Early filler'),late=new Layer('Late',null,'Late filler');early.inPoint=0;early.outPoint=5;late.inPoint=5;late.outPoint=10;child.rows=[early,late,new Layer('Retained photo',new f.context.FootageItem())];
 const left=new Layer('Early scene',child),right=new Layer('Late scene',child);left.inPoint=0;left.outPoint=5;right.inPoint=5;right.outPoint=10;f.template.rows=[left,right];
 const snapshot=f.scan().snapshot,rows=snapshot.templates[0].texts;
 assert.deepEqual(rows.map(r=>r.id),['1/1','2/2']);
 const plan={project_id:snapshot.project_id,composition_id:snapshot.composition_id,fingerprint:snapshot.fingerprint,actions:rows.filter((r,i)=>!keepSecond||i===0).map(r=>({template_layer_id:String(f.placed.id),text_id:r.id,action:'hide',text:''}))};
 const result=JSON.parse(f.context.storylensPanelTemplateText({action:'apply',plan}));assert.equal(result.ok,true);
 const a=f.placed.source.layer(1).source,b=f.placed.source.layer(2).source;
 assert.equal(a===b,!keepSecond);assert.equal(a.layer(1).enabled,false);assert.equal(b.layer(2).enabled,keepSecond);
 assert.equal(early.enabled,true);assert.equal(late.enabled,true);assert.equal(result.copies,2);
});

test('native item lookup uses AE ID lookup without scanning thousands of project items',()=>{const f=fixture();let reads=0;f.context.app.project.itemByID=id=>{reads++;return f.all.find(x=>x.id===id)||null};f.context.app.project.item=()=>{throw Error('Linear project scan is forbidden')};assert.equal(f.context.SLTemplateText.item(String(f.target.id)),f.target);assert.equal(f.context.SLTemplateText.item('999999'),null);assert.equal(reads,2)});

test('a repeated scene hashes long expression state once while keeping each visible interval guarded',()=>{
 const f=fixture(),Layer=f.title.constructor;f.title.text.expressionEnabled=true;f.title.text.expression='"'+('Long controller '.repeat(1000))+'"';f.template.rows=[new Layer('A',null,'Base')];
 const shared=new f.context.CompItem('Shared');shared.rows=[f.title];for(let i=0;i<30;i++)f.template.rows.push(new Layer('Instance '+i,shared));
 const compact=f.context.SLTemplateText.scan(f.target),legacy=f.context.SLTemplateText.scan(f.target,{legacy:true});assert.match(compact.fingerprint,/^v2:/);assert.ok(Number(compact.fingerprint.split(':')[1])*4<Number(legacy.fingerprint.split(':')[0]));
 f.template.rows[10].outPoint=15;assert.notEqual(f.context.SLTemplateText.scan(f.target).fingerprint,compact.fingerprint);
 f.title.text.expression+=' ';assert.notEqual(f.context.SLTemplateText.scan(f.target).fingerprint,compact.fingerprint);
});

for(const artwork of [false,true])test('filler-only text precomps switch off without duplication while artwork stays intact: '+artwork,()=>{
 const f=fixture(),Layer=f.title.constructor,child=new f.context.CompItem('Filler paragraph');child.rows=[f.title];if(artwork)child.rows.push(new Layer('Picture',new f.context.FootageItem()));
 f.template.rows=[new Layer('Paragraph precomp',child)];const s=f.scan().snapshot;
 const plan={project_id:s.project_id,composition_id:s.composition_id,fingerprint:s.fingerprint,actions:[{template_layer_id:String(f.placed.id),text_id:'1/1',action:'hide',text:''}]};
 const result=JSON.parse(f.context.storylensPanelTemplateText({action:'apply',plan}));assert.equal(result.ok,true);
 const parent=f.placed.source.layer(1);assert.equal(parent.enabled,artwork);assert.equal(result.copies,artwork?2:1);assert.equal(child.layer(1).enabled,true);
 if(artwork){assert.notEqual(parent.source,child);assert.equal(parent.source.layer(1).enabled,false);assert.equal(parent.source.layer(2).enabled,true);}else assert.equal(parent.source,child);
});

test('a later pass can revive a heading inside a previously muted text-only branch',()=>{
 const f=fixture(),Layer=f.title.constructor,child=new f.context.CompItem('Filler paragraph');child.rows=[f.title];f.template.rows=[new Layer('Paragraph precomp',child)];
 let s=f.scan().snapshot;const apply=action=>JSON.parse(f.context.storylensPanelTemplateText({action:'apply',plan:{project_id:s.project_id,composition_id:s.composition_id,fingerprint:s.fingerprint,actions:[{template_layer_id:String(f.placed.id),text_id:'1/1',...action}]}}));
 assert.equal(apply({action:'hide',text:''}).ok,true);assert.equal(f.placed.source.layer(1).enabled,false);s=f.scan().snapshot;assert.equal(s.templates[0].texts[0].text,'Lorem Ipsum');assert.equal(apply({action:'replace',text:'Mumbai won'}).ok,true);assert.equal(f.placed.source.layer(1).enabled,true);assert.equal(f.placed.source.layer(1).source.layer(1).text.value.text,'Mumbai won');assert.equal(f.title.text.value.text,'Lorem Ipsum');
});
test('another active composition refuses instead of applying to the previous project',()=>{const f=fixture(),scan=f.scan().snapshot;f.context.app.project.activeItem=f.template;assert.match(f.apply(scan).error,/same final composition/);assert.equal(f.undos(),0)});
test('expression-controlled Source Text remains untouched',()=>{const f=fixture();f.title.text.expressionEnabled=true;f.title.text.expression='"Owner value"';const scan=f.scan().snapshot;assert.match(f.apply(scan).error,/invalid or stale/);assert.equal(f.undos(),0)});
test('unreadably long headings are hidden instead of shrinking the whole template',()=>{const f=fixture(),scan=f.scan().snapshot,r=f.apply(scan,'A very very very very very very long headline');assert.equal(r.ok,true);assert.equal(r.hidden,1);assert.equal(f.placed.source.layer(1).enabled,false);assert.equal(f.title.enabled,true)});
test('a very large title can fit a full player name while remaining readable',()=>{const f=fixture();f.title.text.doc.text='to fight';f.title.text.doc.fontSize=316;const r=f.apply(f.scan().snapshot,'Sachin Tendulkar');assert.equal(r.ok,true);assert.equal(r.changed,1);assert.equal(f.placed.source.layer(1).enabled,true);assert.ok(f.placed.source.layer(1).text.value.fontSize>100)});
test('expression relocation does not rewrite comments and ordinary text literals',()=>{const f=fixture(),source='// comp("Title")\nvar s="comp(Title)";comp("Title").width';const after=f.context.SLTemplateTextModel.expression(source,{Title:'Private Title'});assert.match(after,/\/\/ comp\("Title"\)/);assert.match(after,/Private Title/)});

test('Copy Paste progress is not rebound merely because slot counts are equal',()=>{const f=fixture(),scan=f.scan().snapshot;f.context.SLCopyPaste={graph:x=>x};f.context.SLCopyPasteModel={state:()=>({owner:String(f.placed.id),root:String(f.template.id),next:1,signature:'old'}),scan:(graph)=>({signature:graph===f.template?'old':'new',slots:[{source:graph===f.template?'photo1':'photo2',path:'Image 1',layers:[1]}]}),writeState:()=> 'rebound'};const r=f.apply(scan);assert.equal(r.ok,true);assert.notEqual(f.placed.comment,'rebound');assert.ok(r.warnings.some(s=>/slot progress/.test(s)))});
test('valid ordered media correspondence preserves the next Copy Paste slot',()=>{const f=fixture(),scan=f.scan().snapshot;f.context.SLCopyPaste={graph:x=>x};f.context.SLCopyPasteModel={state:()=>({owner:String(f.placed.id),root:String(f.template.id),next:1,signature:'old'}),scan:(graph)=>({signature:graph===f.template?'old':'new',slots:[{source:'photo1',path:'Image 1',layers:[1]}]}),writeState:(comment,state)=> 'next='+state.next+';root='+state.root};const r=f.apply(scan);assert.equal(r.ok,true);assert.equal(f.placed.comment,'next=1;root='+f.placed.source.id)});
test('native files avoid ES3 reserved object keys and identifiers',()=>{for(const name of ['host.jsx','model.js']){const s=fs.readFileSync('editor_plugins/template-text/'+name,'utf8');assert.doesNotMatch(s,/[{,]\s*(?:protected|private|public|class|const|let|yield|interface|package|implements)\s*:/);assert.doesNotMatch(s,/\b(?:var|function)\s+(?:protected|private|public|class|const|let|interface|package|implements)\b/)}});

test('renamed private compositions preserve authored thisComp.name expression semantics',()=>{const f=fixture(),source='// thisComp.name\nvar label="thisComp.name"; thisComp.name.split(" ")[0]';const after=f.context.SLTemplateTextModel.expression(source,{'Main':'Private'},'Main 01');assert.match(after,/"Main 01"\.split/);assert.match(after,/var label="thisComp.name"/);assert.match(after,/\/\/ thisComp.name/)});
test('repeat repairs resolve original controller names within the same template only',()=>{
 const f=fixture(),names={};f.context.SLTemplateText.alias(names,'Final Comp [SLTT old]','Final Comp [SLTT new]');
 assert.equal(names['Final Comp'],'Final Comp [SLTT new]');
 assert.equal(names['Final Comp [SLTT old]'],'Final Comp [SLTT new]');
 f.context.SLTemplateText.alias(names,'Final Comp [SLTT other]','Different copy');
 f.context.SLTemplateText.alias(names,'Final Comp [SLTT third]','Third copy');
 assert.equal(names['Final Comp'],null,'ambiguous controller names cannot silently bind to another template');
});
test('a name-only expression does not embed the whole template alias table',()=>{const f=fixture(),names={};for(let i=0;i<1000;i++)names['Original '+i]='Private '+i;const after=f.context.SLTemplateTextModel.expression('thisComp.name',names,'Heading 01');assert.equal(after,'"Heading 01"');});
test('literal composition references stay compact and unknown names stay unchanged',()=>{const f=fixture(),names={};for(let i=0;i<1000;i++)names['Original '+i]='Private '+i;assert.equal(f.context.SLTemplateTextModel.expression('comp("Original 7").width',names),'comp("Private 7").width');assert.equal(f.context.SLTemplateTextModel.expression('comp("External").width',names),'comp("External").width');assert.match(f.context.SLTemplateTextModel.expression('comp(prefix + index).width',names),/function __storylensCompRef/);});
test('literal optimization preserves escaped names and does not consume concatenated arguments',()=>{const f=fixture(),names={'A"B':'Private'};assert.equal(f.context.SLTemplateTextModel.expression('comp("A\\"B").width',names),'comp("Private").width');assert.match(f.context.SLTemplateTextModel.expression('comp("A" + suffix).width',names),/function __storylensCompRef/);});

test('a later text pass can revive a date slot previously hidden by Template Text',()=>{const f=fixture(),first=f.scan().snapshot;const hidden=JSON.parse(f.context.storylensPanelTemplateText({action:'apply',plan:{job_id:'first',project_id:first.project_id,composition_id:first.composition_id,fingerprint:first.fingerprint,actions:[{template_layer_id:String(f.placed.id),text_id:'1',action:'hide',text:''}]}}));assert.equal(hidden.ok,true);assert.equal(f.placed.source.layer(1).enabled,false);const second=f.scan().snapshot;assert.equal(second.templates[0].texts[0].enabled,true);assert.equal(f.apply(second,'2020').ok,true);assert.equal(f.placed.source.layer(1).enabled,true);assert.equal(f.placed.source.layer(1).text.value.text,'2020')});

test('refresh restores original slot font size and fitting bounds rather than shrinking cumulatively',()=>{const f=fixture(),original=f.title.text.value.fontSize;assert.equal(f.apply(f.scan().snapshot,'Mumbai Indians').ok,true);assert.ok(f.placed.source.layer(1).text.value.fontSize<original);assert.equal(f.apply(f.scan().snapshot,'MI').ok,true);assert.equal(f.placed.source.layer(1).text.value.fontSize,original);assert.equal(f.scan().snapshot.templates[0].texts[0].bounds.width,'Lorem Ipsum'.length*original*.5)});

test('manual font-size edits invalidate a scan even when baseline fitting metadata is retained',()=>{const f=fixture();assert.equal(f.apply(f.scan().snapshot,'MI').ok,true);const scan=f.scan().snapshot;f.placed.source.layer(1).text.doc.fontSize=55;assert.match(f.apply(scan).error,/changed/)});

test('a padded paper label belongs to its centered title only inside a dedicated title group',()=>{
 const f=fixture(),text={id:'caption',text:true,rect:{x:1303,y:1596,w:591,h:84}};
 const paper={id:'paper',name:'Torn Paper 2.png',dedicatedTitle:true,rect:{x:1150,y:1500,w:900,h:256}};
 assert.equal(f.context.SLTemplateTextModel.decorationOwners([text,paper])[0].owners[0],'caption');
 paper.dedicatedTitle=false;assert.equal(f.context.SLTemplateTextModel.decorationOwners([text,paper]).length,0);
 paper.dedicatedTitle=true;paper.rect.h=900;assert.equal(f.context.SLTemplateTextModel.decorationOwners([text,paper]).length,0);
});

test('title geometry requires readable in-frame ink for most of the sampled scene',()=>{
 const m=fixture().context.SLTemplateTextModel;
 const good={left:500,right:800,top:300,bottom:345},off={left:2500,right:2800,top:300,bottom:345},tiny={left:500,right:600,top:300,bottom:309};
 assert.equal(m.titleGeometry([good,good,off],1920,1080).usable,true);
 assert.equal(m.titleGeometry([good,off,off],1920,1080).usable,false);
 assert.equal(m.titleGeometry([tiny,tiny,tiny],1920,1080).usable,false);
});

test('a failed camera probe is removed and its unmeasured title is not offered as a confident slot',()=>{
 const f=fixture(),snapshot=f.scan().snapshot;let removed=0;
 const point={valueAtTime:()=>{throw Error('Camera expression unavailable')}};
 f.target.layers={addShape:()=>({property:()=>({addProperty:()=>({property:()=>point})}),remove:()=>removed++})};
 f.context.SLTemplateText.projectTitles(f.target,snapshot);
 assert.equal(removed,1);assert.equal(snapshot.templates[0].texts[0].projected.usable,false);
 assert.ok(snapshot.warnings.some(w=>/positions need visual review/.test(w)));
});
