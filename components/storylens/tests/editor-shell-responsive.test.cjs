const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
test('saved pane widths leave space for the editor at desktop sizes',()=>{
 const {paneWidths}=require('../hinglish_app/static/editor-shell.js');
 for(const viewport of [1180,1280,1536,1920]){
  const w=paneWidths(viewport,900,640,true,true);
  assert.ok(w.chat>=320); assert.ok(w.history>=240);
  assert.ok(viewport-w.chat-w.history-96>=360,JSON.stringify({viewport,...w}));
 }
});
test('narrow and invalid stored sizes remain bounded',()=>{
 const {paneWidths}=require('../hinglish_app/static/editor-shell.js');
 for(const viewport of [320,390,562,768,900,1024]){
  const w=paneWidths(viewport,NaN,Infinity,true,true);
  assert.ok(Number.isFinite(w.chat)&&Number.isFinite(w.history));
  assert.ok(w.chat<=viewport);assert.ok(w.history<=viewport);
 }
});
test('shared UI labels have no mojibake sequences',()=>{
 for(const file of ['assistant.js','editor-panel.js','editor-panel.html']){
  const source=fs.readFileSync(require('node:path').join(__dirname,'../hinglish_app/static',file),'utf8');
  assert.doesNotMatch(source,/[\u00e2\u00c3\u00c2\u00ef][\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2010-\u203a\u20ac\u2122]/,file);
 }
});
