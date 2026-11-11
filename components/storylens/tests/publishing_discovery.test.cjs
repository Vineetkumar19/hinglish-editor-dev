const test=require('node:test'),assert=require('node:assert/strict');
const {checks,thumbnailDraft,render}=require('../hinglish_app/static/publishing-discovery.js');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.value='';this.listeners=new Map();}
 append(...rows){this.children.push(...rows);}
 replaceChildren(...rows){this.children=[...rows];}
 setAttribute(k,v){this[k]=v;}
 addEventListener(k,v){this.listeners.set(k,v);}
 removeEventListener(k,v){if(this.listeners.get(k)===v)this.listeners.delete(k);}
}
const walk=n=>[n,...n.children.flatMap(walk)];
const plan={status:'ready',primary_query:'Punjab Kings brand value',secondary_queries:[],intent:'information',
 description:'A supported summary #PunjabKings #IPL #Cricket',tags:['Punjab Kings'],research:{status:'unavailable'},
 titles:['search','browse','hybrid'].map((angle,i)=>({angle,title:'Punjab Kings story '+i,reason:'Matches the actual story'})),
 thumbnail:{text:'MISSING IDENTITY',subject:'Punjab Kings',composition:'One focal subject',style:'Team colours'}};
test('presentation checks do not invent quality scores or require title numbers',()=>{
 assert.equal(checks('Punjab Kings Brand Value','MISSING IDENTITY').length,0);
 assert.ok(checks('Punjab Kings Brand Value','Punjab Kings Brand Value').some(n=>n.includes('repeats')));
});
test('thumbnail handoff retains references and exact wording without invoking generation',()=>{
 const previous={refs:{portrait:'owner.png'},seed:'42',generate:true};const d=thumbnailDraft(plan,previous);
 assert.deepEqual(d.refs,previous.refs);assert.equal(d.title,'MISSING IDENTITY');assert.equal(d.text_mode,'exact');
 assert.equal(previous.title,undefined);assert.equal(d.aspect,'16:9');
});
test('review applies only explicitly selected fields, locks submitted copy and keeps Shorts without a cover action',()=>{
 global.document={createElement:tag=>new Element(tag)};global.localStorage={getItem:()=>null,setItem(){throw Error('quota');}};
 const host=new Element('div'),title=new Element('input'),changes=[];
 title.value='Existing title';const options={copy:{discovery:plan},id:'a',mode:'shorts',title,apply:v=>changes.push(v),save(){}};
 render(host,options);let nodes=walk(host);assert.equal(changes.length,0);
 nodes.find(n=>n.textContent==='Use title').onclick();assert.deepEqual(changes,[{title:plan.titles[0].title}]);
 assert.equal(nodes.some(n=>n.tag==='a'),false);
 render(host,{...options,locked:true});nodes=walk(host);assert.ok(nodes.filter(n=>n.tag==='button').every(n=>n.disabled));
 assert.equal(title.listeners.size,1);
 render(host,{...options,copy:{},id:'legacy'});assert.equal(title.listeners.size,0);
 assert.ok(walk(host).some(n=>n.textContent?.includes('saved preparation has no SEO')));
});
test('brief handoff backs up the existing draft and reports storage failure without opening',()=>{
 global.document={createElement:tag=>new Element(tag)};
 const saved=new Map([['storylens-thumbnail-studio-v1',JSON.stringify({refs:{portrait:'owner.png'}})]]);
 global.localStorage={getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)};
 const host=new Element('div'),title=new Element('input');title.value='Existing title';
 render(host,{copy:{discovery:plan},id:'b',mode:'long',title,apply(){},save(){}});
 const link=walk(host).find(n=>n.tag==='a');link.onclick({preventDefault(){throw Error('Unexpected failure');}});
 assert.equal(saved.size,2);assert.equal(JSON.parse(saved.get('storylens-thumbnail-studio-v1')).refs.portrait,'owner.png');
 global.localStorage.setItem=()=>{throw Error('quota');};let prevented=false;link.onclick({preventDefault(){prevented=true;}});
 assert.equal(prevented,true);assert.ok(walk(host).some(n=>n.textContent?.includes('could not be saved')));
});
