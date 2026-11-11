// Exercise the real content controller. No Instagram, network or real media.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const checks=require('../editor_plugins/storylens-chrome/dom-checks.js');
function fixture({label='Select from computer',missingSelector=false,manual=false,media=false}={}){
 let clock=0,currentDialog=manual?{}:null,handler,closed=0;
 const element=(text,click=()=>{})=>({innerText:text,getAttribute:()=>null,querySelector:()=>null,getClientRects:()=>[{}],click,getBoundingClientRect:()=>({x:10,y:20,width:100,height:30})});
 const select=element(label),close=element('Close',()=>{currentDialog=null;closed++});
 const composer={getClientRects:()=>[{}],querySelector:()=>null,querySelectorAll:s=>s==='input[type="file"]'?[{files:[],getAttribute:()=> 'video/mp4'}]:s==='video,img[src^="blob:"]'?(media?[{}]:[]):s==='[contenteditable="true"],textarea'?[]:missingSelector?[close]:[select,close]};
 if(manual)currentDialog=composer;
 const post=element('Post',()=>{currentDialog=composer}),create=element('New post');
 const document={querySelector:()=>null,querySelectorAll:s=>s==='[role="dialog"]'?(currentDialog?[currentDialog]:[]):s==='a[href]'?[]:[create,post,...(currentDialog?[close]:[])]};
 const chrome={runtime:{id:'fixture',onMessage:{addListener:f=>{handler=f}}}};
 class FakeDate extends Date{static now(){return clock}}
 const context=vm.createContext({document,chrome,location:{pathname:'/'},getComputedStyle:()=>({visibility:'visible'}),StorylensDOM:checks,Map,Set,Date:FakeDate,setTimeout:(fn,ms)=>{clock+=ms;fn()}});
 vm.runInContext(fs.readFileSync('editor_plugins/storylens-chrome/instagram.js','utf8'),context);
 return {call:action=>new Promise(resolve=>handler({source:'storylens',action,id:'job',name:'clip.mp4'},{id:'fixture'},resolve)),closed:()=>closed};
}
test('the real start action accepts the observed lowercase file-selection label',async()=>{
 const f=fixture();const result=await f.call('start');assert.equal(result.ok,true);assert.equal(result.uploadControl.x,60);
});
test('selector failure closes only its own empty composer and returns the bounded retry marker',async()=>{
 const f=fixture({missingSelector:true});const result=await f.call('start');assert.equal(result.ok,false);
 assert.match(result.error,/storylens-safe-retry:empty-composer/);assert.equal(f.closed(),1);
});
test('a manual composer is never closed or reused',async()=>{
 const f=fixture({manual:true});assert.equal((await f.call('idle')).ok,false);assert.equal(f.closed(),0);
 assert.equal((await f.call('start')).ok,false);assert.equal(f.closed(),0);
});
test('an owned composer containing media is preserved for review',async()=>{
 const f=fixture({media:true});assert.equal((await f.call('start')).ok,true);
 assert.equal((await f.call('idle')).ok,false);assert.equal(f.closed(),0);
});

function profileFixture({signedIn='fantasy_legends91',heading='fantasy_legends91',path='/fantasy_legends91/',accounts=[]}={}){
 let handler,clock=0;
 const picture=(account,inMain)=>({getClientRects:()=>[{}],closest:()=>inMain?{}:null,
   getAttribute:key=>key==='href'?'/'+account+'/':null,
   querySelectorAll:()=>[{alt:account+"'s profile picture"}],querySelector:()=>({alt:account+"'s profile picture"})});
 const links=[picture(signedIn,false),picture('fantasy_legends91',true),
   {getClientRects:()=>[{}],closest:()=>({}),getAttribute:key=>key==='href'?'/fantasy_legends91/reel/EXISTING/':null,querySelectorAll:()=>[]}];
 const document={querySelector:()=>null,querySelectorAll:s=>{
   if(s==='a[href]'){if(accounts.length)signedIn=accounts.shift();return [picture(signedIn,false),...links.slice(1)]}
   return s==='main h1,main h2,main [role="heading"]'?[{innerText:heading,getClientRects:()=>[{}]}]:[];
 }};
 class FakeDate extends Date{static now(){return clock}}
 const context=vm.createContext({document,chrome:{runtime:{id:'fixture',onMessage:{addListener:f=>{handler=f}}}},
   location:{pathname:path},getComputedStyle:()=>({visibility:'visible'}),StorylensDOM:checks,Map,Set,
   Date:FakeDate,setTimeout:(fn,ms)=>{clock+=ms;fn()}});
 vm.runInContext(fs.readFileSync('editor_plugins/storylens-chrome/instagram.js','utf8'),context);
 return {call:()=>new Promise(resolve=>handler({source:'storylens',action:'profile',account:'fantasy_legends91'},{id:'fixture'},resolve))};
}

test('destination profile loads without an Edit Profile button in the current Instagram layout',async()=>{
 assert.equal((await profileFixture().call()).ok,true);
});

test('viewing the target profile cannot impersonate its signed-in account',async()=>{
 const result=await profileFixture({signedIn:'other_account'}).call();
 assert.equal(result.ok,false);assert.match(result.error,/could not confirm the requested account/);
});

test('profile readiness requires the target handle in the loaded main heading',async()=>{
 assert.equal((await profileFixture({heading:'Some other account'}).call()).ok,false);
});

test('account labels may clear or revert while switching, then settle before the profile proceeds',async()=>{
 const target='fantasy_legends91';
 const f=profileFixture({accounts:['other_account',target,'',target,target,'other_account',target,target,target,target]});
 assert.equal((await f.call()).ok,true);
});
