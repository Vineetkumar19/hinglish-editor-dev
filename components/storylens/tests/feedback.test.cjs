const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.style={};this.children=[]}append(...items){this.children.push(...items)}replaceChildren(...items){this.children=items}remove(){}setAttribute(){}}
const window={storylensErrorCatalog:JSON.parse(fs.readFileSync('hinglish_app/error_catalog.json','utf8'))},events={};
window.addEventListener=(name,fn)=>events[name]=fn;
const document={getElementById:()=>null,querySelector:()=>null,createElement:()=>new Element(),body:new Element()};
vm.runInNewContext(fs.readFileSync('hinglish_app/static/feedback.js','utf8'),{window,document,fetch:async()=>{throw TypeError('Failed to fetch')}});
test('HTML service failures become readable errors instead of JSON parser failures',async()=>{
 await assert.rejects(window.storylensResponse({status:500,ok:false,json:async()=>{throw SyntaxError('Unexpected token <')}}),e=>/could not finish/.test(e.message)&&/HTTP 500/.test(e.details));
});
test('same catalog preserves context overflow and publishing uncertainty',()=>{
 assert.equal(window.storylensProblem('HTTP 400 request exceeds the available context size').code,'model_context_full');
 assert.match(window.storylensProblem('request timed out').message,/may still be processing/);
 assert.doesNotMatch(window.storylensProblem('request timed out').message,/not uploaded/);
});
test('attachment errors keep backend diagnostics instead of a bare JSON error',async()=>{
 await assert.rejects(window.storylensXHR({status:400,responseText:JSON.stringify({error:'Select a supported video.',error_code:'request_failed',error_details:'format rejected'})}),e=>e.message==='Select a supported video.'&&e.details==='format rejected');
});
test('network failures have a reconnect message and code for the existing poller',async()=>{
 await assert.rejects(window.storylensFetch('/api/jobs/example'),e=>e.code==='local_connection'&&/Cannot reach Storylens/.test(e.message));
});
test('background-job diagnostics survive, and secrets are hidden in Details',()=>{
 const error=window.storylensJobError({error:'Beat analysis stopped. Select another file.',error_code:'file_missing',error_details:'No such file at /api?token=private-secret&item=one'});
 assert.equal(window.storylensProblem(error).code,'file_missing');
 assert.doesNotMatch(window.storylensProblem(error).details,/private-secret/);
 assert.match(window.storylensProblem(error).details,/item=one/);
});
test('unexpected interface errors show a readable alert without removing console diagnostics',()=>{
 events.unhandledrejection({reason:TypeError('cannot read properties of null')});
 const alert=document.body.children.at(-1);
 assert.equal(alert.id,'storylensUnexpectedError');
 assert.match(alert.children[0].textContent,/could not finish/);
});
test('server guidance and technical details survive transport separately',async()=>{
 await assert.rejects(window.storylensResponse({status:400,ok:false,json:async()=>({error:'Sign in to the selected account.',error_code:'sign_in_required',error_details:'raw detail'})}),e=>e.message==='Sign in to the selected account.'&&e.details==='raw detail'&&e.code==='sign_in_required');
 assert.match(window.storylensError(Error('Failed to fetch')),/Cannot reach Storylens/);
});
