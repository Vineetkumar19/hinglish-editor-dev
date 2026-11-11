const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function library(){
 const nodes={};let created=0,version=1;
 const el=id=>nodes[id]||(nodes[id]={id,children:[],attributes:{},events:{},hidden:false,scrollWidth:1000,clientWidth:300,scrollLeft:0,setAttribute(k,v){this.attributes[k]=v;},replaceChildren(...items){this.children=items;},append(...items){this.children.push(...items);},addEventListener(k,fn){this.events[k]=fn;},scrollBy(p){this.scrollLeft+=p.left;}});
 const c={document:{getElementById:el,createElement:()=>el('new-'+(++created))},window:{addEventListener(){},storylensError:e=>e.message},Date,Math,setInterval:()=>1,setTimeout,clearTimeout};
 vm.runInNewContext(fs.readFileSync('hinglish_app/static/preset-library.js','utf8'),c);
 const tab=el('animationPresetsHome');tab.onclick=()=>{tab.clicked=true;};
 const view=c.window.storylensPresetLibrary({extraTabs:[tab],native:async action=>action==='categories'?{categories:[{id:'text',name:'Text'},{id:'fx',name:'Effects'},...(version===2?[{id:'new',name:'New pack'}]:[])]}:{packs:[]},isBusy:()=>false,clearError(){},showError:e=>{throw e;},onSelect(){tab.setAttribute('aria-pressed','false');}});
 return {view,nodes,tab,update(){version=2;}};
}
test('Presets remains first in the header across category selection, hiding and automatic catalog changes',async()=>{
 const h=library();await h.view.init();assert.equal(h.nodes.presetCategoryStrip.children[0],h.tab);
 await h.nodes.presetCategoryStrip.children[1].onclick();h.view.hide();h.update();await h.view.refresh();
 assert.equal(h.nodes.presetCategoryStrip.children[0],h.tab);assert.equal(h.nodes.presetCategoryStrip.children.length,4);h.tab.onclick();assert.equal(h.tab.clicked,true);
});
test('header wheel scrolls both directions, normalizes wheel lines/pages and respects pinch zoom',async()=>{
 const h=library();await h.view.init();const strip=h.nodes.presetCategoryStrip,fn=strip.events.wheel;
 function wheel(deltaY,deltaX=0,deltaMode=0,ctrlKey=false){let prevented=false;fn({deltaY,deltaX,deltaMode,ctrlKey,preventDefault(){prevented=true;}});return prevented;}
 assert.equal(wheel(100),true);assert.equal(strip.scrollLeft,100);wheel(-40);assert.equal(strip.scrollLeft,60);wheel(0,20);assert.equal(strip.scrollLeft,80);wheel(2,0,1);assert.equal(strip.scrollLeft,144);wheel(1,0,2);assert.equal(strip.scrollLeft,444);wheel(1000);assert.equal(strip.scrollLeft,700);wheel(-1000);assert.equal(strip.scrollLeft,0);
 assert.equal(wheel(100,0,0,true),false);strip.scrollWidth=100;assert.equal(wheel(100),false);assert.equal(strip.scrollLeft,0);
});
test('Presets opens directly with the tools grid hidden; returning to ordinary tools clears the selected header tab',()=>{
 const source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8'),fn=source.slice(source.indexOf('function select('),source.indexOf('function patchUtility('));
 const nodes={},el=id=>nodes[id]||(nodes[id]={hidden:false,attributes:{},dataset:{},append(){},setAttribute(k,v){this.attributes[k]=v;},querySelectorAll(){return [];}});let opens=0,hides=0;
 const c={$:el,document:{querySelector:el,body:{dataset:{}}},host:'aftereffects',mode:'clean',labels:{animationPresets:'Presets',clean:'Smart Clean'},clearError(){},presetView:{hide(){}},animationPresetView:{open(){opens++;},hide(){hides++;}}};
 vm.createContext(c);vm.runInContext(fn,c);c.select('animationPresets');assert.equal(nodes.tools.hidden,true);assert.equal(nodes.animationPresetSection.hidden,false);assert.equal(nodes.editingControls.hidden,true);assert.equal(nodes.animationPresetsHome.attributes['aria-pressed'],'true');assert.equal(nodes.storylensHome.attributes['aria-pressed'],'false');assert.equal(opens,1);
 c.select('clean');assert.equal(nodes.tools.hidden,false);assert.equal(nodes.animationPresetSection.hidden,true);assert.equal(nodes.animationPresetsHome.attributes['aria-pressed'],'false');assert.equal(hides,1);
 const html=fs.readFileSync('hinglish_app/static/editor-panel.html','utf8');assert.match(html,/<nav id="presetCategoryStrip"[^>]*><button id="animationPresetsHome"/);assert.doesNotMatch(source,/for\(const tool of \['animationPresets','templateAligner'/);
 assert.ok(source.includes("if(mode==='clean')select('clean',true);"),'late initialization must preserve an already opened Presets workspace');
 const css=fs.readFileSync('hinglish_app/static/preset-library.css','utf8');assert.match(css,/scrollbar-width:none/);assert.match(css,/#presetCategoryStrip::-webkit-scrollbar\{height:0;width:0;display:none\}/);
});
