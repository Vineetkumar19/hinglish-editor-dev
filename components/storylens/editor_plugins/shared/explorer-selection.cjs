/* One read-only Explorer selection request. No hooks, hotkeys or injected input. */
const path=require('path');
function readExplorerSelection(root,execFile=require('child_process').execFile,windowHandle=0){
 if(!Number.isSafeInteger(windowHandle)||windowHandle<0)return Promise.reject(Error('Select the Explorer window again.'));
 const args=['-E','-X','utf8','-m','hinglish_app.explorer_selection'];if(windowHandle)args.push('--window-handle',String(windowHandle));
 return new Promise((resolve,reject)=>execFile(path.join(root,'.venv','Scripts','python.exe'),args,{cwd:root,windowsHide:true,shell:false,timeout:8000,maxBuffer:65536},(error,stdout,stderr)=>{
  if(error)return reject(Object.assign(Error('Select one image or video in Explorer, then press Copy again.'),{details:String(stderr||error.message)}));
  try{const value=JSON.parse(String(stdout).replace(/^\uFEFF/,''));if(!Array.isArray(value.paths)||value.paths.length!==1||typeof value.paths[0]!=='string'||!path.win32.isAbsolute(value.paths[0])||!/^\.(jpe?g|png|tiff?|bmp|gif|psd|exr|tga|mp4|mov|avi|mxf|m4v|webm)$/i.test(path.extname(value.paths[0])))throw Error('Select one supported media file.');resolve({paths:value.paths});}
  catch(e){reject(Object.assign(Error('Select one image or video in a single Explorer window.'),{details:e.message}));}
 }));
}
module.exports={readExplorerSelection};
