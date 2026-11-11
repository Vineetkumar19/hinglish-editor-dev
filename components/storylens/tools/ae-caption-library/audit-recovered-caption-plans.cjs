/* Inspect actual worker output through the production native bridge. No AE calls. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),bridge=require('../../editor_plugins/caption-patterns/bridge.cjs'),model=require('../../editor_plugins/caption-patterns/model.cjs');
const receipts=[];
for(const id of process.argv.slice(2)){
 assert.match(id,/^[a-f0-9]{32}$/);
 const folder=path.join(root,'output/captions/ae-speech',id),request=JSON.parse(fs.readFileSync(path.join(folder,'request.json'),'utf8')),saved=bridge.savedWords(root,folder),plan=model.prepare({...saved,script:saved.caption_script});
 assert.equal(saved.reference_script,request.script);
 const words=plan.pages.flatMap(p=>p.words);
 assert.equal(words.length,saved.words.length);
 assert.equal(words.map(w=>w.source).join(' '),saved.caption_script);
 for(const p of plan.pages){assert(p.end>p.start);assert(p.words.every(w=>w.start>=p.start&&w.start<p.end));}
 const jsx=bridge.nativeRequest(root,{action:'patternInsert',request_id:id,context:request.context,result_folder:folder,script:request.script},{persist:false});
 assert(jsx.includes('StorylensCaptionPatterns.insert('));
 receipts.push({id,words:words.length,precomp_groups:plan.pages.length,exact_words:true,positive_group_durations:true,bridge_generated:true,ae_run:false});
}
fs.writeFileSync(path.join(root,'output/caption-recording-recovery-20261029/plan-checks.json'),JSON.stringify(receipts,null,2));
console.log(JSON.stringify(receipts));
