const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),runtime=path.join(root,'tools/motion-engines-runtime');
const requireRuntime=require('module').createRequire(path.join(runtime,'package.json'));
const {bundle}=requireRuntime('@remotion/bundler'),{selectComposition,renderStill,renderMedia}=requireRuntime('@remotion/renderer');
async function main(){
 const project=path.join(root,'output/motion/chatgpt-madurai-after-ten-20261024');
 const serveUrl=await bundle({entryPoint:path.join(project,'src/film.tsx'),outDir:path.join(project,'bundle'),publicDir:path.join(project,'public'),webpackOverride:c=>({...c,resolve:{...c.resolve,modules:[path.join(runtime,'node_modules'),'node_modules']}})});
 const opts={serveUrl,id:'MaduraiAfterTen',inputProps:{},browserExecutable:'C:/Program Files/Google/Chrome/Application/chrome.exe',chromiumOptions:{gl:'swangle'}};
 const composition=await selectComposition(opts);
 fs.mkdirSync(path.join(project,'review'),{recursive:true});
 for(const time of [2,10,19,28,38,46])await renderStill({...opts,composition,frame:Math.round(time*30),output:path.join(project,`review/frame-${time}.png`),logLevel:'error'});
 console.log('Six actual scene snapshots saved.');
 if(process.argv.includes('--stills-only'))return;
 let last=-1;
 await renderMedia({...opts,composition,codec:'h264',outputLocation:path.join(project,'FILM-SILENT.mp4'),concurrency:2,crf:20,overwrite:true,logLevel:'error',onProgress:p=>{const n=Math.floor(p.progress*10);if(n!==last){last=n;console.log(`Rendering ${n*10}%`);}}});
 console.log('Rendered 50-second ChatGPT-authored film.');
}
main().catch(e=>{console.error(e.stack||String(e));process.exitCode=1});
