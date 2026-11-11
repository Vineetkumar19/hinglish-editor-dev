/* Read-only catalogue adapter. Never evaluates JSX or starts Adobe. */
'use strict';
const path=require('path'),root=path.resolve(__dirname,'..');
async function read(request){
 const {action,payload:p={}}=request;
 if(action==='animationPresets'&&p.action==='catalog')return require('../editor_plugins/animation-presets/bridge.cjs').prepare(p).result;
 if(action==='effectsLibrary'&&p.action==='catalog')return require('../editor_plugins/effects-library/bridge.cjs').prepare(p).result;
 if(action==='cinematicText'&&p.action==='catalog')return require('../editor_plugins/cinematic-text/catalog.cjs').createCatalog().list();
 if(action==='presetLibrary'){
  if(['categories','catalog'].includes(p.action))return require('../editor_plugins/preset-library/bridge.cjs').session(root).prepare(p).result;
  if(p.action==='motionCatalog')return require('../editor_plugins/quick-motion/bridge.cjs').prepare({action:'motionCatalog'}).result;
  if(p.action==='toolkitCatalog')return require('../editor_plugins/effects-toolkit/bridge.cjs').prepare({action:'toolkitCatalog'}).result;
  if(['gallery','galleryStatus'].includes(p.action)){
   const result=await require('../editor_plugins/preset-library/bridge.cjs').session(root).gallery({...p,action:'galleryStatus'},()=>{throw Error('Native rendering is not a catalogue action.');});
   return {...result,native_status:result.status,status:result.scenes?.length&&result.scenes.every(s=>s.image)?'cached':'needs_editor'};
  }
 }
 throw Error('This action needs the connected After Effects panel.');
}
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>{input+=chunk;if(input.length>100000)throw Error('Catalogue request too large.');});process.stdin.on('end',async()=>{try{process.stdout.write(JSON.stringify(await read(JSON.parse(input))));}catch(e){process.stdout.write(JSON.stringify({error:String(e.message||e)}));process.exitCode=1;}});
