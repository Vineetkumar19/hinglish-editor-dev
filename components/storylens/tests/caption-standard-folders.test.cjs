const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{test}=require('node:test');
const source=fs.readFileSync('editor_plugins/shared/aftereffects-panel.jsx','utf8');
test('Standard captions and artwork are grouped under Auto Captions / Standard / style',()=>{
 const folder={};const ctx={app:{project:{items:{},rootFolder:{name:'Root'}}},storylensCurrentComp:()=>({name:'Owner',duplicate:()=>({layers:{add:()=>{}},openInViewer(){}})}),storylensFolder:(name,parent)=>{const item={name,parentFolder:parent};folder[name]=item;return item;},storylensFootage:()=>({})};
 vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('function storylensAEWords'),source.indexOf('function storylensPanelImport')),ctx);
 ctx.storylensAEWords({name:'Serif Circle',words:[],decorations:'decoration.png'});assert.equal(folder.Standard.parentFolder.name,'Auto Captions');assert.equal(folder['Serif Circle'].parentFolder.name,'Standard');assert.equal(folder['Storylens caption artwork'].parentFolder.name,'Serif Circle');
});
