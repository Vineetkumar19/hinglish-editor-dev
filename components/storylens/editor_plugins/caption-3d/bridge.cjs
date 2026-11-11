const fs=require('fs'),path=require('path'),{prepare,prepareUpdate,catalog}=require('./model.cjs');
function nativeRequest(root,input={}){
 if(/^pattern/.test(input.action||'')){for(const f of ['bridge.cjs','model.cjs','profile.json']){const p=path.join(root,'editor_plugins/caption-patterns',f);delete require.cache[require.resolve(p)];}for(const directory of ['caption-two','caption-three','caption-six'])for(const f of ['model.cjs','profile.json']){const p=path.join(root,'editor_plugins',directory,f);delete require.cache[require.resolve(p)];}const fp=path.join(root,'editor_plugins/caption-patterns/fonts.cjs');if(require.cache[require.resolve(fp)]?.exports?.revision!==5)delete require.cache[require.resolve(fp)];return require('../caption-patterns/bridge.cjs').nativeRequest(root,input);}
 const header=fs.readFileSync(path.join(root,'editor_plugins/shared/aftereffects-project-session.jsx'),'utf8')+'\n'+fs.readFileSync(path.join(__dirname,'host.jsx'),'utf8');
 if(input.action==='context')return '(function(){'+header+'return storylens3DContext();})()';
 if(!['insert','selected','update','sound','depth'].includes(input.action))throw Error('Choose a title action.');
 if(input.action!=='selected'&&!/^[a-f0-9]{32}$/.test(input.request_id||''))throw Error('Choose the title again.');
 if(input.action!=='selected'&&(!input.context||!/^\d+$/.test(input.context.comp_id||'')||!Number.isFinite(input.context.time)||input.context.time<0))throw Error('Open a composition first.');
 if(['update','sound','depth'].includes(input.action)&&(!/^\d+$/.test(input.context.layer_id||'')||!/^\d+$/.test(input.context.source_id||'')))throw Error('Use Edit selected first.');
 const plan=input.action==='selected'?{family:'3d3',sound_fx:false}:['update','sound','depth'].includes(input.action)?prepareUpdate(input):prepare(input),request={...input.context,request_id:input.request_id};
 // Installed AE imports existing local WAVs. Portable JSX embeds them instead.
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'library/3d-caption-sounds/manifest.json'),'utf8')),assets={};
 if(plan.sound_fx)for(const kind of ['whoosh','click','pop']){
  const asset=manifest[kind];if(!/^[a-f0-9]{64}$/.test(asset.sha256||''))throw Error('A caption sound manifest is invalid. Restore the Storylens sound files.');
  const file=path.join(root,'library','3d-caption-sounds',asset.sha256+'.wav'),bytes=fs.readFileSync(file);
  if(require('crypto').createHash('sha256').update(bytes).digest('hex')!==asset.sha256)throw Error('A caption sound changed. Restore the Storylens sound files before adding this title.');
  assets[kind]={path:file,sha256:asset.sha256,duration:asset.duration};
 }
 const engine=fs.readFileSync(path.join(__dirname,'folders.jsx'),'utf8')+'\n$.global.StorylensSurfaceCatalog='+JSON.stringify(catalog)+';\n$.global.StorylensCaptionAudioData='+JSON.stringify(assets)+';\n'+fs.readFileSync(path.join(__dirname,'sound.jsx'),'utf8')+'\n'+fs.readFileSync(path.join(__dirname,'sound-edit.jsx'),'utf8')+'\n'+fs.readFileSync(path.join(__dirname,'solid.jsx'),'utf8')+'\n'+fs.readFileSync(path.join(__dirname,plan.family==='3d1'?'camera-engine.jsx':'engine.jsx'),'utf8');
 const invoke=input.action==='selected'?'$.global.StorylensCaptionAudioEdit.describe()':input.action==='depth'?'$.global.StorylensSolidTitles.upgrade('+JSON.stringify(plan)+','+JSON.stringify(request)+')':input.action==='sound'?'$.global.StorylensCaptionAudioEdit.update('+JSON.stringify(plan)+','+JSON.stringify(request)+')':input.action==='update'?'$.global.StorylensSurfaceTitles.update('+JSON.stringify(plan)+','+JSON.stringify(request)+')':'storylens3DInsert('+JSON.stringify(plan)+','+JSON.stringify(request)+')';
 return '(function(){'+header+'try{'+engine+'return hJSON('+invoke+');}catch(e){var details=String(e),message="The title could not be changed. Select its outer precomp in the timeline and retry.";if(/Solid 3D1 needs|real text extrusion/.test(details))message="Solid 3D1 needs Cinema 4D text extrusion. Check that renderer in this composition, then retry.";else if(/Move outer effects or masks/.test(details))message="Move the title outer effects or masks inside its precomp before enabling solid depth.";return hJSON({error:message,code:"editor_native",details:details});}})()';
}
module.exports={nativeRequest};
