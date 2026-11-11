const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const html=fs.readFileSync('hinglish_app/static/publisher.html','utf8');
const workflow=fs.readFileSync('hinglish_app/static/workflow.html','utf8');
const css=fs.readFileSync('hinglish_app/static/workflow.css','utf8');
test('each channel exposes matching source, output, account and preparation slots',()=>{
 const cards=[...workflow.matchAll(/<section class="channel-workflow-card"[^>]*>([\s\S]*?)<\/section>/g)].map(x=>x[1]);
 assert.equal(cards.length,2);
 for(const [i,p] of ['cricket','gaming'].entries()){
  assert.match(cards[i],new RegExp('<h2[^>]*>'+p[0].toUpperCase()+p.slice(1)+'</h2>'));
  for(const label of ['Source','Output','Accounts'])assert.ok(cards[i].includes('>'+label+'<'));
  assert.match(cards[i],new RegExp('id="'+p+'Accounts"'));
  assert.match(cards[i],new RegExp('href="publisher.html\\?profile='+p+'"'));
 }
 assert.match(css,/grid-template-rows:\s*subgrid/);
 assert.match(css,/@media\s*\(max-width:700px\)/);
});
test('compact posting controls retain independent editable posting and approval choices',()=>{
 for(const id of ['enabled','audit'])assert.match(html,new RegExp('<label[^>]*>[^<]*<input[^>]*id="'+id+'"'));
 assert.doesNotMatch(html.match(/<input[^>]*id="enabled"[^>]*>/)[0],/\bdisabled\b/);
 assert.doesNotMatch(html.match(/<input[^>]*id="audit"[^>]*>/)[0],/\bchecked\b/);
 assert.match(html,/aria-label="Posting controls"/);
});

test('all prior publisher fields and failure surfaces remain reachable',()=>{
 for(const id of ['visibility','saveSettings','sourceRoot','readinessResult','tasks','publishingQueue','audience','synthetic','chooseVideo'])assert.equal([...html.matchAll(new RegExp('id="'+id+'"','g'))].length,1);
 assert.doesNotMatch(html,/<(?:fieldset|details)[^>]*id="(?:postingPermission|youtubeEligibility)"[^>]*\bhidden/);
});
test('phone bulk actions wrap onto usable rows instead of squeezing their words',()=>{
 const publisherCss=fs.readFileSync('hinglish_app/static/publisher.css','utf8');
 assert.match(publisherCss,/\.queue-toolbar button\{[^}]*min-width:132px/);
 assert.match(publisherCss,/\.queue-toolbar select\{[^}]*flex:1 1 calc\(100% - 48px\)/);
});
test('both publisher pages wrap header controls within narrow viewports',()=>{
 for(const name of ['publisher','workflow']){
  const styles=fs.readFileSync('hinglish_app/static/'+name+'.css','utf8');
  assert.match(styles,new RegExp('\\.'+(name==='publisher'?'publishing':'workflow')+'-page \\.topbar \\.header-actions\\{[^}]*flex-wrap:wrap'));
 }
});
