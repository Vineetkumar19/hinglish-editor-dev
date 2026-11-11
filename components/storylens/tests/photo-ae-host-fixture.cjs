const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let items=[],nextId=1,files={};const root={id:0,name:'Root'};
function FolderItem(name){this.id=nextId++;this.name=name;this.comment='';this.parentFolder=root;items.push(this)}
function FootageItem(file){this.id=nextId++;this.file=file;this.width=1200;this.height=675;this.parentFolder=root;items.push(this)}
function File(path){this.fsName=path;this.name=path.split('/').pop();this.exists=true;this.open=()=>true;this.close=()=>{};this.write=data=>files[path]=data}
const project={file:{fsName:'D:/owner.aep',name:'owner.aep'},rootFolder:root,items:{addFolder:name=>new FolderItem(name)},item:i=>items[i-1],importFile:options=>new FootageItem(options.file)};
Object.defineProperty(project,'numItems',{get:()=>items.length});
new FolderItem('Images');
const sandbox={app:{project,beginUndoGroup:()=>{},endUndoGroup:()=>{}},File,FolderItem,FootageItem,ImportOptions:function(file){this.file=file},alert:message=>{throw Error(message)}};
vm.createContext(sandbox);
const first=fs.readFileSync(process.argv[2],'utf8'),second=fs.readFileSync(process.argv[3],'utf8');
vm.runInContext(first,sandbox);vm.runInContext(first,sandbox);vm.runInContext(second,sandbox);
const images=items.find(x=>x instanceof FolderItem&&x.name==='Photo Collector');
const folders=items.filter(x=>x instanceof FolderItem&&x.parentFolder===images);
assert.deepEqual(folders.map(x=>x.name),['Screenshot 1','Screenshot 2']);
assert.equal(items.filter(x=>x instanceof FootageItem&&x.parentFolder===folders[0]).length,1);
assert.equal(items.filter(x=>x instanceof FootageItem&&x.parentFolder===folders[1]).length,1);
assert.equal(items.filter(x=>x instanceof FootageItem).length,2);
assert.ok(Object.values(files).every(text=>JSON.parse(text).status==='done'));
console.log('AE host folder numbering and per-screenshot retry checks passed');
