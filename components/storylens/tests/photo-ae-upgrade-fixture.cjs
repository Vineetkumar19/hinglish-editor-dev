const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let items=[],next=1,receipts={};const root={id:0};
function FolderItem(name){this.id=next++;this.name=name;this.comment='';this.parentFolder=root;items.push(this)}
function FootageItem(file){this.id=next++;this.file=file;this.name=file.name;this.comment='';this.parentFolder=root;this.width=300;this.height=200;this.replace=function(file){this.file=file;this.width=1200;this.height=800};items.push(this)}
function File(path){this.fsName=path;this.name=path.split('/').pop();this.exists=true;this.open=()=>true;this.close=()=>{};this.write=s=>receipts[path]=s}
const project={file:{fsName:'D:/owner.aep',name:'owner.aep'},rootFolder:root,items:{addFolder:n=>new FolderItem(n)},item:i=>items[i-1],importFile:o=>new FootageItem(o.file)};Object.defineProperty(project,'numItems',{get:()=>items.length});
const context={app:{project,beginUndoGroup(){},endUndoGroup(){}},FolderItem,FootageItem,File,ImportOptions:function(file){this.file=file},alert:s=>{throw Error(s)}};vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);const id=items.find(x=>x instanceof FootageItem).id;
vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),context);vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),context);
const footage=items.filter(x=>x instanceof FootageItem);assert.equal(footage.length,1);assert.equal(footage[0].id,id);assert.equal(footage[0].file.fsName,'D:/original.png');assert.equal(footage[0].width,1200);
assert.equal(items.filter(x=>x instanceof FolderItem&&x.name==='Screenshot 1').length,1);
assert.ok(Object.values(receipts).every(s=>JSON.parse(s).status==='done'));
console.log('Preview upgrade preserved native item ID and one numbered folder');
