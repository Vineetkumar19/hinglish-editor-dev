'use strict';
const path=require('path'),model=require('./model.js');
const ascii=value=>JSON.stringify(value).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
function prepare(p={}){try{if(p.action==='motionCatalog')return {result:{ok:true,presets:model.catalog()}};if(p.action!=='applyMotion')throw Error('Choose a motion preset from Effects.');return {payload:model.validate(p)};}catch(e){throw Object.assign(Error(e.message),{code:'quick_motion',details:String(e)});}}
function nativeRequest(root,payload){return '(function(){try{'+['model.js','host.jsx'].map(file=>'$.evalFile(new File('+ascii(path.join(root,'editor_plugins','quick-motion',file).replace(/\\/g,'/'))+'));').join('')+'return storylensQuickMotion('+ascii(payload)+');}catch(e){return hJSON({error:"Motion presets could not load. Reopen Storylens and try again.",code:"quick_motion",details:String(e)});}})()';}
module.exports={prepare,nativeRequest};
