const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('hinglish_app/static/publisher.html','utf8');
const js=fs.readFileSync('hinglish_app/static/publisher.js','utf8');
test('both posting checkboxes remain editable',()=>{
 for(const id of ['enabled','audit']){
  const input=html.match(new RegExp('<input[^>]*id="'+id+'"[^>]*>'))?.[0];
  assert.ok(input);assert.doesNotMatch(input,/\bdisabled\b|\breadonly\b/);
 }
});
test('checkbox choices are saved independently including unchecked values',()=>{
 const code=js.slice(js.indexOf('function settings()'),js.indexOf('async function refresh('));
 for(const enabled of [true,false])for(const approval of [true,false]){
  const fields={mediaRoot:{value:'media'},sourceRoot:{value:'source'},shortCount:{value:'7'},visibility:{value:'private'},enabled:{checked:enabled},audit:{checked:approval}};
  const context={state:{settings:{daily_time:'19:00',vision:true,s3_bucket:'saved',s3_region:'saved'}},$:s=>fields[s.slice(1)]};
  vm.createContext(context);vm.runInContext(code+';this.saved=settings()',context);
  assert.equal(context.saved.enabled,enabled);assert.equal(context.saved.youtube_public_api_ready,approval);
 }
});
test('preparation history is initially collapsed without removing task actions',()=>{
 const history=html.match(/<details\b([^>]*\bid="preparationHistory"[^>]*)>([\s\S]*?)<\/details>/);
 assert.ok(history,'History disclosure missing');assert.doesNotMatch(history[1],/\bopen\b/);
 assert.match(history[2],/<summary[^>]*>[\s\S]*Preparation history[\s\S]*<\/summary>/);
 assert.match(history[2],/<div id="tasks"/);
 assert.match(js,/Resume preparation/);assert.match(js,/Technical details/);
 assert.doesNotMatch(js,/preparationHistory[^;]*\.open\s*=/);
});
