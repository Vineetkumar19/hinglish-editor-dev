const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
test('template tool tiles only navigate; selecting or double-clicking cannot run a native edit',()=>{
 const source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8');
 const start=source.indexOf("for(const tool of ['templateAligner','templateImport'])"),end=source.indexOf('const copy=',start);
 assert.ok(start>=0&&end>start);const tiles=[],selected=[],nativeCalls=[];
 vm.runInNewContext(source.slice(start,end),{document:{createElement:()=>({})},$:()=>({append:tile=>tiles.push(tile)}),labels:{templateAligner:'Template Aliner',templateImport:'Import Template'},isEditingBusy:()=>false,select:mode=>selected.push(mode),native:(...args)=>nativeCalls.push(args),templateImportView:{start:()=>nativeCalls.push('start')}});
 for(const tile of tiles){tile.onclick();tile.onclick();}
 assert.equal(tiles.length,2);assert.equal(selected.length,4);assert.equal(nativeCalls.length,0);
 const html=fs.readFileSync('hinglish_app/static/editor-panel.html','utf8');
 assert.match(html,/id="templateAliner"[^>]*>Run Template Aliner/);assert.match(html,/id="templateImport"[^>]*>Run Import Template/);
});
