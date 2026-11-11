const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const scope={};vm.createContext(scope);vm.runInContext(fs.readFileSync('tools/import_template_library_model.js','utf8'),scope);
const root='D:/Templates',project=root+'/Package/Main.aep',pick=(missing,files)=>scope.StorylensLibraryModel.mediaCandidate(missing,files,project,root);
test('moved assets resolve within their own package with spaces and case changes',()=>{
 assert.equal(pick('F:/Author/Assets/Texture 01.jpg',[root+'/Package/Assets/Texture 01.JPG']).path,root+'/Package/Assets/Texture 01.JPG');
});
test('same-named media in another template cannot silently fill the missing source',()=>{
 assert.equal(pick('F:/Author/1.jpg',[root+'/Other/1.jpg']).path,null);
});
test('matching folder suffix disambiguates duplicate names; ties stay unresolved',()=>{
 const files=[root+'/Package/Video/1.png',root+'/Package/Photos/1.png'];
 assert.equal(pick('F:/Author/Photos/1.png',files).path,files[1]);
 assert.equal(pick('F:/Author/1.png',files).path,null);
 assert.equal(pick('F:/Author/1.png',files).reason,'ambiguous');
});
