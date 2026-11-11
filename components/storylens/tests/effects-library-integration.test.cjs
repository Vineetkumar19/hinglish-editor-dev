const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
test('Effects is a separate third tab and mounts its own module with the real native bridge',()=>{
 const html=fs.readFileSync('hinglish_app/static/editor-panel.html','utf8'),js=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8'),shell=fs.readFileSync('editor_plugins/shared/cep-shell.js','utf8');
 assert(html.includes('id="effectsLibraryHome"'));assert(html.indexOf('id="effectsHome"')<html.indexOf('id="effectsLibraryHome"'));assert(html.includes('effects-library.js'));assert(js.includes('storylensEffectsLibrary'));assert(js.includes("native('effectsLibrary'" )||js.includes('storylensEffectsLibrary?.({native,'));assert(shell.includes("message.action==='effectsLibrary'"));assert(shell.includes('storylensPanelEffects'));assert(JSON.parse(fs.readFileSync('hinglish_app/error_catalog.json')).some(r=>r.code==='effects_library'));
});
