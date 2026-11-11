/* Run only after native JSX returns; never block AE's UI thread. */
async function finishFolderCleanup(host, action, payload, result, run) {
 if(host!=='aftereffects'||!result.ok||result.needs_choices||!['templateAlign','templateCollapseFolders','templateImport','imageDownload','downloadImport','templateText','presetLibrary'].includes(action)||action==='templateAlign'&&payload.collapse_folders===false)return result;
 if(action==='presetLibrary'&&!['insertChoice','insertSequence'].includes(payload.action))return result;
 if(action==='templateText'&&payload.action!=='apply')return result;
 if(action==='templateImport'&&(result.running||!['complete','stopped','needs_attention'].includes(result.state)||!result.imported))return result;
 try { await new Promise(resolve=>setTimeout(resolve,350));result.ui_cleanup=await run(result.project_id); }
 catch(error){result.ui_cleanup={ok:false,message:'Your templates are kept. Folder cleanup could not finish; reopen Storylens to try again.',details:String(error.message||error)};}
 return result;
}
function runFolderCleanup(root, projectId, execFile=require('child_process').execFile){
 const path=require('path');
 if(!root||typeof projectId!=='string'||!projectId)return Promise.resolve({ok:false,message:'Save this project once before using automatic folder cleanup.'});
 return new Promise((resolve,reject)=>execFile(path.join(root,'.venv','Scripts','python.exe'),['-E','-X','utf8',path.join(root,'hinglish_app','adobe_folder_cleanup.py'),'--project-id',projectId],{cwd:root,timeout:12000,windowsHide:true,shell:false,maxBuffer:32768},(error,stdout)=>{
  if(error){reject(error);return;}
  try{const result=JSON.parse(stdout);if(typeof result.ok!=='boolean')throw Error('Invalid cleanup result');resolve(result);}catch(e){reject(e);}
 }));
}
module.exports={finishFolderCleanup,runFolderCleanup};
