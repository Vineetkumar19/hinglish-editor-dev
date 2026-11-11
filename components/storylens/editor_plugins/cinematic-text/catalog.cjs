'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const DEFAULT_ROOT='D:/Editing/Cinematics AE templates/Text templates';
const ignored=/(?:^|[\\/])(?:__MACOSX|Adobe After Effects Auto-Save|Auto-Save|backups?|\.git)(?:[\\/]|$)/i;
function createCatalog(root=DEFAULT_ROOT){
 const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
 function walk(base,depth=0,files=[]){if(depth>12||files.length>16000)return files;for(const e of fs.readdirSync(base,{withFileTypes:true})){if(e.name.startsWith('.')||e.isSymbolicLink())continue;const p=path.join(base,e.name);if(ignored.test(p)||fs.lstatSync(p).isSymbolicLink())continue;if(e.isDirectory())walk(p,depth+1,files);else if(e.isFile())files.push(p);}return files;}
 function inside(p){const base=fs.realpathSync(root),real=fs.realpathSync(p),rel=path.relative(base,real);if(!rel||rel.startsWith('..')||path.isAbsolute(rel))throw Error('Refresh the Effects library and choose a local pack.');return real;}
 function inventory(){if(!fs.existsSync(root))throw Error('The Text templates folder is unavailable. Connect drive A, then refresh Effects.');const files=walk(root),groups=new Map();
  for(const file of files){if(!/\.(aep|aepx|aet)$/i.test(file))continue;const rel=path.relative(root,file),parts=rel.split(path.sep),key=parts.length>1?parts[0]:path.basename(file,path.extname(file));if(!groups.has(key))groups.set(key,[]);groups.get(key).push(file);}
  const packs=[];for(const [key,versions] of groups){versions.sort((a,b)=>{const rank=x=>Number(/(?:converted|backup|old|\bCS[3-6]\b)/i.test(x))*100+x.split(path.sep).length;return rank(a)-rank(b)||a.localeCompare(b,undefined,{numeric:true});});const file=inside(versions[0]),stat=fs.statSync(file),kind=/12.text.interactive/i.test(key)?'interactive':/intro.cinematic/i.test(key)?'intro':/cinematic.title.pack/i.test(key)?'cinematic':'generic',names={interactive:'12 Text',cinematic:'Cinematic Title',intro:'Intro Cinematic'};
   const resolvedKind=/cinematic.lower.third/i.test(key)?'lowerThirds':kind;
   const record={id:hash(path.relative(root,file).toLowerCase()).slice(0,24),signature:hash([file,stat.size,stat.mtimeMs].join('|')).slice(0,24),name:resolvedKind==='lowerThirds'?'Cinematic Lower Thirds':names[kind]||path.basename(file,path.extname(file)),kind:resolvedKind,expected:{interactive:12,cinematic:3,intro:21,lowerThirds:6}[resolvedKind]||null,path:file,packageRoot:partsRoot(file,key),versions:versions.length};
   const namesSeen=new Set(),projects=[];for(const candidate of versions){const stem=path.basename(candidate,path.extname(candidate));if(namesSeen.has(stem.toLowerCase()))continue;namesSeen.add(stem.toLowerCase());const real=inside(candidate),st=fs.statSync(real);projects.push({...record,id:hash(path.relative(root,real).toLowerCase()).slice(0,24),signature:hash([real,st.size,st.mtimeMs].join('|')).slice(0,24),name:stem,path:real,versions:1});}if(projects.length>1)record.projects=projects;
   packs.push(record);
  }packs.sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true}));return {packs,files};
 }
 function partsRoot(file,key){const candidate=path.join(root,key);return fs.existsSync(candidate)&&fs.statSync(candidate).isDirectory()?candidate:path.dirname(file);}
 function publicRow({path:unused,packageRoot:unused2,projects,...r}){return {...r,...(projects?{projects:projects.map(publicRow)}:{})};}
 function list(){return {ok:true,root,packs:inventory().packs.map(publicRow)};}
 function resolve(id,signature){const inv=inventory(),p=inv.packs.flatMap(r=>r.projects||[r]).find(r=>r.id===id);if(!p)throw Error('Refresh Effects and choose a pack from this library.');if(signature&&signature!==p.signature)throw Error('The template file changed. Refresh Effects before using it.');const media=inv.files.filter(f=>f.startsWith(p.packageRoot+path.sep)&&! /\.(aep|aepx|aet|zip|exe|jsx|js|pdf|txt|html)$/i.test(f)).map(f=>inside(f));return {...p,media};}
 return {list,resolve};
}
module.exports={createCatalog,DEFAULT_ROOT};
