'use strict';
const path=require('node:path'),fs=require('node:fs'),model=require('./model.js');
const models=['text','typography','styling','transitions','builders','masks','camera','layers','timing','library','delivery'];
for(const name of models)require('./'+name+'-model.js');
const ascii=v=>JSON.stringify(v).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
function prepare(p={}){
 try{
  if(p.action==='toolkitCatalog'){const list=model.catalog().slice().sort((a,b)=>a.number-b.number);return {result:{ok:true,categories:model.categories().slice().sort((a,b)=>list.find(t=>t.category===a.id).number-list.find(t=>t.category===b.id).number),tools:list}};}
  if(p.action!=='toolkitApply')throw Error('Choose a tool from Effects.');
  return {payload:model.validate(p)};
 }catch(e){throw Object.assign(Error(e.message),{code:'effects_toolkit',details:String(e)});}
}
function nativeRequest(root,payload){
 const files=['quick-motion/model.js','effects-toolkit/model.js',...models.map(m=>'effects-toolkit/'+m+'-model.js'),...['controls','motion','text','typography','builders','styling','layer-styles','transitions','masks','camera','layers','timing','library','delivery','host'].map(m=>'effects-toolkit/'+m+'.jsx')];
 return '(function(){try{'+files.map(f=>'$.evalFile(new File('+ascii(path.join(root,'editor_plugins',f).replace(/\\/g,'/'))+'));').join('')+'return storylensToolkit('+ascii(payload)+');}catch(e){return hJSON({error:"Effects tools could not load. Reopen Storylens and try again.",code:"effects_toolkit",details:String(e)});}})()';
}
function finish(result,appData=process.env.APPDATA){
 if(!result?.ok||!result.preview_paths)return result;
 if(!appData||!Array.isArray(result.preview_paths)||result.preview_paths.length!==8)throw Error('The preview cache receipt is incomplete.');
 model.find(result.preview_tool);const base=path.resolve(appData,'Storylens','toolkit-previews'),frames=[];let bytes=0;
 for(const filename of result.preview_paths){if(typeof filename!=='string'||path.dirname(path.resolve(filename)).toLowerCase()!==base.toLowerCase()||!path.basename(filename).startsWith(result.preview_tool+'-')||path.extname(filename).toLowerCase()!=='.png')throw Error('Preview files must stay inside the Storylens preview cache.');const stat=fs.lstatSync(filename);if(stat.isSymbolicLink()||!stat.isFile()||stat.size>2*1024*1024||(bytes+=stat.size)>4*1024*1024)throw Error('The preview is too large to cache in the panel. Use a smaller composition preview.');const data=fs.readFileSync(filename);if(data.subarray(0,8).toString('hex')!=='89504e470d0a1a0a')throw Error('The preview is not a readable PNG.');frames.push('data:image/png;base64,'+data.toString('base64'));}
 return {...result,preview_paths:undefined,preview_frames:frames};
}
module.exports={prepare,nativeRequest,finish};
