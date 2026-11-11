const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function page(){
 const navigations=[],buttons=[];
 const document={documentElement:{dataset:{token:'unit'}},dispatchEvent(){},createElement(){return{setAttribute(){},append(){}};}};
 const window={location:{assign:url=>navigations.push(url)},storylensEditorLogo:()=>'',storylensIcon:()=>''};
 vm.runInNewContext(fs.readFileSync('hinglish_app/static/editor-handoff.js','utf8'),{document,window,Event:function(){},URL,console,setTimeout});
 return {window,navigations,buttons,container:{querySelectorAll:()=>[],append:b=>buttons.push(b)}};
}
test('main B-roll result offers three destinations and opens review before any import',()=>{
 const p=page();p.window.storylensEditors.render(p.container,{folder:'D:\\Full Drive\\remove silence\\output\\broll\\job\\bank'});
 assert.equal(p.buttons.length,3);
 assert.match(p.buttons[1].innerHTML,/After Effects/);
 p.buttons[1].onclick();assert.equal(p.navigations[0],'/broll-output/job/bank/report.html?editor=aftereffects');
});
test('unrelated caption destinations are retained and invalid B-roll paths do not navigate',()=>{
 const p=page();p.window.storylensEditors.render(p.container,{folder:'D:\\project\\output\\captions\\saved'});assert.equal(p.buttons.length,2);
 const bad=page();bad.window.storylensEditors.render(bad.container,{folder:'D:\\project\\output\\broll\\..\\outside'});
 assert.equal(bad.buttons.length,3);assert.throws(()=>bad.buttons[0].onclick(),/review/);assert.equal(bad.navigations.length,0);
});
test('After Effects has its own Ae icon',()=>{
 const window={},document={addEventListener(){}};
 vm.runInNewContext(fs.readFileSync('hinglish_app/static/icons.js','utf8'),{window,document});
 assert.match(window.storylensEditorLogo('aftereffects'),/>Ae</);
});
test('multi-video B-roll results keep their actual index page',()=>{
 const p=page();p.window.storylensEditors.render(p.container,{folder:'D:\\project\\output\\broll\\batch',page:'D:\\project\\output\\broll\\batch\\index.html'});
 p.buttons[0].onclick();assert.equal(p.navigations[0],'/broll-output/batch/index.html?editor=premiere');
});
