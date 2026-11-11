'use strict';
const fail=message=>Object.assign(Error(message),{userFacing:true});
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const DEFAULT_ROOT='D:/Editing/Cinematics AE templates/Effects templates';
const project=/\.(aep|aepx|aet)$/i,media=/\.(png|jpe?g|tiff?|psd|ai|eps|exr|dpx|tga|bmp|gif|webp|mp4|mov|avi|mxf|m4v|webm|wav|mp3|aiff?|aac|m4a)$/i;
const ignored=/^(?:__MACOSX|Adobe After Effects Auto-Save|Auto-Save|backups?|\.git)$/i;
const hash=s=>crypto.createHash('sha256').update(s).digest('hex').slice(0,24);
function createCatalog(root=DEFAULT_ROOT){
 function walk(dir,depth=0,out=[]){
  if(depth>16||out.length>20000)throw fail('This Effects folder is too large to read safely. Split it into smaller template packs.');
  for(const e of fs.readdirSync(dir,{withFileTypes:true})){if(e.name.startsWith('.')||ignored.test(e.name))continue;const p=path.join(dir,e.name);if(e.isSymbolicLink()||fs.lstatSync(p).isSymbolicLink())continue;if(e.isDirectory())walk(p,depth+1,out);else if(e.isFile())out.push(p);}return out;
 }
 function inside(file){const real=fs.realpathSync(file),rel=path.relative(fs.realpathSync(root),real);if(!rel||rel==='..'||rel.startsWith('..'+path.sep)||path.isAbsolute(rel))throw fail('Refresh Effects and choose a local template pack.');return real;}
 function inventory(){
  if(!fs.existsSync(root)||fs.lstatSync(root).isSymbolicLink())throw fail('The Effects templates folder is unavailable. Connect drive A and refresh Effects.');
  const files=walk(root),groups=new Map(),archives=[];
  for(const f of files){const parts=path.relative(root,f).split(path.sep);if(parts.length===1&&/\.zip$/i.test(f))archives.push(path.basename(f));if(!project.test(f))continue;const name=parts.length>1?parts[0]:path.basename(f,path.extname(f));if(!groups.has(name))groups.set(name,[]);groups.get(name).push(f);}
  const packs=[];for(const [name,projects] of groups){
   projects.sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));const first=projects[0],packRoot=path.relative(root,first).split(path.sep).length>1?path.join(root,name):root;
   const entries=projects.map(f=>{const p=inside(f),s=fs.statSync(p);return {key:hash(path.relative(root,p).toLowerCase()),name:path.relative(packRoot,p),path:p,size:s.size,modified:s.mtimeMs};});
   const assets=files.filter(f=>media.test(f)&&(packRoot===root?path.dirname(f)===root:f.startsWith(packRoot+path.sep)));
   // Include asset metadata: restored/changed dependencies invalidate old cards too.
   const signature=hash(entries.map(p=>[p.key,p.size,p.modified].join('|')).concat(assets.map(f=>{const s=fs.statSync(f);return [path.relative(root,f),s.size,s.mtimeMs].join('|');})).join('\n'));
   packs.push({id:hash(name.toLowerCase()),name,signature,projects:entries,media:assets.map(inside)});
  }
  packs.sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true}));return {packs,archives:archives.filter(a=>!groups.has(a.replace(/\.zip$/i,'')))};
 }
 function list(){const r=inventory();return {ok:true,root,packs:r.packs.map(p=>({id:p.id,name:p.name,signature:p.signature,projects:p.projects.map(({key,name})=>({key,name}))})),archives:r.archives};}
 function resolve(id,signature,key){const p=inventory().packs.find(p=>p.id===id);if(!p)throw fail('Refresh Effects and choose a template from the library.');if(!signature||signature!==p.signature)throw fail('The Effects template or its assets changed. Refresh Effects before adding it.');const file=key?p.projects.find(f=>f.key===key):p.projects.length===1?p.projects[0]:null;if(!file)throw fail('Refresh Effects and choose the project inside this pack.');return {id:p.id,name:p.name,signature:p.signature,project_key:file.key,path:file.path,media:p.media};}
 return {list,resolve};
}
module.exports={createCatalog,DEFAULT_ROOT};
