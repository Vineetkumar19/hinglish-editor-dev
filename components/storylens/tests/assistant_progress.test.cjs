const {test}=require('node:test'),assert=require('node:assert/strict');
const {build}=require('../hinglish_app/static/assistant-progress.js');
test('progress polling retains the same scroll container and reader position',()=>{
 const {render}=require('../hinglish_app/static/assistant-progress.js');
 class Element{
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.scrollTop=0;this.scrollLeft=0;this.className='';}
  get childNodes(){return this.children;}
  set textContent(value){this.text=value;this.children=[];}
  append(...nodes){for(const n of nodes){if(n.parent)n.remove();n.parent=this;this.children.push(n);}}
  replaceChildren(...nodes){for(const n of this.children)n.parent=null;this.children=[];this.scrollTop=0;this.append(...nodes);}
  querySelector(selector){for(const n of this.children){if(n.className.split(' ').includes(selector.slice(1)))return n;const found=n.querySelector(selector);if(found)return found;}return null;}
  insertBefore(node,before){if(node.parent)node.remove();node.parent=this;const i=this.children.indexOf(before);this.children.splice(i<0?this.children.length:i,0,node);}
  remove(){if(this.parent){this.parent.children.splice(this.parent.children.indexOf(this),1);this.parent=null;}}
  setAttribute(){}
 }
 const previous=global.document;global.document={createElement:tag=>new Element(tag)};
 try{
  const host=new Element('div'),session={id:'reader-session',status:'running',steps:[{tool:'clean'},{tool:'captions'}],stage:'Working',job:{progress:12}};
  render(host,session);const grid=host.querySelector('.assistant-progress-cards'),first=grid.children[0];grid.scrollTop=210;grid.scrollLeft=4;
  session.job.progress=37;render(host,session);
  assert.equal(host.querySelector('.assistant-progress-cards'),grid);assert.equal(grid.children[0],first);
  assert.equal(grid.scrollTop,210);assert.equal(grid.scrollLeft,4);
  session.steps.push({tool:'sound'});render(host,session);assert.equal(grid.scrollTop,210);assert.equal(grid.children.length,3);
  render(host,{...session,id:'different-chat'});assert.notEqual(host.querySelector('.assistant-progress-cards'),grid);
 }finally{global.document=previous;}
});
test('saved stages, unknown inference and local buffering remain distinct',()=>{
 const session={status:'running',task_progress:{workflow:true,count:3,elapsed:30,drafts:[{role:'shorts',mode:'shorts',count:3,status:'working',current_stage:'copy:youtube:1',stages:{inspect:{},speech:{},selection:{},'render:1':{},'render:2':{},'render:3':{}},errors:{},stage_timings:{'copy:youtube:1':{started:100}},live:{stage:'copy:youtube:1',message:'Writing text'}}],jobs:[{role:'instagram',index:1,status:'ready',authorized:true}]}};
 const view=build(session,130),active=view.cards.find(c=>c.id==='shorts:copy:youtube:1');
 assert.equal(active.percent,null);assert.equal(active.eta,null);assert.equal(active.elapsed,30);
 const buffer=view.cards.find(c=>c.id==='instagram:delivery:1');assert.equal(buffer.state,'done');assert.match(buffer.text,/not posted/);
 assert.equal(view.finished+view.remaining,view.total);assert.ok(view.total>3);
});
test('speech estimates derive from actual completed batches only',()=>{
 const view=build({status:'running',task_progress:{workflow:false,count:1,drafts:[{role:'preparation',mode:'long',count:1,status:'working',current_stage:'speech',stages:{inspect:{}},errors:{},stage_timings:{speech:{started:100}},live:{stage:'speech',message:'Words and timing 6/10'}}],jobs:[]}},150);
 const speech=view.cards.find(c=>c.id==='preparation:speech');assert.equal(speech.percent,50);assert.equal(speech.eta,50);
});
test('failed stages do not become complete and unverified uploads are not scheduled',()=>{
 const view=build({status:'needs_review',task_progress:{workflow:true,count:1,drafts:[{role:'shorts',mode:'shorts',count:1,status:'failed',current_stage:'copy:youtube:1',stages:{},errors:{'copy:youtube:1':{error:'Needs review'}}}],jobs:[{role:'youtube',index:1,status:'processing',verified:false}]}});
 assert.equal(view.cards.find(c=>c.id==='shorts:copy:youtube:1').state,'failed');
 assert.notEqual(view.cards.find(c=>c.id==='youtube:delivery:1').state,'done');
});
test('ordinary editing requests show their real planned step count',()=>{
 const view=build({status:'running',step_index:1,steps:[{tool:'clean'},{tool:'captions'},{tool:'sound'}],job:{progress:42},stage:'Adding captions'});
 assert.equal(view.total,3);assert.equal(view.finished,1);assert.equal(view.cards[1].percent,42);
});

test('Instagram share receipts complete cards without YouTube timestamps',()=>{
 const view=build({status:'needs_review',task_progress:{workflow:true,count:3,drafts:[],jobs:[
  {role:'instagram',index:1,status:'published',verified:false,authorized:true},
  {role:'instagram',index:2,status:'processing',verified:false,authorized:true},
  {role:'instagram',index:3,status:'ready',verified:false,authorized:true}
 ]}});
 const published=view.cards.find(c=>c.id==='instagram:delivery:1');
 assert.equal(published.state,'done');assert.equal(published.percent,100);
 assert.equal(published.text,'100% · Published on Instagram');
 assert.equal(view.cards.find(c=>c.id==='instagram:delivery:2').state,'active');
 assert.equal(view.cards.find(c=>c.id==='instagram:delivery:3').text,'Queued locally · not posted');
});
