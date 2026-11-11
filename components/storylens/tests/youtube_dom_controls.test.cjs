// Real content-controller tests using the control structure observed in Studio:
// zero-sized custom host, visible inner dialog, custom date trigger, footer buttons.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {fixture}=require('./fixtures/youtube_dom_fixture.cjs');
async function prepare(f){for(const action of ['inspect','open','opened','expand','date']){if(action==='opened')f.nativeOpen();const r=await f.call(action);assert.equal(r.ok,true,r.error)}f.closeCalendar();assert.equal((await f.call('time')).ok,true)}

test('pre-submission recovery selects the exact dropdown instead of repeating the private label',async()=>{
 const f=fixture({visibilityArrow:true,wireJob:{recover_before_submit:true}});
 const result=await f.call('open');assert.equal(result.ok,true,result.error);
 assert.equal(f.markedArrow(),'new00000001-visibility');
 assert.equal(f.markedPrivateLabel(),undefined);assert.equal(f.commits(),0);
});

test('a verified destination dashboard is valid before opening the content list',async()=>{
 const f=fixture({dashboard:true});assert.equal((await f.call('channel')).channel_id,'UC'+'g'.repeat(22));
 const reset=await f.call('reset');assert.equal(reset.ok,true,reset.error);assert.equal(f.commits(),0);
});

test('channel inspection identifies the current account before a mismatched target can change visibility',async()=>{
 const f=fixture({wireJob:{channel_id:'UC'+'x'.repeat(22)}});
 const identity=await f.call('channel');assert.equal(identity.channel_id,'UC'+'g'.repeat(22));
 assert.match((await f.call('open')).error,/different channel/);assert.equal(f.commits(),0);
});

test('the observed day-first Studio date format is filled and independently verified',async()=>{
 const f=fixture({dayFirst:true,preview:true});const results=await f.runWorker();
 assert.equal(results[0].controls_verified,true);assert.equal(f.commits(),0);
});
test('observed custom controls prepare exactly the reviewed date/time and cancel without saving',async()=>{
 const f=fixture();await prepare(f);const ready=await f.call('ready');assert.equal(ready.ok,true,ready.error);
 assert.equal(ready.driver_version,'0.4.7');assert.equal((await f.call('cancel')).ok,true);
 assert.equal(f.opened(),false);assert.equal(f.commits(),0);
});
test('date, time, and timezone mismatch independently block readiness and commit',async()=>{
 for(const option of ['wrongDate','wrongTime','wrongZone']){const f=fixture({[option]:true});await prepare(f);
  assert.equal((await f.call('ready')).ok,false);assert.equal((await f.call('commit')).ok,false);assert.equal(f.commits(),0)}
});
test('preview cannot commit even after all fields match',async()=>{
 const f=fixture({preview:true});await prepare(f);assert.equal((await f.call('ready')).ok,true);
 assert.match((await f.call('commit')).error,/preview cannot submit/);assert.equal(f.commits(),0);
});
test('normal confirmed controller commits once and clears its prepared evidence',async()=>{
 const f=fixture();await prepare(f);assert.equal((await f.call('ready')).ok,true);
 assert.equal((await f.call('commit')).ok,true);assert.equal((await f.call('commit')).ok,false);assert.equal(f.commits(),1);
});

test('schedule commit waits for the exact row to settle and never clicks twice on a stalled save',async()=>{
 const success=fixture();await prepare(success);await success.call('ready');
 const settled=await success.call('commit');assert.equal(settled.ui_commit_settled,true);assert.equal(success.opened(),false);
 const stalled=fixture({saveNeverSettles:true});await prepare(stalled);await stalled.call('ready');
 const result=await stalled.call('commit');assert.equal(result.ok,false);assert.match(result.error,/saved schedule/);
 assert.equal(stalled.commits(),1);assert.equal((await stalled.call('commit')).ok,false);assert.equal(stalled.commits(),1);
});

test('private-only cleanup saves the exact scheduled video without scheduling or publishing it',async()=>{
 const f=fixture({visibility:'Scheduled',privateCleanup:true,wireJob:{action:'youtube_private',publish_at:'',publish_now:false}});
 const result=await f.runWorker();assert.equal(result[0].status,'submitted');assert.equal(result[0].private_only,true);
 assert.equal(result[0].publish_at,'');assert.equal(f.commits(),1);assert.equal(f.opened(),false);
});

