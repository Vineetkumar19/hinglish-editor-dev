// Execute the actual browser renderer with an offline canvas, without opening an app.
const fs=require('fs'),vm=require('vm'),path=require('path');
const {createCanvas,GlobalFonts}=require('@napi-rs/canvas');
const root=path.resolve(__dirname,'..'),out=path.join(root,'output/captions/serif-circle-correction');
for(const [family,file] of [['Circle Sans','Inter-SemiBold.ttf'],['Circle Serif','PlayfairDisplay-BoldItalic.ttf'],['Circle Italic','InterDisplay-SemiBoldItalic.ttf']])GlobalFonts.registerFromPath(path.join(root,'hinglish_captions/fonts',file),family);
const examples=[['Your story deserves attention','Why one single post'],['Small ideas create impact','Your audience needs more.'],['ONE POST CHANGES EVERYTHING','ONE POST CHANGES NOTHING.'],['Ideas aur kahani banao','middle and bottom funnel.']];
const failures=[],results=[];
async function run(profileFile,label){
 const project={serif_circle_profile:JSON.parse(fs.readFileSync(profileFile,'utf8'))};
 const canvas=createCanvas(1280,2276);canvas.style={};canvas.setAttribute=()=>{};
 const controls={font:{value:'template'},position:{value:65},size:{value:100}};
 const caption={style:{},replaceChildren(){},setAttribute(){}};
 let canvasCalls=0;
 const sandbox={project,document:{createElement:()=>{if(canvasCalls++===0)return canvas;return createCanvas(1280,2276)},fonts:{load:async()=>[]}},draw(){},currentStyle:'serif_circle_draft',visibility:'phrase',
  cues:[],video:{currentTime:0,addEventListener(){}},stage:{clientHeight:640,clientWidth:360},templates:{serif_circle_draft:{default_position:.65}},
  $:selector=>controls[selector.slice(1)],caption,updateSelection(){},wordColors:[],fonts:{},wordsAt:()=>sandbox.cues[0].words.map(w=>w.text),console};
 const context=vm.createContext(sandbox);
 vm.runInContext(fs.readFileSync(path.join(root,'hinglish_captions/template_patterns.js'),'utf8'),context);
 const code=fs.readFileSync(path.join(root,'hinglish_captions/serif_circle.js'),'utf8').replace('\n})();','\n globalThis.serifProbe={recipeFor,plan,points};\n})();').replace('if(source.taper){const left','globalThis.strokeAudit={assigned:(source.stroke||3)*ratio,actual:ctx.lineWidth};if(source.taper){const left');
 vm.runInContext(code,context);await Promise.resolve();await Promise.resolve();
 for(const [index,[text,source]] of examples.entries()){
  sandbox.cues=[{start:0,end:2.5,template_source:source,template_slot:index,words:text.split(' ').map((text,i)=>({text,start:i*.6,end:(i+1)*.6}))}];
  sandbox.video.currentTime=2.49;sandbox.draw();
  if(sandbox.strokeAudit&&Math.abs(sandbox.strokeAudit.actual-sandbox.strokeAudit.assigned)>.01)failures.push({label,index,error:'canvas stroke width differs',...sandbox.strokeAudit});
  const recipe=context.serifProbe.recipeFor(sandbox.wordsAt()),runs=context.serifProbe.plan(sandbox.wordsAt(),recipe);
  if(recipe.template_pattern&&recipe.template_pattern!==source)failures.push({label,index,error:'source changed'});
  if(!runs.every(r=>Number.isFinite(r.origin_x)&&Number.isFinite(r.baseline)))failures.push({label,index,error:'invalid position'});
  const planJSON=JSON.stringify(runs);sandbox.video.currentTime=.55;sandbox.draw();
  const after=context.serifProbe.plan(sandbox.wordsAt(),context.serifProbe.recipeFor(sandbox.wordsAt()));
  if(JSON.stringify(after)!==planJSON)failures.push({label,index,error:'layout moved on reveal'});
  sandbox.video.currentTime=2.49;sandbox.draw();
  // Present caption alpha over the actual black review background.
  const review=createCanvas(canvas.width,canvas.height),reviewCtx=review.getContext('2d');reviewCtx.fillStyle='black';reviewCtx.fillRect(0,0,review.width,review.height);reviewCtx.drawImage(canvas,0,0);
  fs.writeFileSync(path.join(out,`canvas-${label}-${index+1}.png`),review.toBuffer('image/png'));
  results.push({label,text,source,rows:recipe.rows.map(r=>({source_row:r.source_row,band:r.band,x:r.x,y:r.y,size:r.size})),bounds:recipe.bounds});
 }
}
(async()=>{await run(path.join(root,'hinglish_captions/serif_circle_reference.json'),'current');await run(path.join(out,'before-profile.json'),'embedded-old');
 const report={kind:'offline_canvas_renderer_audit',cases:results.length,failures,results,application_validation:'Not run; this is an offline canvas harness.'};
 fs.writeFileSync(path.join(out,'canvas-validation.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({cases:results.length,failures}));if(failures.length)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1});
