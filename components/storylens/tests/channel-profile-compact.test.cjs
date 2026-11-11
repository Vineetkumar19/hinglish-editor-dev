const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const js=fs.readFileSync('hinglish_app/static/niche.js','utf8').replace(/\r\n/g,'\n'),css=fs.readFileSync('hinglish_app/static/niche.css','utf8');
function actions(profile){
 const start=js.indexOf('function actionsFor(profile)');assert.ok(start>=0,'Profile actions helper missing');
 const end=js.indexOf('\n  function draw()',start);const context={};vm.createContext(context);
 vm.runInContext(js.slice(start,end)+';this.actions=actionsFor',context);return context.actions(profile);
}
test('Gaming has exactly three compact actions with correct highlight-then-five-shorts intent',()=>{
 const options=actions('gaming');assert.equal(options.length,3);
 assert.deepEqual(Array.from(options,x=>x.label),['15-minute highlights','Create thumbnail','Highlights + 5 Shorts']);
 assert.ok(options.every(x=>!x.href));
 assert.match(options[2].prompt,/one 15-minute gaming highlights video/i);
 assert.match(options[2].prompt,/then extract exactly 5 Shorts from that finished highlights video/i);
});
test('Cricket offers thumbnail, profile-scoped publishing and five shorts from finished export',()=>{
 const options=actions('cricket');assert.deepEqual(Array.from(options,x=>x.label),['Create thumbnail','Post video','Video + 5 Shorts']);
 assert.equal(options[1].href,'publisher.html?profile=cricket');
 assert.match(options[2].prompt,/finished Cricket video/i);assert.match(options[2].prompt,/exactly 5 Shorts/i);
 assert.doesNotMatch(options[2].prompt,/stream|highlight/i);
 assert.equal(actions('general').length,0);assert.equal(actions('invalid').length,0);
});
test('removed explanatory/style UI stays absent while preferences stay editable',()=>{
 for(const value of ['channelSummary','documentarySettings','drawDocumentary','documentaryExplorer','Find a reference','These notes guide future requests','This applies to new requests','Your existing editor'])assert.ok(!js.includes(value),value);
 for(const value of ['channelPreferences','channelFeedback','channelReferences','channelSave'])assert.ok(js.includes('id="'+value+'"'));
 assert.match(js,/feedback:q\('#channelFeedback'\)\.value/);
 assert.doesNotMatch(js,/changes\.documentary_style\s*=/);
});
test('fourth screenshot research fields and copy stay byte-for-byte unchanged',()=>{
 const start=js.indexOf('<div id="cricketResearch"'),end=js.indexOf('\n  <button type="button" id="channelSave"');
 assert.equal(js.slice(start,end),fs.readFileSync('tests/fixtures/niche-cricket-research.html','utf8'));
});
test('reference links and action buttons use adjacent wrapping rows',()=>{
 assert.match(css,/#channelReferences\{[^}]*display:flex[^}]*flex-wrap:wrap/);
 assert.match(css,/#channelReferences a\{[^}]*display:inline-flex/);
 assert.match(css,/\.channel-actions button\{[^}]*flex:1 1 0[^}]*min-width:0/);
});
test('shortcuts close the modal and prepare a request without submitting it',()=>{
 assert.match(js,/button\.onclick=\(\)=>\{dialog\.close\(\);if\(action\.href\)location\.href=action\.href;else prompt\(action\.prompt\)/);
 assert.doesNotMatch(js,/requestSubmit|assistantSend|\.submit\(/);
});
test('shortcut opens the editor rather than the separate Chats/history toggle',()=>{
 const start=js.indexOf('function prompt(text)'),end=js.indexOf('\n  window.creatorProfile=',start);
 const box={value:'',focus(){}},clicked=[];
 const context={document:{body:{classList:{contains:()=>false}},querySelector:s=>{
  if(s==='#assistantPrompt')return box;
  return {getAttribute:()=> 'false',click:()=>clicked.push(s)};
 }},status:()=>{},location:{}};
 vm.createContext(context);vm.runInContext(js.slice(start,end)+';prompt("Prepared request")',context);
 assert.deepEqual(clicked,['.assistant-toggle:not(.chat-history-toggle)']);assert.equal(box.value,'Prepared request');
});
