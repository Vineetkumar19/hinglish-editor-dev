const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('Adobe CEP exposes the browser model even when Node module is also present',()=>{
 const c={window:{},module:{exports:{}}};vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/shared/panel-model.js','utf8'),c);
 assert.equal(c.window.storylensPanel.tools.length,11);assert.equal(c.window.storylensPanel.choiceCount('short'),5);assert.equal(c.module.exports.tools.length,11);
});
test('Photo Collector remains available in the Adobe mixed context',()=>{
 const c={module:{exports:{}}};c.window=c;vm.createContext(c);vm.runInContext(fs.readFileSync('hinglish_app/static/photos-model.js','utf8'),c);
 assert.equal(c.PhotoCollector.startPayload('screen','MI').min_edge,0);assert.equal(typeof c.module.exports.canImport,'function');
});
test('successful native photo retry clears the earlier failure message',async()=>{
 const source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8');
 const fn=source.slice(source.indexOf('async function importPhotos(id){'),source.indexOf('async function importManifest('));
 const nodes={sharedScript:{value:''},contentFormat:{value:'short'},receipt:{textContent:''}},state={error:'Earlier photo file was locked'};
 const c={host:'premiere',mode:'clean',photoWatch:null,$:id=>nodes[id],clearError:()=>state.error='',native:async action=>action==='projectContext'?{}:{status:'done',original_count:1,preview_count:0,folder:{name:'Screenshot 1'}},api:async path=>path==='/api/panel/context'?{id:'ctx'}:path==='/api/panel/photos'?{photos:[{id:1,path:'photo.png',origin:'original'}]}:path.startsWith('/api/photos/job')?{status:'done'}:{}};
 vm.createContext(c);vm.runInContext(fn,c);await c.importPhotos('existing');assert.equal(state.error,'');assert.match(nodes.receipt.textContent,/1 originals/);
});
