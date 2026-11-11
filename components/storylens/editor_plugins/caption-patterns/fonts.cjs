/* Activate exact local fonts once per CEP process; no model, shell or admin writes. */
const path=require('node:path'),ready=new Set();
function ensure(root,options={}){
 const style=options.style==='caption_4'?'caption_3':options.style,key=root+(['caption_2','caption_3','caption_6'].includes(style)?'|'+style:'|caption_1');if((options.platform||process.platform)!=='win32'||ready.has(key))return;
 const result=(options.spawnSync||require('node:child_process').spawnSync)(path.join(root,'.venv/Scripts/python.exe'),[path.join(root,'tools/activate_caption_one_fonts.py'),'--root',root,...(style==='caption_6'?['--caption-six']:style==='caption_3'?['--caption-three']:style==='caption_2'?['--caption-two']:[])],{cwd:root,shell:false,windowsHide:true,encoding:'utf8',timeout:15000,maxBuffer:64*1024});
 if(result.error||result.status!==0)throw Error('Caption fonts could not be activated. Your saved speech timing is kept. '+String(result.error||result.stderr||'Retry Generate captions.').slice(-2000));
 ready.add(key);
}
module.exports={ensure,revision:5};
