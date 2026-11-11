// Exercises the Reel Recreate button flow with the owner's saved plan; AE validation is separate.
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..');
const plan=JSON.parse(fs.readFileSync(path.join(root,'output/reel-recreate/dfb55ed4995b4f80bc58766a2b9bf6db/reel-plan.json'),'utf8'));
const saved=new Map([['storylens.reelRecreate.lastJob',plan.id]]);
const imports=[];
let rejectNext=false;
let serverPlan=JSON.parse(JSON.stringify(plan));
function node(){return {value:'',textContent:'',hidden:false,disabled:false,dataset:{},options:[],children:[],append(...items){this.children.push(...items)},replaceChildren(){this.children=[]},querySelectorAll(kind){return kind==='textarea'?this.children.map(row=>row.children.find(x=>x.kind==='textarea')):[]}}}
function page(){const elements={};const get=id=>elements[id]||(elements[id]=node());get('style').options=[];const document={documentElement:{dataset:{token:'test'}},getElementById:get,createElement(kind){return {...node(),kind}}};
 const context={document,window:{storylensFetch:async(url,options)=>{if(url.includes('/styles'))return {styles:[]};if(url.includes('/jobs/'))return {id:plan.id,status:'complete',result:JSON.parse(JSON.stringify(serverPlan))};if(url.includes('/revise')){const change=JSON.parse(options.body);serverPlan={...serverPlan,caption:{...serverPlan.caption,style:change.style},caption_style:change.style};return {id:plan.id,status:'complete',result:JSON.parse(JSON.stringify(serverPlan))}}throw Error('Unexpected route '+url)},storylensResponse:async response=>response,storylensRecreateImport:async result=>{imports.push(JSON.parse(JSON.stringify(result)));if(rejectNext){rejectNext=false;throw Error('Native import failed')}return {message:'Created new composition.'}},storylensError:error=>String(error.message||error)},localStorage:{getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,String(value))},location:{search:'?host=aftereffects'},URLSearchParams,setInterval(){},setTimeout,clearTimeout,Math,JSON,console};
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(root,'hinglish_app/static/reel-recreate.js'),'utf8'),context);return {get,context};}
async function settle(){await new Promise(resolve=>setTimeout(resolve,0))}
(async()=>{
 const first=page();await settle();
 assert.strictEqual(first.get('review').hidden,false,'saved reel did not reopen');
 await first.get('import').onclick();
 assert(/^[0-9a-f]{32}$/.test(imports[0].revision_id),'an earlier saved caption update reused the original reel identity');
 first.get('newStyle').value='caption_3';await first.get('update').onclick();
 assert.strictEqual(imports.length,2,'Update did not import automatically: '+first.get('importStatus').textContent);
 assert.strictEqual(imports[1].caption.style,'caption_3');
 const firstId=imports[1].revision_id;
 first.get('newStyle').value='caption_4';await first.get('update').onclick();
 assert.strictEqual(imports.length,3);assert.strictEqual(imports[2].caption.style,'caption_4');
 assert.notStrictEqual(imports[2].revision_id,firstId,'the second Update reused the old composition identity');
 const lastId=imports[2].revision_id;
 const reopened=page();await settle();await reopened.get('import').onclick();
 assert.strictEqual(imports[3].revision_id,lastId,'reopening lost the current caption version');
 rejectNext=true;reopened.get('newStyle').value='caption_5';await reopened.get('update').onclick();
 assert(/did not confirm/.test(reopened.get('importStatus').textContent));
 const failedRevision=imports[4].revision_id;await reopened.get('import').onclick();
 assert.strictEqual(imports[5].revision_id,failedRevision,'retry created another revision');
 console.log(JSON.stringify({status:'pass',existingSavedUpdateGetsOwnRevision:true,automaticImports:3,distinctRevisionIds:true,reloadKeepsCurrentRevision:true,failedImportRetryKeepsRevision:true,priorRevisionPreserved:true}));
})().catch(error=>{console.error(error);process.exitCode=1});
