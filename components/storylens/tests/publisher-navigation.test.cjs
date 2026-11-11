const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function href(message){
  const source=fs.readFileSync('hinglish_app/static/assistant.js','utf8');
  const code=source.split('// publisher-navigation-start')[1]?.split('// publisher-navigation-end')[0];
  assert.ok(code,'Publisher navigation helper must be present');
  const context={URLSearchParams};vm.createContext(context);vm.runInContext(code+';this.href=publisherHref;',context);
  return context.href(message);
}
test('Cricket handoff retains only its own exact draft IDs',()=>{
  const url=new URL(href({publisher_profile:'cricket',publish_ids:['draft-one','draft-two']}),'http://local/');
  assert.equal(url.pathname,'/prepare-post.html');assert.equal(url.searchParams.get('profile'),'cricket');assert.equal(url.searchParams.get('drafts'),'draft-one,draft-two');
});
test('ordinary publisher links stay generic; untrusted profile and IDs cannot change origin',()=>{
  assert.equal(href({}),'prepare-post.html');
  const url=new URL(href({publisher_profile:'https://bad.example',publish_ids:['<bad>']}),'http://local/');
  assert.equal(url.origin,'http://local');assert.equal(url.searchParams.get('profile'),null);assert.equal(url.searchParams.get('drafts'),null);
});
