'use strict';
/* Fixed-root local capability; UI cannot supply executable code or arbitrary paths. */
const fs=require('fs'),path=require('path'),{createCatalog}=require('./catalog.cjs'),{createGallery}=require('./gallery.cjs');
const galleries=new Map();
function gallery(root,payload,runNative){let session=galleries.get(root);if(!session){session=createGallery(root,(id,signature)=>{const p=createCatalog().resolve(id,signature);if(!signature||p.signature!==signature)throw Error('Refresh the Text gallery before using this updated pack.');return p;});galleries.set(root,session);}return session.handle(payload,runNative);}
function prepare(root,payload){const catalog=createCatalog();if(payload.action==='catalog')return {result:catalog.list()};
 if(payload.action==='destination')return {payload:{action:'destination'}};
 if(payload.action==='insertChoice'){let session=galleries.get(root);if(!session){session=createGallery(root,(id,signature)=>{const pack=catalog.resolve(id,signature);if(!signature||pack.signature!==signature)throw Error('Refresh the Text gallery before using this updated pack.');return pack;});galleries.set(root,session);}return {payload:session.choice(payload)};}
 if(payload.action==='selectedBackground')return {payload:{action:'selectedBackground',background_off:payload.background_off===true,request_id:'background-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)}};
 const pack=catalog.resolve(payload.pack_id,payload.signature);if(!payload.signature||pack.signature!==payload.signature)throw Error('Refresh Effects before opening this updated template.');
 if(payload.action==='load')return {payload:{action:'load',pack}};
 if(!['preview','insert','background'].includes(payload.action))throw Error('Choose a scene or its background control in Effects.');
 if(typeof payload.project_id!=='string'||payload.project_id.length>2048||!/^\d+$/.test(String(payload.scene_id)))throw Error('Reopen the Effects pack in the current project.');
 const clean={action:payload.action,pack_id:pack.id,signature:pack.signature,project_id:payload.project_id,scene_id:String(payload.scene_id)};
 if(payload.action==='insert'){if(!/^[-a-zA-Z0-9_]{5,80}$/.test(payload.request_id||''))throw Error('Choose the title again to add it.');clean.request_id=payload.request_id;clean.background_off=payload.background_off===true;}
 if(payload.action==='background'){const r=payload.receipt||{};if(!/^[-a-zA-Z0-9_]{5,80}$/.test(r.request_id||'')||!['composition_id','target_id','layer_id'].every(k=>/^\d+$/.test(String(r[k]))))throw Error('Add a title first, then use its background switch.');clean.receipt={request_id:r.request_id,composition_id:String(r.composition_id),target_id:String(r.target_id),layer_id:String(r.layer_id)};clean.background_off=payload.background_off===true;}
 if(payload.action==='preview'){const base=fs.realpathSync(root),folder=path.join(base,'cache','cinematic-text',pack.id,pack.signature);let cursor=base;for(const part of ['cache','cinematic-text',pack.id,pack.signature]){cursor=path.join(cursor,part);if(fs.existsSync(cursor)&&fs.lstatSync(cursor).isSymbolicLink())throw Error('The preview folder changed. Restore the local cache folder before retrying.');}fs.mkdirSync(folder,{recursive:true});const output=path.join(folder,clean.scene_id+'.png');if(fs.existsSync(output)&&fs.lstatSync(output).isSymbolicLink())throw Error('The preview file changed. Restore the local cache file before retrying.');clean.output_path=output;return {payload:clean,preview:output};}
 return {payload:clean};
}
function image(file){return require('./png-preview.cjs').image(file);}
module.exports={prepare,image,gallery,nativeRequest:(root,payload)=>require('../preset-library/native-request.cjs').build(root,payload,'text')};
