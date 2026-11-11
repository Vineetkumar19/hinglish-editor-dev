const test=require('node:test'),assert=require('node:assert/strict');
const {plan,measure,activity}=require('../hinglish_app/static/prepare-post-progress.js');

test('a metadata-only weekly refresh remains incomplete until its model result is saved',()=>{
 const d={mode:'long',count:1,status:'working',current_stage:'weekly:youtube:1',stages:{inspect:{},speech:{},'copy:youtube:1':{}}};
 assert.ok(plan(d,'long').includes('weekly:youtube:1'));
 const value=measure('weekly:youtube:1',d,{stage:'weekly:youtube:1',message:'V8 is preparing 4 weekly SEO packages'});
 assert.equal(value.percent,null);assert.match(value.text,/V8 is preparing 4 weekly/);
});
test('each format lists its own upcoming grey stages and all platform copies',()=>{
 assert.deepEqual(plan(null,'long'),['inspect','speech','copy:youtube:1']);
 assert.deepEqual(plan(null,'highlights'),['inspect','speech','highlight-signals','highlight-selection','highlights','copy:youtube:1']);
 const steps=plan(null,'shorts',5);assert.equal(steps.filter(k=>k.startsWith('render:')).length,5);assert.equal(steps.filter(k=>k.startsWith('copy:')).length,10);
 assert.equal(measure('speech',null).state,'pending');
});
test('ASR reports completed batches, not the batch just started',()=>{
 const draft={status:'working',current_stage:'speech',stages:{inspect:{}}};
 const result=measure('speech',draft,{stage:'speech',message:'Words and timing 21/649 (285.3s)'});
 assert.equal(result.percent,3);assert.match(result.text,/20\/649 batches · 629 left/);
 assert.equal(measure('inspect',draft).percent,100);assert.equal(measure('inspect',draft).state,'done');
});
test('unknown progress and unrelated messages never fabricate a percentage',()=>{
 const d={status:'working',current_stage:'highlight-selection',stages:{}};
 assert.equal(measure('highlight-selection',d,{stage:'speech',message:'Words and timing 200/649'}).percent,null);
 assert.equal(measure('highlight-selection',d,{stage:'highlight-selection',message:'Model is thinking'}).percent,null);
 assert.equal(measure('copy:youtube:1',d).state,'pending');
});
test('gaming selection displays the actual current section, completed percentage and remaining count',()=>{
 const d={status:'working',current_stage:'highlight-selection',stages:{}};
 const p=measure('highlight-selection',d,{stage:'highlight-selection',message:'Finding gaming moments in section 7/31'});
 assert.equal(p.percent,19);assert.equal(p.text,'19% · Section 7/31 · 25 left');
 const last=measure('highlight-selection',d,{stage:'highlight-selection',message:'Finding gaming moments in section 31/31'});
 assert.equal(last.percent,96);assert.equal(last.state,'active');
});
test('last segment stays incomplete until its checkpoint is saved; failures stay visible',()=>{
 const d={status:'working',current_stage:'highlights',stages:{}};
 assert.equal(measure('highlights',d,{stage:'highlights',message:'Rendering saved interval 5/5'}).percent,80);
 d.status='failed';d.errors={highlights:{error:'Stopped'}};assert.equal(measure('highlights',d).state,'failed');
 d.stages.highlights={};assert.equal(measure('highlights',d).state,'done');
});
test('reported total never makes an unsaved stage green',()=>{
 const d={status:'working',current_stage:'speech',stages:{}};
 const result=measure('speech',d,{stage:'speech',message:'Alternate CUDA speech: 600/600s'});
 assert.equal(result.percent,99);assert.equal(result.state,'active');
});
test('all stages without fractions explain the current operation rather than a missing percentage',()=>{
 for(const key of ['inspect','speech','selection','highlight-signals','highlight-selection','highlights','render:2','copy:youtube:2','copy:instagram:2','context:1']){
  const result=measure(key,{status:'working',current_stage:key,stages:{}},{stage:key,message:'GPU slot reserved'});
  assert.equal(result.percent,null);assert.ok(result.text.length>5);assert.doesNotMatch(result.text,/unavailable/i);
  assert.match(result.text,/0\/1 complete/);
 }
 assert.equal(activity('speech','Waiting for the shared GPU slot'),'Waiting for the GPU');
 assert.equal(activity('copy:instagram:1'),'Writing caption and hashtags');
 const d={status:'working',current_stage:'selection',stages:{}};
 assert.equal(measure('selection',d,{stage:'selection',message:'Finding hook moments in part 3/8 (1:30-4:30)'}).percent,25);
 assert.equal(measure('selection',d,{stage:'selection',message:'Looking for 2 more complete, unused moment(s) (3/5 selected)'}).percent,60);
});
