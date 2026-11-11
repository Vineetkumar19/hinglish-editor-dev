const test=require('node:test'),assert=require('node:assert/strict');
const panel=require('../editor_plugins/shared/panel-model.js');
test('one shared script is sent to every semantic tool',()=>{
 for(const mode of ['script','captions','broll','visuals','zoom','sound']){
  const body=panel.request(mode,{script:'Exact words',content_format:'long'},{id:'context'},{});
  assert.equal(body.script,'Exact words');assert.equal(body.mode,mode);
 }
});
test('long form gives two choices; short form gives five',()=>{
 assert.equal(panel.choiceCount('long'),2);assert.equal(panel.choiceCount('short'),5);
});
test('host messages ignore unrelated windows and reject missing receipts',()=>{
 assert.equal(panel.accepts({source:'wrong'},'expected'),false);
 assert.equal(panel.accepts({source:'expected'},'expected'),true);
});
test('supported tools exclude Resolve and preserve both sound actions',()=>{
 assert.equal(panel.hosts.includes('resolve'),false);assert.equal(panel.tools.length,11);
 assert.deepEqual(panel.soundActions,['recommend','auto']);
});
