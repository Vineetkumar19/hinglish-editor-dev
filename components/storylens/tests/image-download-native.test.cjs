const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
function harness(){
 let next=0,imports=0;const items=[],root={id:0};
 class FolderItem{constructor(name){this.name=name;this.id=++next;this.parentFolder=root;items.push(this);}}
 class FootageItem{constructor(file){this.file=file;this.id=++next;this.parentFolder=root;items.push(this);}}
 class File{constructor(path){this.fsName=path;this.name=path.split('/').pop();this.exists=true;}}
 const project={rootFolder:root,get numItems(){return items.length},item:n=>items[n-1],get selection(){return items.filter(item=>item.selected)},items:{addFolder:name=>new FolderItem(name)},importFile:options=>{imports++;return new FootageItem(options.file);}};
 const c={app:{project,beginUndoGroup(){},endUndoGroup(){}},File,FolderItem,FootageItem,ImportOptions:class{constructor(file){this.file=file;}},storylensProjectId:()=> 'owner.aep',hJSON:JSON.stringify};
 vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/shared/image-download-import.jsx','utf8'),c);
 const manifest={id:'a'.repeat(24),expected_project_id:'owner.aep',path:'D:/Full Drive/remove silence/output/image-downloads/Downloads/Image-'+ 'a'.repeat(16)+'.jpg'};
 return {items,manifest,call:m=>JSON.parse(c.storylensPanelImageDownload(m||manifest)),imports:()=>imports,owner:()=>{const item=new FolderItem('Owner folder');item.selected=true;return item;}};
}
test('exact image goes into root Image Downloader once without sweeping project selections',()=>{
 const h=harness(),owner=h.owner(),first=h.call(),second=h.call();
 assert.equal(first.ok,true);assert.equal(second.footage_id,first.footage_id);assert.equal(h.imports(),1);
 const photo=h.items.find(i=>i.id===first.footage_id);assert.equal(photo.parentFolder.name,'Image Downloader');assert.equal(photo.selected,false);assert.equal(owner.selected,true);
});
test('project change is rejected before creating a folder or importing',()=>{
 const h=harness(),result=h.call({...h.manifest,expected_project_id:'another.aep'});
 assert.equal(result.ok,undefined);assert.equal(h.items.length,0);assert.equal(h.imports(),0);
});
