const {test}=require('node:test');
const assert=require('node:assert/strict');
const {checked,composerAccount,videoInput,newTopReel,publishedCaption,accountSwitchRow}=require('../editor_plugins/storylens-chrome/dom-checks.js');
const {sameControl,emptyComposer}=require('../editor_plugins/storylens-chrome/dom-checks.js');
test('file selection labels tolerate casing and whitespace without matching unrelated controls',()=>{
 assert.equal(sameControl('Select from computer','Select From Computer'),true);
 assert.equal(sameControl(' SELECT  FROM\nCOMPUTER ','Select from computer'),true);
 assert.equal(sameControl('Select profile photo','Select from computer'),false);
});
test('only an empty composer can be cleaned up automatically',()=>{
 const d=({files=[],media=[],captions=[]}={})=>({querySelectorAll:s=>s==='input[type="file"]'?files:s==='video,img[src^="blob:"]'?media:captions});
 assert.equal(emptyComposer(d()),true);
 assert.equal(emptyComposer(d({files:[{files:[{}]}]})),false);
 assert.equal(emptyComposer(d({media:[{}]})),false);
 assert.equal(emptyComposer(d({captions:[{innerText:'My draft'}]})),false);
 assert.equal(emptyComposer(null),false);
});
test('distinguishes an unloaded switch from a real off state, then recognizes original audio',()=>{
 assert.equal(checked(null),null);
 assert.equal(checked({getAttribute:()=>null}),null);
 assert.equal(checked({type:'checkbox',checked:true,getAttribute:()=>null}),true);
 assert.equal(checked({type:'checkbox',checked:false,getAttribute:()=>null}),false);
 assert.equal(checked({getAttribute:()=> 'true'}),true);
});
test('selects only the video input inside the composer, excluding profile photo inputs',()=>{
 const photo={getAttribute:()=> 'image/jpeg'};
 const photo2={getAttribute:()=> 'image/jpeg,image/png'};
 const video={getAttribute:()=> 'image/avif,image/jpeg,image/png,image/heic,image/heif,video/mp4,video/quicktime'};
 assert.equal(videoInput({querySelectorAll:()=>[photo,photo2,video]}),video);
 assert.equal(videoInput({querySelectorAll:()=>[photo,photo2]}),null);
 assert.equal(videoInput(null),null);
});
test('real composer SPAN role=link with avatar verifies the account without an anchor href',()=>{
 const identity=account=>({getAttribute:()=>null,querySelector:()=>({alt:account+"'s profile picture"})});
 assert.equal(composerAccount({querySelectorAll:()=>[identity('vineet_editz19')]},'vineet_editz19'),true);
 assert.equal(composerAccount({querySelectorAll:()=>[identity('other_account')]},'vineet_editz19'),false);
 assert.equal(composerAccount({querySelectorAll:()=>[]},'vineet_editz19'),false);
});

test('lazy-loaded older posts never become a new publication receipt',()=>{
 const link=id=>({getAttribute:()=>'/vineet_editz19/reel/'+id+'/'});
 const old=link('OLD'),lazy=link('OLDER'),fresh=link('NEW');
 const prior=new Set([old.getAttribute('href')]);
 assert.equal(newTopReel({querySelectorAll:()=>[old,lazy]},'vineet_editz19',prior),null);
 assert.equal(newTopReel({querySelectorAll:()=>[fresh,old,lazy]},'vineet_editz19',prior),fresh);
});

test('post-publication grid outside main still locates only a new top entry',()=>{
 const link=id=>({getAttribute:()=>'/fantasy_legends91/reel/'+id+'/'});
 const old=link('OLD'),fresh=link('NEW');
 const profile=links=>({querySelectorAll:selector=>selector==='a[href]'?links:[]});
 const prior=new Set([old.getAttribute('href')]);
 assert.equal(newTopReel(profile([fresh,old]),'fantasy_legends91',prior),fresh);
 assert.equal(newTopReel(profile([old,fresh]),'fantasy_legends91',prior),null);
});

test('publication requires the actual posted caption and exact permalink',()=>{
 const href='/vineet_editz19/reel/NEW/';
 const article=(text,url=href)=>({querySelectorAll:s=>s==='a[href]'?[{getAttribute:()=>url}]:[{innerText:text}]});
 assert.equal(publishedCaption(article(''),href,'Cricket #IPL'),false);
 assert.equal(publishedCaption(article('Cricket #IPL','/vineet_editz19/reel/OLD/'),href,'Cricket #IPL'),false);
 assert.equal(publishedCaption(article('Cricket\n#IPL'),href,'Cricket #IPL'),true);
});

