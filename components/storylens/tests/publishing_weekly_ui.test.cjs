const test=require('node:test'),assert=require('node:assert/strict');
const {render}=require('../hinglish_app/static/publishing-weekly.js');
class Element{constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.value='';this.checked=false;this.disabled=false;}append(...n){this.children.push(...n);}}
const walk=n=>[n,...n.children.flatMap(walk)];
test('weekly plan generation is explicit and bounded to one through four weeks',()=>{
 global.document={createElement:tag=>new Element(tag)};
 const host=new Element('div'),calls=[];
 render(host,{mode:'long',copy:{},generateWeekly:n=>calls.push(n),weeklyLocked:false});
 const nodes=walk(host),select=nodes.find(n=>n.tag==='select');
 assert.deepEqual(select.children.map(n=>n.value),['1','2','3','4']);assert.deepEqual(calls,[]);
 select.value='4';nodes.find(n=>n.textContent==='Generate weekly packages · V8').onclick();assert.deepEqual(calls,[4]);
 assert.equal(nodes.some(n=>n.textContent?.startsWith('Enable this')),false);
 const shorts=new Element('div');assert.equal(render(shorts,{mode:'shorts',generateWeekly(){}}),null);
});
test('week count cannot silently change an already generated plan; enabling sends reviewed text and explicit image choice',()=>{
 global.document={createElement:tag=>new Element(tag)};
 const row={week:1,title:'Supported title',description:'Supported description #Cricket #IPL #Analysis',tags:[],reason:'Supported angle',thumbnail:{text:'ONE STORY',subject:'Cricket',composition:'One subject',style:'Contrast'}};
 const host=new Element('div'),calls=[];render(host,{mode:'long',copy:{weekly_seo:{status:'ready',weeks:1,revision:'v1',variants:[row]}},preparation:{},generateWeekly(){},enableWeekly:v=>calls.push(v),weeklyLocked:false});
 const nodes=walk(host),select=nodes.find(n=>n.tag==='select'),enable=nodes.find(n=>n.textContent==='Enable this 1-week browser plan');
 select.value='4';select.onchange();assert.equal(enable.disabled,true);
 select.value='1';select.onchange();enable.onclick();assert.equal(calls[0].revision,'v1');assert.equal(calls[0].change_thumbnails,false);assert.equal(calls[0].variants[0].title,row.title);
});
