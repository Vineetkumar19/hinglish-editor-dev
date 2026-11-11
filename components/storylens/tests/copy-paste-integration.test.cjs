const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
test('Copy Paste is embedded in the single Storylens panel with ordered native dependencies',()=>{
 const host=fs.readFileSync('editor_plugins/after-effects-cep/jsx/host.jsx','utf8');
 assert.ok(host.includes('#include "copy-paste-model.js"'));assert.ok(host.indexOf('#include "copy-paste-model.js"')<host.indexOf('#include "copy-paste.jsx"'));
 const html=fs.readFileSync('hinglish_app/static/editor-panel.html','utf8');assert.match(html,/id="copyPasteSection"[^>]*hidden/);assert.match(html,/copy-paste\.js\?v=/);
 const js=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8');assert.match(js,/storylensCopyPaste/);assert.match(js,/dataset\.mode='copyPaste'/);
});
test('all native Copy Paste errors have ordinary-language shared catalog messages',()=>{
 const catalog=JSON.parse(fs.readFileSync('hinglish_app/error_catalog.json','utf8'));
 for(const code of ['media','target','template','stale','full','host','native']){const rule=catalog.find(r=>r.code==='copy_paste_'+code);assert.ok(rule,code);assert.match(rule.message,/Select|Open|Choose|Read|After Effects|Inspect|Copy/i);assert.doesNotMatch(rule.message,/Traceback|TypeError/);}
});
