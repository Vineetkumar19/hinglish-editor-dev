const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const html=fs.readFileSync('hinglish_app/static/publisher.html','utf8'),js=fs.readFileSync('hinglish_app/static/publisher.js','utf8');
test('publisher exposes profile, exact path, source type and safe pre-demo diagnostics',()=>{for(const id of ['publisherProfile','sourceMode','publishKind','publishDestinations','checkReadiness','readinessResult'])assert.match(html,new RegExp('id="'+id+'"'));assert.match(html,/Full video path/);assert.match(html,/publisher-intake.js/)});
test('compact screen keeps preference editor and existing authorization review',()=>{for(const id of ['creatorMemory','memoryList','authorize','audience','synthetic','queue'])assert.match(html,new RegExp('id="'+id+'"'));assert.match(html,/<details[^>]+id="creatorMemory"/)});
test('publisher uses backend draft intake and separate live browser read',()=>{assert.match(js,/StorylensPublisherIntake.intake/);assert.match(js,/api\/local-browser/);assert.match(js,/operation:'diagnostics'/);assert.match(js,/publisherProfile/)});
test('compact workbench keeps queue filter and collapsible connection controls',()=>{
 for(const id of ['queueView','connectionSettings'])assert.match(html,new RegExp('id="'+id+'"'));
 assert.match(html,/<details[^>]+id="connectionSettings"/);assert.doesNotMatch(html,/<details[^>]+id="connectionSettings"[^>]*\bopen/);
 assert.doesNotMatch(html,/Check before demo|id="sourceScript"|Script &amp; notes/);
});

test('channel workflow documents varying daily slots and finished-highlights lineage',()=>{
 const workflow=fs.readFileSync('hinglish_app/static/workflow.html','utf8');
 assert.match(workflow,/5–9 p\.m\. IST/);assert.match(workflow,/Shorts from that finished edit/);
 assert.match(workflow,/<script src="icons\.js[^\"]*"><\/script>/);
 assert.doesNotMatch(workflow,/Daily at <strong>7 p\.m\.|Reuse the seven saved/);
 for(const id of ['cricketAccounts','gamingAccounts','workflowSaved','workflowBatches','workflowChrome','workflowQueue','workflowFailures'])assert.match(workflow,new RegExp('id="'+id+'"'));
});
