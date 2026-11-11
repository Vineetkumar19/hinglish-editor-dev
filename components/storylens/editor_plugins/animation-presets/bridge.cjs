'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const ROOT='D:\\Editing\\after effects presets';
const fail=message=>Object.assign(Error(message),{code:'animation_presets'});
// Folder ownership takes precedence for unnamed files in dedicated CC packs.
// Mixed packs and root Extras use each filename. Unknown names remain Effects.
function category(relative){return relative.split('/').some(name=>/(?:^|[^a-z0-9])cc(?:['’]?s)?\d*(?=$|[^a-z0-9])|colou?r[ _-]*(?:correction|grading)|(?:^|[^a-z0-9])luts?(?=$|[^a-z0-9])/i.test(name))?'cc':'effects';}
function createLibrary(root=ROOT){
 function scan(){
  let base;try{base=fs.realpathSync(root);}catch(e){throw fail('Connect drive A and check the after effects presets folder, then Refresh.');}
  const files=new Map();let total=0;
  function walk(dir,relative){
   const folders=[],presets=[],other=[];
   for(const entry of fs.readdirSync(dir,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true,sensitivity:'base'}))){
    const full=path.join(dir,entry.name),rel=relative?relative+'/'+entry.name:entry.name;
    if(entry.isSymbolicLink()||(fs.lstatSync(full).mode&0o170000)===0o120000)continue;
    const real=fs.realpathSync(full),inside=path.relative(base,real);if(inside.startsWith('..')||path.isAbsolute(inside))continue;
    if(entry.isDirectory()){folders.push(walk(full,rel));continue;}
    if(!entry.isFile())continue;
    if(path.extname(entry.name).toLowerCase()!=='.ffx'){other.push({name:entry.name,category:category(rel)});continue;}
    const stat=fs.statSync(full),id=crypto.createHash('sha256').update(rel).digest('hex');
    const signature=crypto.createHash('sha256').update(rel+'|'+stat.size+'|'+stat.mtimeMs).digest('hex');
    const item={id,name:entry.name.slice(0,-4),signature,category:category(rel)};presets.push(item);files.set(id,{...item,path:real});total++;
   }
   return {id:relative||'root',name:relative.split('/').pop()||'Presets',folders,presets,other};
  }
  const tree=walk(base,'');
  if(tree.presets.length||tree.other.length){tree.folders.push({id:'@extras',name:'Extras',folders:[],presets:tree.presets,other:tree.other});tree.presets=[];tree.other=[];}
  return {tree,files,total};
 }
 return {prepare(p={}){
  if(p.action==='catalog'){const s=scan();return {result:{ok:true,tree:s.tree,total:s.total,root}};}
  if(p.action==='adjustment')return {payload:{action:'adjustment'}};
  if(p.action!=='apply'||!['selected','adjustment'].includes(p.target))throw fail('Choose a preset and a layer option, then try again.');
  const s=scan(),item=s.files.get(p.id);
  if(!item||item.signature!==p.signature)throw fail('This preset moved or changed. Refresh and choose it again.');
  return {payload:{action:'apply',path:item.path,name:item.name,target:p.target}};
 },scan};
}
function nativeRequest(root,payload){
 const files=['editor_plugins/shared/aftereffects-project-session.jsx','editor_plugins/animation-presets/host.jsx'];
 return '(function(){try{'+files.map(f=>'$.evalFile(new File('+JSON.stringify(path.join(root,...f.split('/')))+'));').join('')+'return storylensAnimationPresets('+JSON.stringify(payload)+');}catch(e){return JSON.stringify({error:"Presets could not load. Reopen Storylens and try again.",code:"animation_presets",details:String(e)});}})()';
}
const library=createLibrary();module.exports={createLibrary,category,nativeRequest,prepare:p=>library.prepare(p)};
