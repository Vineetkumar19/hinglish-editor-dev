const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(host='aftereffects',answers=[{ok:true,placements:[{},{}],covered_duration:9,uncovered_duration:831}],storage=new Map()){
 function el(){return {hidden:false,value:'',children:[],disabled:false,append(...a){this.children.push(...a)},replaceChildren(...a){this.children=[...a]},textContent:''}}
 const nodes=Object.fromEntries(['templateAlinerSection','templateAliner','templateAlinerChoices','templateAlinerReset','templateAlinerStatus','templateFontCheck','templateFontDetails','templateFontList','templateFontStatus','templateCollapseFolders','templateCollapseNow','templateFolderStatus'].map(id=>[id,el()]));
 const calls=[],errors=[],context={window:{},localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},document:{getElementById:id=>nodes[id],createElement:el},Object,Array,Math,Number,String,Error};
 vm.createContext(context);vm.runInContext(fs.readFileSync('hinglish_app/static/template-aliner.js','utf8'),context);
 context.window.storylensTemplateAliner({host,native:async(action,payload)=>{calls.push({action,payload});return answers.shift()},showError:e=>errors.push(e),clearError(){}});
 return {nodes,calls,errors};
}
test('Template Aliner stays inside AE and makes only the named native request',async()=>{
 const f=fixture();assert.equal(f.nodes.templateAlinerSection.hidden,false);await f.nodes.templateAliner.onclick();
 assert.equal(f.calls.length,1);assert.equal(f.calls[0].action,'templateAlign');assert.equal(f.calls[0].payload.repeat,undefined);
 assert.match(f.nodes.templateAlinerStatus.textContent,/2 template/);assert.match(f.nodes.templateAlinerStatus.textContent,/13:51.*uncovered/);
 assert.equal(f.nodes.templateAliner.disabled,false);
 const pp=fixture('premiere');assert.equal(pp.nodes.templateAlinerSection.hidden,true);
});

test('folder cleanup defaults on, is sent with alignment, and remembers opt-out',async()=>{
 const storage=new Map(),f=fixture('aftereffects',undefined,storage);
 assert.equal(f.nodes.templateCollapseFolders.checked,true);await f.nodes.templateAliner.onclick();assert.equal(f.calls[0].payload.collapse_folders,true);
 f.nodes.templateCollapseFolders.checked=false;f.nodes.templateCollapseFolders.onchange();
 const next=fixture('aftereffects',undefined,storage);assert.equal(next.nodes.templateCollapseFolders.checked,false);
 await next.nodes.templateAliner.onclick();assert.equal(next.calls[0].payload.collapse_folders,false);
});

test('folder cleanup failure is a warning after a successful alignment, not a reason to rerun',async()=>{
 const f=fixture('aftereffects',[{ok:true,placements:[{}],covered_duration:10,uncovered_duration:0,ui_cleanup:{ok:false,message:'Clear the Project search before collapsing folders.'}}]);
 await f.nodes.templateAliner.onclick();assert.equal(f.errors.length,0);assert.match(f.nodes.templateAlinerStatus.textContent,/1 template/);assert.match(f.nodes.templateFolderStatus.textContent,/Clear the Project search/);
});

test('collapse-now uses only the folder cleanup action',async()=>{
 const f=fixture('aftereffects',[{ok:true,ui_cleanup:{ok:true,message:'Project folders collapsed.'}}]);
 await f.nodes.templateCollapseNow.onclick();assert.equal(f.calls[0].action,'templateCollapseFolders');assert.match(f.nodes.templateFolderStatus.textContent,/collapsed/);
});
test('one click sends no main-composition questions or user choices',async()=>{
 const f=fixture();await f.nodes.templateAliner.onclick();assert.equal(f.calls.length,1);
 assert.equal(f.calls[0].payload.choices,undefined);assert.equal(f.nodes.templateAlinerChoices.children.length,0);
});
test('the shipped panel exposes the AE action and packages both native dependencies',()=>{
 assert.match(fs.readFileSync('hinglish_app/static/editor-panel.html','utf8'),/id="templateAliner"[^>]*class="[^"]*guarded-run[^"]*"[^>]*>Run Template Aliner</);
 assert.match(fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8'),/calls\.templateAlign\s*=\s*'storylensPanelTemplateAlign'/);
 const host=fs.readFileSync('editor_plugins/after-effects-cep/jsx/host.jsx','utf8');
 assert.match(host,/#include "template-aliner-model.js"/);assert.match(host,/#include "template-aliner.jsx"/);
});

test('font check lists an unavailable face honestly and does not launch alignment',async()=>{
 const f=fixture('aftereffects',[{ok:true,font_report:{checked:true,missing:[{name:'FutureMissing-Bold',occurrences:2}],policy:'native-substitution'}}]);
 await f.nodes.templateFontCheck.onclick();assert.equal(f.calls[0].action,'templateFonts');
 assert.match(f.nodes.templateFontStatus.textContent,/temporary substitute/i);
 assert.match(f.nodes.templateFontList.children[0].textContent,/FutureMissing-Bold/);assert.equal(f.nodes.templateFontDetails.hidden,false);
});

test('failure reason is visible beside the action instead of only below the fold',async()=>{const f=fixture('aftereffects',[{error:'Open the main video composition on the timeline, then press Template Aliner.',code:'template_aliner'}]);await f.nodes.templateAliner.onclick();assert.match(f.nodes.templateAlinerStatus.textContent,/main video composition/);assert.equal(f.errors.length,1)});
