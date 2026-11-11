'use strict';
const {build}=require('./native-request.cjs');
const {createCatalog}=require('./catalog.cjs'),{createGallery}=require('../cinematic-text/gallery.cjs');
const crypto=require('crypto'),model=require('./model.js');
function createBridge(root,catalog=createCatalog()){
 const gallery=createGallery(root,(id,signature)=>catalog.resolve(id,signature)),covers=new Map(),coverPacks=new Map();
 const asCover=pack=>({...pack,signature:crypto.createHash('sha256').update(pack.signature+'|documentary-cover-v1').digest('hex').slice(0,24),profile:'documentaryCover',cover_only:true});
 const coverGallery=createGallery(root,(id,signature)=>asCover(catalog.resolve(id,signature)));
 function picture(data,name){const candidates=(data.scenes||[]).filter(s=>s.image).map(s=>({...s,duration:s.duration||1,folder:s.group||'',usedBy:0}));return model.cover(candidates,name)?.image||null;}
 function cover(p){const key=p.id+'|'+p.signature;if(!covers.has(key)){if(!coverPacks.has(key))coverPacks.set(key,catalog.resolve(p.id,p.signature));const pack=coverPacks.get(key),image=picture(coverGallery.snapshot(asCover(pack)),pack.name)||picture(gallery.snapshot(pack),pack.name)||(pack.legacy_gallery_signature?picture(gallery.snapshot({...pack,signature:pack.legacy_gallery_signature}),pack.name):null);if(image)covers.set(key,image);return image;}return covers.get(key);}
 function coverResult(data,pack){const image=picture(data,pack.name),rows=data.scenes||[],writing=rows.some(s=>!s.image&&(s.preview_status==='ready'||/native preview file was not created/i.test(s.preview_details||'')));return {ok:true,cover:true,status:image?'ready':data.status==='failed'?'failed':writing?'writing':data.status==='partial'?'failed':'building',image,missing_media:rows.find(s=>s.image)?.cover_missing_media||[],error:data.error||rows.find(s=>s.preview_error)?.preview_error,details:data.details||rows.find(s=>s.preview_details)?.preview_details};}
 async function prepareCover(p,runNative){const pack=catalog.resolve(p.pack_id,p.signature,p.category_id);if(pack.category_name!=='Documentary Templates')throw Error('Choose a documentary template cover.');const key=pack.id+'|'+pack.signature,force=p.action==='refreshCover';if(!force){const existing=cover(pack);if(existing)return {ok:true,cover:true,status:'ready',image:existing};}else covers.delete(key);
  let saved=coverGallery.snapshot(asCover(pack));
  if(p.action==='coverStatus'||(!force&&(saved.status==='failed'||saved.scenes.length&&saved.status==='partial')))return coverResult(saved,pack);
  if(gallery.isBuilding()||coverGallery.isBuilding())return {ok:true,cover:true,status:'queued',image:null};
  const action=force&&saved.scenes.length?'refreshPreview':'gallery';saved=await coverGallery.handle({...p,action,...(action==='refreshPreview'?{scene_id:'1'}:{})},runNative);const result=coverResult(saved,pack);if(result.image)covers.set(key,result.image);return result;
 }
 function prepare(p){p=p||{};if(p.action==='categories')return {result:catalog.categories()};if(p.action==='catalog'){const r=catalog.list(p.category_id,{refresh:p.refresh===true});if(r.groups)r.packs=r.packs.map(p=>({...p,preview_image:cover(p.projects?.[0]||p)}));return {result:r};}
  if(p.action==='destination')return {payload:{action:'destination'}};
  if(p.action==='insertSequence'){
   const pack=catalog.resolve(p.pack_id,p.signature,p.category_id);
   if(!['MatchCut','Speed Ramp'].includes(pack.category_name))throw Error('Choose an individual design from this section.');
   if(!/^[-a-zA-Z0-9_]{5,80}$/.test(p.request_id||'')||typeof p.project_id!=='string'||!/^\d+$/.test(String(p.composition_id))||!Number.isFinite(p.time)||p.time<0)throw Error('Choose the destination timeline and sequence again.');
   return {payload:{action:'insertSequence',pack,request_id:p.request_id,project_id:p.project_id,composition_id:String(p.composition_id),time:p.time,background_off:p.background_off===true}};
  }
  if(p.action==='insertChoice')return {payload:gallery.choice(p)};
  if(p.action==='selectedBackground')return {payload:{action:'selectedBackground',background_off:p.background_off===true,request_id:'preset-bg-'+Date.now().toString(36)}};
  if(p.action==='background'){const receipt=p.receipt||{};if(!/^[-\w]{5,80}$/.test(receipt.request_id||'')||!['composition_id','target_id','layer_id'].every(k=>/^\d+$/.test(String(receipt[k])))||typeof p.project_id!=='string')throw Error('Select an inserted preset, then use Remove BG.');return {payload:{action:'background',pack:catalog.resolve(p.pack_id,p.signature),project_id:p.project_id,receipt:{request_id:receipt.request_id,composition_id:String(receipt.composition_id),target_id:String(receipt.target_id),layer_id:String(receipt.layer_id)},background_off:p.background_off===true}};}
  throw Error('Choose a project or design from the preset gallery.');
 }
 return {prepare,cover:prepareCover,buildNative:value=>build(root,value,'preset'),gallery:async(payload,runNative)=>{if(payload.action!=='galleryStatus'){await coverGallery.waitForIdle();await gallery.waitForIdle();}const result=await gallery.handle(payload,runNative),image=picture(result,'');if(image)covers.set(payload.pack_id+'|'+payload.signature,image);return result;}};
}
const sessions=new Map();function session(root){if(!sessions.has(root))sessions.set(root,createBridge(root));return sessions.get(root);}
module.exports={createBridge,session};
