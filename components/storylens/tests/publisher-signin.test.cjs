const test=require('node:test'),assert=require('node:assert/strict');
const {create}=require('../hinglish_app/static/publisher-signin.js');
const URL='https://accounts.google.com/o/oauth2/auth?state=fixture';
function fixture(start){
 const button={disabled:false,textContent:''},status={textContent:''},link={hidden:true,href:''};
 const opened={location:{replace(url){this.url=url}},close(){this.closed=true}};let count=0;
 const controller=create({button,status,link,start,profile:()=> 'cricket',clientFile:()=>'',refresh:async()=>{},openWindow:()=>{count++;return opened},error:e=>e.message});
 return {controller,button,status,link,opened,count:()=>count};
}
test('double click keeps the sign-in window reachable and starts one request',async()=>{
 let release,calls=0;const f=fixture(()=>{calls++;return new Promise(r=>release=r)});
 const running=f.controller.click();await f.controller.click();assert.equal(calls,1);assert.equal(f.count(),1);assert.equal(f.button.disabled,false);
 release({id:'one',authorization_url:URL});await running;assert.equal(f.opened.location.url,URL);assert.equal(f.link.href,URL);assert.equal(f.link.hidden,false);
 f.controller.observe([{id:'one',kind:'youtube_signin',profile:'cricket',status:'failed',message:'Google sign-in timed out. Try again.'}]);
 assert.equal(f.button.disabled,false);assert.equal(f.link.hidden,true);assert.match(f.status.textContent,/timed out/);
});
test('legacy queued login still opens a window on click without adding a login request',async()=>{
 let calls=0;const f=fixture(async()=>{calls++;return{}});f.controller.observe([{id:'old',status:'working',message:'Complete Google sign-in in the browser that opens'}]);
 assert.equal(f.button.disabled,false);await f.controller.click();assert.equal(f.count(),1);assert.equal(calls,0);assert.match(f.status.textContent,/Waiting for Google/i);
});
test('legacy queued connection remains busy between browser attempts',()=>{
 const f=fixture(async()=>({}));f.controller.observe([{id:'old',status:'working',message:'Preparing…',can_stop:false,can_resume:false}]);
 assert.equal(f.button.disabled,false);
});
test('request failure leaves the opened window available with an explanation',async()=>{
 const f=fixture(async()=>{throw Error('The local sign-in request failed. Try again.');});await f.controller.click();
 assert.equal(f.count(),1);assert.notEqual(f.opened.closed,true);assert.equal(f.button.disabled,false);assert.match(f.status.textContent,/failed/);
});
test('waiting message clears when the old attempt finishes',()=>{
 const f=fixture(async()=>({}));f.controller.observe([{status:'working',message:'Complete Google sign-in in the browser that opens'}]);
 f.controller.observe([]);assert.equal(f.button.disabled,false);assert.equal(f.status.textContent,'');
});
test('blocked popups retain a clickable Google fallback; wrong hosts are rejected',async()=>{
 const f=fixture(async()=>({id:'one',authorization_url:'https://evil.invalid/'}));await f.controller.click();
 assert.equal(f.link.hidden,true);assert.equal(f.opened.location.url,undefined);assert.equal(f.button.disabled,false);
 const button={},status={},link={};const c=create({button,status,link,start:async()=>({id:'safe',authorization_url:URL}),profile:()=> 'gaming',clientFile:()=>'',refresh:async()=>{},openWindow:()=>null,error:e=>e.message});
 await c.click();assert.equal(link.href,URL);assert.equal(link.hidden,false);assert.match(status.textContent,/Open Google/i);
});
