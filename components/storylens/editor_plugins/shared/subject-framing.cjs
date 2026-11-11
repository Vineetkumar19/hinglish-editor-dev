/* Local, bounded CPU inspection of the media path returned by AE, never UI code. */
const path=require('path');
function analyzeMedia(root,file,execFile=require('child_process').execFile){
 if(typeof file!=='string'||!path.win32.isAbsolute(file)||!/^\.(jpe?g|png|tiff?|bmp|gif|webp|psd|exr|tga|mp4|mov|avi|mxf|m4v|webm)$/i.test(path.extname(file)))return Promise.reject(Error('Choose one local picture or video.'));
 return new Promise((resolve,reject)=>execFile(path.join(root,'.venv','Scripts','python.exe'),['-E','-X','utf8','-m','hinglish_app.adobe_framing','--path',file],{cwd:root,windowsHide:true,shell:false,timeout:20000,maxBuffer:262144},(error,stdout,stderr)=>{
  try{if(error)throw error;const value=JSON.parse(String(stdout).replace(/^\uFEFF/,''));if(value.error)throw Object.assign(Error(value.error),value);
   if(value.version!==1||!Array.isArray(value.faces)||value.faces.length>1000||!(value.width>0&&value.height>0))throw Error('Invalid framing response.');resolve(value);
  }catch(e){reject(Object.assign(Error('Automatic picture framing could not finish. Copy the media again.'),{code:'copy_paste_media',details:String(e.details||stderr||e.message)}));}
 }));
}
module.exports={analyzeMedia};
