'use strict';
/* Produce conservative ExtendScript, never executable caller-supplied source. */
const path=require('path');
const common=['editor_plugins/shared/aftereffects-project-session.jsx','editor_plugins/copy-paste/model.js'];
function ascii(value){return JSON.stringify(value).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));}
function build(root,payload,mode='preset'){
 if(!['preset','text'].includes(mode))throw Error('Choose a supported native preset operation.');
 const files=common.concat(mode==='preset'?['editor_plugins/copy-paste/host.jsx']:[],['editor_plugins/cinematic-text/model.js','editor_plugins/cinematic-text/host.jsx','editor_plugins/cinematic-text/selective.jsx'],mode==='preset'?['editor_plugins/preset-library/model.js','editor_plugins/preset-library/host.jsx']:[]);
 const code=files.map(file=>'stage='+ascii(file)+';$.evalFile(new File('+ascii(path.join(root,...file.split('/')).replace(/\\/g,'/'))+'));').join('');
 const fn=mode==='preset'?'storylensPanelPreset':'storylensPanelCinematicText',label=mode==='preset'?'The preset':'Text',errorCode=mode==='preset'?'preset_library':'cinematic_text';
 return '(function(){var stage="native loader";try{'+code+'stage="run '+String(payload.action||'step').replace(/[^a-zA-Z]/g,'')+'";return '+fn+'('+ascii(payload)+');}catch(e){return hJSON({error:'+ascii(label+' could not load. Check Technical details, reopen Storylens and retry.')+',code:'+ascii(errorCode)+',details:String(e)+" at line "+String(e.line||"?")+" ["+stage+"]"+(e.fileName?" ("+String(e.fileName)+")":"")});}})()';
}
module.exports={build};