test('an already-private cleanup task submits readback evidence without pressing Save',async()=>{
 const f=fixture({privateCleanup:true,wireJob:{action:'youtube_private',publish_at:'',publish_now:false}});
 const result=await f.runWorker();assert.equal(result[0].private_only,true);assert.equal(f.commits(),0);
});

test('scheduled visibility marks the actual dropdown arrow instead of its tooltip label',async()=>{
 const f=fixture({visibility:'Scheduled',visibilityArrow:true,allowReschedule:true});
 assert.equal((await f.call('open')).ok,true);assert.equal(f.markedArrow(),'new00000001-visibility');
 assert.equal(f.opened(),false);assert.equal(f.commits(),0);
});

test('private visibility targets its stable label even when a hover arrow exists',async()=>{
 const f=fixture({visibility:'Private',visibilityArrow:true});
 assert.equal((await f.call('open')).ok,true);
 assert.equal(f.markedPrivateLabel(),'new00000001-visibility');
 assert.equal(f.markedArrow(),undefined);
 assert.equal(f.opened(),false);assert.equal(f.commits(),0);
});
test('real worker and content controller close the modal calendar before typing the time',async()=>{
 const f=fixture({preview:true,wrongDate:true});const finishes=await f.runWorker();
 assert.equal(finishes.length,1);assert.equal(finishes[0].status,'complete');assert.equal(finishes[0].controls_verified,true);
 assert.equal(f.commits(),0);assert.equal(f.opened(),false);
});

test('opening only returns the exact target and does not synthesize a visibility click',async()=>{
 const f=fixture();const result=await f.call('open');
 assert.equal(result.ok,true,result.error);assert.equal(result.control.selector,'[data-storylens-click="new00000001-visibility"]');
 assert.equal(f.opened(),false);assert.equal(f.commits(),0);
});

test('waits for asynchronously populated visibility without repeating an upload or clicking',async()=>{
 const f=fixture({visibilityDelay:8});const result=await f.call('open');
 assert.equal(result.ok,true,result.error);assert.equal(f.opened(),false);assert.equal(f.commits(),0);
});

test('a visibility timeout reports observed state without publishing or guessing the cause',async()=>{
 const f=fixture({visibilityDelay:100});const result=await f.call('open');
 assert.equal(result.ok,false);assert.match(result.error,/Observed control state/);
 assert.match(result.error,/"row_found":true/);assert.match(result.error,/"visibility_states":\[\]/);
 assert.equal(f.opened(),false);assert.equal(f.commits(),0);
});

test('scheduled rows require explicit replacement authority and public videos stay untouched',async()=>{
 for(const visibility of ['Scheduled','Public','Unlisted']){
  const f=fixture({visibility});const result=await f.call('open');assert.equal(result.ok,false);
  assert.equal(f.opened(),false);assert.equal(f.commits(),0);
 }
});

test('already-expanded scheduled dialog supports changed dates across months, years and leap days',async()=>{
 for(const publishAt of ['2031-01-01T19:30:00+05:30','2032-02-29T00:05:00+05:30',
  '2033-04-30T23:45:00+05:30','2034-12-31T13:30:00Z']){
  const f=fixture({visibility:'Scheduled',allowReschedule:true,preview:true,publishAt,wrongDate:true,wrongTime:true});
  const finishes=await f.runWorker();assert.equal(finishes[0].controls_verified,true);
  assert.equal(finishes[0].publish_at,publishAt);assert.equal(f.commits(),0);assert.equal(f.opened(),false);
 }
});

test('authorized schedule replacement submits the exact new date once through the full worker',async()=>{
 const f=fixture({visibility:'Scheduled',allowReschedule:true,publishAt:'2035-07-09T19:30:00+05:30',wrongDate:true,wrongTime:true});
 const results=await f.runWorker();assert.equal(results[0].status,'submitted');
 assert.equal(results[0].publish_at,'2035-07-09T19:30:00+05:30');assert.equal(f.commits(),1);
});
