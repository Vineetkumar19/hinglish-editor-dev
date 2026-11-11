'use strict';
const fail=message=>Object.assign(Error(message),{userFacing:true});
const {createCatalog}=require('./catalog.cjs');
function prepare(value,catalog=createCatalog()){
 const p=value||{};if(p.action==='catalog')return {result:catalog.list()};
 if(p.action!=='insert')throw fail('Choose an Effects action from this panel.');
 if(!/^[-a-zA-Z0-9_]{5,80}$/.test(p.request_id||''))throw fail('Choose the effect again to add it.');
 const pack=catalog.resolve(p.pack_id,p.signature,p.project_key),clean={action:'insert',pack,request_id:p.request_id};
 if(p.scene_id!==undefined){if(!/^\d+$/.test(String(p.scene_id))||typeof p.project_id!=='string'||p.project_id.length>2048||!/^\d+$/.test(String(p.target_id)))throw fail('Reopen the effect and choose its main composition.');clean.scene_id=String(p.scene_id);clean.project_id=p.project_id;clean.target_id=String(p.target_id);}
 return {payload:clean};
}
module.exports={prepare};
