const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');

// Native Photo Collector must scroll its whole grid inside the fixed-height
// iframe. The main web editor retains its existing parent-resize workflow.
function embed(search,photoFlow){
 const styles=[],messages=[];let observers=0;
 const parent={postMessage:value=>messages.push(value)},document={
  documentElement:{dataset:{photoFlow},classList:{add(){}}},
  createElement:()=>({textContent:''}),head:{append:style=>styles.push(style)},
  querySelector:()=>({getBoundingClientRect:()=>({height:1900})})
 };
 const window={parent,addEventListener(){}};
 vm.runInNewContext(fs.readFileSync('hinglish_app/static/embedded-tool.js','utf8'),{
  URLSearchParams,location:{search,origin:'http://127.0.0.1:8765'},window,parent,document,
  ResizeObserver:class{constructor(){observers++;}observe(){}}
 });
 return {css:styles.map(style=>style.textContent).join(''),messages,observers};
}
test('native photos allow the full grid to scroll rather than clipping at iframe height',()=>{
 const value=embed('?embedded=1&panel=1','selective');
 assert.match(value.css,/html\.embedded-tool\{overflow-x:hidden;overflow-y:auto/);
 assert.match(value.css,/html\.embedded-tool body\{overflow:visible/);
 assert.equal(value.observers,1);assert.equal(value.messages[0].height,1928);
});
test('main web embedding retains parent height updates',()=>{
 const value=embed('?embedded=1','selective');
 assert.equal(value.observers,1);
 assert.equal(value.messages[0].height,1928);
});