test('existing-post verification requires matching account caption and upload time window',()=>{
 const {existingPublication}=require('../editor_plugins/storylens-chrome/dom-checks.js');
 const after=Date.parse('2026-10-20T14:17:00Z')/1000,before=after+300;
 const article=(account='vineet_editz19',caption='Cricket #IPL',when='2026-10-20T14:18:04Z')=>({
  querySelectorAll:s=>s==='a[href]'?[{getAttribute:()=>`/${account}/reel/NEW/`}]:
   s==='time[datetime]'?[{getAttribute:()=>when}]:[{innerText:caption}]
 });
 assert.equal(existingPublication(article(),'vineet_editz19','Cricket #IPL',after,before).caption_verified,true);
 assert.equal(existingPublication(article('other'),'vineet_editz19','Cricket #IPL',after,before),null);
 assert.equal(existingPublication(article(undefined,'Other'),'vineet_editz19','Cricket #IPL',after,before),null);
 assert.equal(existingPublication(article(undefined,undefined,'2026-10-19T14:18:04Z'),'vineet_editz19','Cricket #IPL',after,before),null);
});

test('account switch prefers the exact username and permits only one email-labelled alternative',()=>{
 const row=text=>({innerText:text,getClientRects:()=>[{}],querySelector:()=>({}),querySelectorAll:()=>[{textContent:text}]});
 const email=row('creator@example.invalid'),exact=row('fantasy_legends91'),other=row('other@example.invalid');
 const dialog=rows=>({querySelectorAll:()=>rows});
 assert.equal(accountSwitchRow(dialog([email]),'fantasy_legends91'),email);
 assert.equal(accountSwitchRow(dialog([email,exact]),'fantasy_legends91'),exact);
 assert.equal(accountSwitchRow(dialog([email,other]),'fantasy_legends91'),null);
});

test('the real saved-login row can lack an avatar without being mistaken for a missing account',()=>{
 const row=text=>({innerText:text,getClientRects:()=>[{}],querySelector:()=>null,querySelectorAll:()=>[{textContent:text}]});
 const saved=row('creator@example.invalid'),other=row('other@example.invalid');
 const dialog=rows=>({querySelectorAll:()=>rows});
 assert.equal(accountSwitchRow(dialog([saved]),'fantasy_legends91'),saved);
 assert.equal(accountSwitchRow(dialog([saved]),'fantasy_legends91',['creator@example.invalid']),saved);
 assert.equal(accountSwitchRow(dialog([saved,other]),'fantasy_legends91'),null);
 assert.equal(accountSwitchRow(dialog([saved]),'fantasy_legends91',['different@example.invalid']),null);
});

test('caption-free receipt requires the correct account permalink, no caption, and posting window',()=>{
 const {existingPublication}=require('../editor_plugins/storylens-chrome/dom-checks.js');
 const start=Date.parse('2026-10-20T15:00:00Z')/1000;
 const article=(caption='',account='fantasy_legends91',when='2026-10-20T15:00:10Z')=>({
  querySelectorAll:s=>s==='a[href]'?[{getAttribute:()=>`/${account}/reel/NEW/`}]:
   s==='time[datetime]'?[{getAttribute:()=>when}]:caption?[{innerText:caption}]:[]
 });
 assert.ok(existingPublication(article(),'fantasy_legends91','',start,start+120));
 assert.equal(existingPublication(article('Unexpected caption'),'fantasy_legends91','',start,start+120),null);
 assert.equal(existingPublication(article('','other'),'fantasy_legends91','',start,start+120),null);
 assert.equal(existingPublication(article('','fantasy_legends91','2026-10-19T15:00:10Z'),'fantasy_legends91','',start,start+120),null);
});

test('receipt recovery opens only one exact-caption link on the requested account',()=>{
 const {matchingReel}=require('../editor_plugins/storylens-chrome/dom-checks.js');
 const link=(account,caption)=>({getAttribute:()=>`/${account}/reel/NEW/`,querySelectorAll:()=>[{alt:caption}]});
 const target=link('fantasy_legends91','Saha 115 #Cricket'),other=link('vineet_editz19','Saha 115 #Cricket');
 const doc=links=>({querySelectorAll:()=>links});
 assert.equal(matchingReel(doc([other,target]),'fantasy_legends91','Saha 115 #Cricket'),target);
 assert.equal(matchingReel(doc([target]),'fantasy_legends91','Different caption'),null);
 assert.equal(matchingReel(doc([target,link('fantasy_legends91','Saha 115 #Cricket')]),'fantasy_legends91','Saha 115 #Cricket'),null);
});
