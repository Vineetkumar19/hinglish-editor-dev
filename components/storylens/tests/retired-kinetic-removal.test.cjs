const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
test('retired kinetic experiment is disconnected while other editor features remain',()=>{
 const js=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8');
 const html=fs.readFileSync('hinglish_app/static/editor-panel.html','utf8');
 const bridge=fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8');
 const http=fs.readFileSync('hinglish_app/editor_panel_http.py','utf8');
 for(const content of [js,html,bridge,http])assert(!/kineticTypography|kineticView|kineticSection|kinetic_typography|kinetic-typography/.test(content));
 for(const feature of ['templateText','copyPaste','templateImport','imageDownload','cinematicText'])assert(bridge.includes(feature));
 for(const id of ['templateTextSection','templateImportSection','copyPasteSection','effectsSection'])assert(html.includes(id));
 assert(fs.existsSync('hinglish_captions/kinetic_gold_reference.json'));
});
