
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {visibleComments,commentPostDate,commentContext}=require('../editor_plugins/storylens-chrome/dom-checks.js');

function fixture({account='fantasy_legends91', owner='fantasy_legends91', href='/reel/EXACT/?comment_id=123', nested=false, pathname='/reel/EXACT/', modal=true, plainPermalink=false, emptyLabel=null}={}){
  const visible=()=>[{}];
  const sidebar={getClientRects:visible,closest:()=>null,querySelectorAll:()=>[],
    getAttribute:name=>name==='href'?'/'+account+'/':'Your profile picture'};
  const outer={};
  const parent={closest:()=>nested?outer:null};
  const author={getClientRects:visible,closest:()=>row,innerText:'viewer',getAttribute:()=>'/viewer/'};
  const text={getClientRects:visible,closest:selector=>selector.startsWith('li')?row:null,innerText:'How did this happen?'};
  const date={getAttribute:()=> '2026-11-07T12:00:00Z'};
  const row={parentElement:parent,querySelectorAll:selector=>selector==='a[href]'?[author]:[text]};
  const link={getClientRects:visible,closest:selector=>selector==='header'?null:row,getAttribute:()=>href,querySelector:()=>date};
  const post={getClientRects:visible,closest:()=>null,
    getAttribute:()=>plainPermalink?'/reel/EXACT/':'/'+owner+'/reel/EXACT/'};
  const authorHeader={getClientRects:visible,closest:selector=>selector==='header'?{closest:()=>article}:null,getAttribute:()=>'/'+owner+'/'};
  const heading={getClientRects:visible,innerText:'The exact post'};
  const article={getClientRects:visible,closest:selector=>modal||selector.includes('main')?{}:null,contains:node=>node===row||node===outer,
    querySelectorAll:selector=>selector==='a[href]'?(plainPermalink?[post,link,authorHeader]:[post,link]):
      selector==='a[href*="comment_id="]'?(emptyLabel===null?[link]:[]):
      selector==='span,p,h2,h3'?[{getClientRects:visible,closest:()=>null,innerText:emptyLabel||''}]:[heading]};
  const document={querySelectorAll:selector=>selector==='a[href]'?[sidebar]:selector==='[role="dialog"] article'&&!modal?[]:[article]};
  return {document,location:{origin:'https://www.instagram.com',pathname}};
}

test('visible comment needs exact signed-in profile, owned post, comment ID and author',()=>{
  const {document,location}=fixture();
  assert.deepEqual(visibleComments(document,location,'fantasy_legends91'),{account:'fantasy_legends91',rows:[{
    source_id:'EXACT',source_url:'https://www.instagram.com/fantasy_legends91/reel/EXACT/',
    comment_id:'123',author_id:'viewer',text:'How did this happen?',published_at:'2026-11-07T12:00:00.000Z',
    source_title:'The exact post',source_description:'The exact post',own:false,
  }]});
});

test('rejects mismatched account or post, nested replies and unsafe or ambiguous IDs',()=>{
  for(const options of [
    {account:'vineet_editz19'}, {owner:'vineet_editz19'}, {nested:true},
    {href:'/reel/OTHER/?comment_id=123'}, {href:'/reel/EXACT/?comment_id=123&comment_id=456'},
    {href:'/reel/EXACT/?comment_id=123&reply_comment_id=456'},
    {href:'https://example.org/reel/EXACT/?comment_id=123'},
  ]){
    const {document,location}=fixture(options);
    assert.throws(()=>visibleComments(document,location,'fantasy_legends91'));
  }
});


test('a profile modal must independently expose one exact owned post',()=>{
  for(const pathname of ['/fantasy_legends91/','/reel/EXACT']){
    const {document,location}=fixture({pathname});
    assert.equal(visibleComments(document,location,'fantasy_legends91').rows[0].source_id,'EXACT');
  }
  const {document,location}=fixture({pathname:'/fantasy_legends91/',modal:false});
  assert.throws(()=>visibleComments(document,location,'fantasy_legends91'),/could not verify the open post/);
});


test('an unprefixed post permalink needs an independently matching post author',()=>{
  const match=fixture({plainPermalink:true,pathname:'/p/EXACT/'});
  assert.equal(visibleComments(match.document,match.location,'fantasy_legends91').rows[0].source_id,'EXACT');
  const other=fixture({plainPermalink:true,owner:'vineet_editz19'});
  assert.throws(()=>visibleComments(other.document,other.location,'fantasy_legends91'),/could not verify the open post/);
});


test('article-less full-page reels require the exact permalink and independent author',()=>{
  const account='fantasy_legends91';
  const visible=()=>[{}];
  const side={getClientRects:visible,closest:()=>null,querySelectorAll:()=>[],
    getAttribute:name=>name==='href'?'/'+account+'/':'Your profile picture'};
  let owner=account;
  const author={getClientRects:visible,closest:()=>null,getAttribute:()=>'/'+owner+'/',
    querySelector:()=>({alt:owner+"'s profile picture"})};
  const post={getClientRects:visible,closest:()=>null,getAttribute:()=>'/reel/EXACT/'};
  const surface={getClientRects:visible,contains:()=>false,querySelectorAll:()=>[author,post]};
  const document={querySelectorAll:selector=>selector==='a[href]'?[side]:
    selector.startsWith('article')?[]:[surface]};
  const location={pathname:'/reels/EXACT/'};
  assert.equal(commentContext(document,location,account).sourceId,'EXACT');
  owner='someone_else';
  assert.throws(()=>commentContext(document,location,account),/could not verify/);
});

test('publication time belongs to the exact post rather than a recent comment',()=>{
  const location={origin:'https://www.instagram.com'};
  const time=(href,stamp)=>({getClientRects:()=>[{}],getAttribute:()=>stamp,
    closest:selector=>selector==='a[href]'?{getAttribute:()=>href}:null});
  const comment=time('/p/EXACT/?comment_id=1','2020-01-03T12:00:00Z');
  const published=time('/p/EXACT/','2020-01-01T12:00:00Z');
  const other=time('/p/OTHER/','2020-01-02T12:00:00Z');
  const context={sourceId:'EXACT',kind:'reel',article:{querySelectorAll:()=>[published,comment,other]}};
  assert.equal(commentPostDate(context,location,'fantasy_legends91').source_published_at,'2020-01-01T12:00:00.000Z');
  context.article.querySelectorAll=()=>[comment,other];
  assert.throws(()=>commentPostDate(context,location,'fantasy_legends91'),/exact publication date/);
});

test('an empty result requires a visible empty state on the verified post',()=>{
  const empty=fixture({emptyLabel:'No comments yet.'});
  assert.deepEqual(visibleComments(empty.document,empty.location,'fantasy_legends91'),{
    account:'fantasy_legends91',rows:[],empty_source:'https://www.instagram.com/fantasy_legends91/reel/EXACT/',
  });
  const loading=fixture({emptyLabel:''});
  assert.throws(()=>visibleComments(loading.document,loading.location,'fantasy_legends91'),/Open the comments panel/);
});
