'use strict';
const fs=require('fs'),path=require('path'),cp=require('child_process');
function prepare(root,result){
 if(!result||result.type!=='reel_recreate'||!/^[a-f0-9]{32}$/.test(result.id||''))return Promise.reject(Error('Choose a saved Reel Recreate result.'));
 if(result.premiere_bundle){
  const bundle=JSON.parse(fs.readFileSync(result.premiere_bundle,'utf8'));
  if((bundle.reel_id||bundle.id)!==result.id)throw Error('This Premiere preparation belongs to a different reel.');
  if(JSON.stringify(bundle.caption_snapshot)===JSON.stringify(result.caption)&&JSON.stringify(bundle.cues_snapshot)===JSON.stringify(result.cues))return Promise.resolve(bundle);
 }
 const revision=/^[a-f0-9]{32}$/.test(result.revision_id||'')?result.revision_id:'original';
 const destination=path.join(root,'output','reel-recreate','premiere-handoffs',result.id,revision);
 fs.mkdirSync(destination,{recursive:true});const input=path.join(destination,'reel-plan.json');
 fs.writeFileSync(input,JSON.stringify(result,null,2),'utf8');
 const script=path.join(root,'editor_plugins','premiere-reel-recreate','prepare.py');
 return new Promise((resolve,reject)=>{
  const child=cp.spawn(path.join(root,'.venv','Scripts','python.exe'),['-B',script,input,destination],{cwd:root,windowsHide:true,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  let output='';child.stdout.on('data',data=>{output=(output+data).slice(-6000)});child.stderr.on('data',data=>{output=(output+data).slice(-6000)});
  child.on('error',reject);child.on('exit',code=>{if(code!==0)return reject(Error('The editable Premiere project could not be prepared. '+output));try{resolve(JSON.parse(fs.readFileSync(path.join(destination,'premiere-bundle.json'),'utf8')))}catch(error){reject(error)}});
 });
}
module.exports={prepare};
