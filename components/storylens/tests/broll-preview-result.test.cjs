const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('manual B-roll result explains deferred preview without claiming a completed edit',()=>{
 const source=fs.readFileSync('hinglish_app/static/app.js','utf8');
 const start=source.indexOf('function showQuality('),end=source.indexOf('// ---- Eye contact',start);
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{classList:{toggle(){}},textContent:''});return nodes.get(id)};
 const context={$:get,window:{storylensEditors:{render(){}}},mode:'broll'};
 vm.createContext(context);vm.runInContext(source.slice(start,end),context);
 context.showQuality({broll_summary:{review_options:true,options:7,moments:10},broll_preview_notice:'Original audio over black. Use Save & rebuild for the combined preview.'});
 assert.equal(get('#resultTitle').textContent,'Choose your B-roll');
 assert.match(get('#qualityMeta').textContent,/Save & rebuild/);
 assert.doesNotMatch(get('#qualityMeta').textContent,/timeline is a suggestion/);
});
