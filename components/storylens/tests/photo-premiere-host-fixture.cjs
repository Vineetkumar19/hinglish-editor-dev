const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');let next=1;
function File(path){this.fsName=path.replace(/\//g,'\\');this.exists=true}
function Bin(name){this.name=name;this.nodeId=next++;this.type=2;this.children=[];Object.defineProperty(this.children,'numItems',{get:()=>this.children.length});this.createBin=n=>{const b=new Bin(n);this.children.push(b);return b}}
const root=new Bin('root'),project={path:'D:\\owner.prproj',name:'owner',rootItem:root,importFiles(paths,a,bin){for(const p of paths){const item={nodeId:next++,name:'import',type:1,path:p.replace(/\//g,'\\'),getMediaPath(){return this.path},changeMediaPath(p){this.path=p.replace(/\//g,'\\');return 0}};bin.children.push(item)}return true}};
const c={app:{project},File};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),c);
let manifest={id:'abc',photos:[{id:1,path:'D:/preview.png',origin:'screenshot-preview'}]},r=c.storylensPhotoImportPremiere(manifest);assert.equal(r.status,'done',r.error);const id=r.imported[0].id;
manifest.folder_id=r.folder.id;manifest.photos=[{id:1,path:'D:/original.png',origin:'original'}];r=c.storylensPhotoImportPremiere(manifest);assert.equal(r.status,'done',r.error);assert.equal(r.upgraded[0].id,id);
r=c.storylensPhotoImportPremiere(manifest);assert.equal(r.already_present[0].id,id);assert.equal(root.children[0].children.length,1);assert.equal(root.children[0].children[0].children.length,1);console.log('Premiere mixed Windows paths and same-item upgrades pass');
delete manifest.folder_id;
r=c.storylensPhotoImportPremiere(manifest);assert.equal(r.status,'done',r.error);assert.equal(r.already_present[0].id,id,'A missing first receipt must still recover the existing photo item');assert.equal(root.children[0].children.length,1,'An uncertain retry must reuse the collection bin');
