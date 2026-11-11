const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
function fixture(){
 const items=[],root={},ctx={};let next=0;
 class FolderItem{constructor(name){this.name=name;this.parentFolder=root;this.id=++next;items.push(this);}}
 class FootageItem{constructor(file){this.file=file;this.id=++next;items.push(this);}}
 class File{constructor(path){this.fsName=path;this.name=path.split('/').pop();this.exists=true;}}
 const project={rootFolder:root,get numItems(){return items.length},item:n=>items[n-1],items:{addFolder:name=>new FolderItem(name)},importFile:option=>new FootageItem(option.file)};
 Object.assign(ctx,{app:{project,beginUndoGroup(){},endUndoGroup(){}},File,FolderItem,FootageItem,ImportOptions:class{constructor(file){this.file=file;}},hJSON:JSON.stringify,storylensProjectId:()=> 'owner.aep'});
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('editor_plugins/shared/download-import.jsx','utf8'),ctx);
 const id='a'.repeat(32),manifest={id,host:'aftereffects',expected_project_id:'owner.aep',kind:'video',path:'D:/App/output/downloads/'+id+'/video/downloaded-video.mp4',name:'Owner video'};
 return {items,manifest,call:m=>JSON.parse(ctx.storylensPanelDownloadImport(m)),legacy(){const folder=new FolderItem('Video'),item=new FootageItem(new File(manifest.path));item.parentFolder=folder;return {folder,item};}};
}
test('video is delivered once to Video without a composition or layer edit',()=>{
 const f=fixture(),a=f.call(f.manifest),b=f.call(f.manifest);
 assert.equal(a.ok,true);assert.equal(a.folder,'Downloader Video');assert.equal(a.item_id,b.item_id);assert.equal(f.items.length,2);
});
test('extracted audio goes to Sound and a project switch stops delivery',()=>{
 const f=fixture(),m={...f.manifest,kind:'audio',path:f.manifest.path.replace('/video/downloaded-video.mp4','/audio/extracted-audio.wav')};
 assert.equal(f.call(m).folder,'Downloader Audio');
 assert.ok(f.call({...m,expected_project_id:'different.aep'}).error);assert.equal(f.items.length,2);
});
test('Premiere reuses the Video bin and item without creating a sequence',()=>{
 const all=[],root={children:{get numItems(){return all.length;}}};let serial=0;
 root.createBin=name=>{const entries=[],bin={name,type:2,nodeId:String(++serial),children:{get numItems(){return entries.length;}}};bin.entries=entries;all.push(bin);root.children[all.length-1]=bin;return bin;};
 const project={path:'owner.prproj',rootItem:root,importFiles(paths,suppress,bin){for(const path of paths){const item={type:1,nodeId:String(++serial),getMediaPath:()=>path};bin.entries.push(item);bin.children[bin.entries.length-1]=item;}return true;}};
 const c={app:{project},ProjectItemType:{BIN:2},File:class{constructor(path){this.fsName=path;this.name=path.split('/').pop();this.exists=true;}},storylensPanelJSON:JSON.stringify};
 vm.createContext(c);vm.runInContext(fs.readFileSync('editor_plugins/shared/download-import.jsx','utf8'),c);
 const id='b'.repeat(32),m={id,kind:'video',host:'premiere',expected_project_id:'owner.prproj',path:'D:/App/output/downloads/'+id+'/video/downloaded-video.mp4',name:'Owner clip'};
 const a=JSON.parse(c.storylensPanelDownloadImport(m)),b=JSON.parse(c.storylensPanelDownloadImport(m));
 assert.equal(a.ok,true);assert.equal(a.item_id,b.item_id);assert.equal(all.length,1);assert.equal(all[0].children.numItems,1);
});

test('old feature Video folder is renamed in place without duplicating its media',()=>{const f=fixture(),old=f.legacy(),result=f.call(f.manifest);assert.equal(result.ok,true);assert.equal(old.folder.name,'Downloader Video');assert.equal(result.item_id,old.item.id);assert.equal(f.items.length,2);});
