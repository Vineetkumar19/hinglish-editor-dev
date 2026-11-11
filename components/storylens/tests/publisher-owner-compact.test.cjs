const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('hinglish_app/static/publisher.html','utf8'),js=fs.readFileSync('hinglish_app/static/publisher.js','utf8');
test('handle labels use the current exact channel identity and never another profile mapping',()=>{
 const {accountLabel}=require('../hinglish_app/static/publisher-intake.js');
 assert.equal(accountLabel({connected:true,id:'gaming',name:'Gaming'},{gaming:'@savedgaming',cricket:'@other'}),'@savedgaming');
 assert.equal(accountLabel({connected:true,id:'new-channel',name:'New channel'},{gaming:'@savedgaming'}),'New channel');
 assert.equal(accountLabel({connected:false,id:'gaming'},{gaming:'@savedgaming'}),'Not connected');
});
test('removed prose and unused script/API/setup controls stay absent',()=>{
 for(const id of ['sourceScript','notes','vision','refreshCopy','igId','igToken','bucket','region','googleClient','dailyWindow'])assert.doesNotMatch(html,new RegExp('id="'+id+'"'));
 for(const text of ['Selecting a file imports','Script &amp; notes','Optional Instagram API','First-time setup','Confirm only after Google approval','Runs only posts you explicitly authorize','A varying time is chosen'])assert.ok(!html.includes(text),text);
 assert.match(html,/Instagram needs this computer awake/);
});
test('connection row has direct YouTube/Instagram controls and exactly two visibility choices',()=>{
 assert.match(html,/class="publisher-connections-row"/);
 assert.match(html,/<button[^>]*id="connectYouTube"[^>]*>Connect YouTube<\/button>/);
 assert.match(html,/<button[^>]*id="connectInstagram"[^>]*>Connect Instagram<\/button>/);
 const select=html.match(/<select id="visibility">([\s\S]*?)<\/select>/)[1];
 assert.equal([...select.matchAll(/<option/g)].length,2);assert.match(select,/value="public">Public/);assert.match(select,/value="private"[^>]*>Schedule\s*\/\s*private/i);
 assert.match(js,/window\.open\('\/chrome\.html'/);
});
test('removed fields do not break settings or change saved legacy guidance/hosting values',()=>{
 const code=js.slice(js.indexOf('function settings()'),js.indexOf('async function refresh('));
 const data={mediaRoot:{value:'media'},sourceRoot:{value:'source'},shortCount:{value:'7'},visibility:{value:'private'},enabled:{checked:true},audit:{checked:false}};
 const context={state:{settings:{daily_time:'19:00',vision:true,s3_bucket:'preserved',s3_region:'preserved-region'}},$:s=>{const e=data[s.slice(1)];assert.ok(e,'Unexpected DOM dependency '+s);return e;}};
 vm.createContext(context);vm.runInContext(code+';this.result=settings()',context);
 assert.equal(context.result.vision,true);assert.equal(context.result.s3_bucket,'preserved');assert.equal(context.result.enabled,true);assert.equal(context.result.youtube_public_api_ready,false);
});
test('saved folders share a row and permission controls remain individually labelled',()=>{
 assert.match(html,/class="publish-row publisher-folder-row"/);for(const id of ['mediaRoot','sourceRoot','enabled','audit'])assert.match(html,new RegExp('id="'+id+'"'));
 assert.doesNotMatch(js,/saved connection|browser online|browser offline/);
});
