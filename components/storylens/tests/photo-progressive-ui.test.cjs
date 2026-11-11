const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function model(){const c={};vm.createContext(c);vm.runInContext(fs.readFileSync('hinglish_app/static/photos-progressive.js','utf8'),c);return c.PhotoProgressive;}
test('confirmed smaller originals are automatically saved, not screenshot crops',()=>{const m=model();assert.equal(m.ready({status:'preview',width:296,height:170}),false);assert.equal(m.ready({status:'ready',width:640,height:420}),true);assert.equal(m.ready({status:'ready',width:1920,height:1080,effective_width:1920,effective_height:1080}),true)});
test('saved rows are not downloaded again and collection keys stay separate',()=>{const m=model(),a={id:'aaa',photos:[{id:1,status:'ready',width:1600,height:900},{id:2,status:'ready',width:1600,height:900,download_file:'Image 1.jpg'}]};assert.equal(m.waiting(a,new Set()).length,1);assert.equal(m.waiting(a,new Set(['aaa:1'])).length,0);assert.equal(m.waiting({...a,id:'bbb'},new Set(['aaa:1'])).length,1)});
test('native receipts prevent duplicate progressive transfers after panel reload',()=>{const m=model(),job={native_receipts:{aftereffects:{imported:[{photo_id:1}],upgraded:[{photo_id:2}],already_present:[{photo_id:3}]}}};assert.equal(m.delivered(job,'aftereffects').size,3)});

test('source switches cannot reuse another screenshot pending keys',()=>{const m=model();assert.notEqual(m.key('first',1),m.key('second',1));const pending=new Set([m.key('first',1)]);const second={id:'second',photos:[{id:1,status:'ready',width:1920,height:1080}]};assert.equal(m.waiting(second,pending).length,1)});

// Source-switch integration contract: prepare the service-state preflight even
// if localStorage/initial UI restore has not completed. Owner runs live checks.
test('screenshot switch consults photo-service history before a new start',()=>{const source=fs.readFileSync('hinglish_app/static/photos.js','utf8');assert.match(source,/async function clearActivePhotoSearches/);assert.match(source,/await clearActivePhotoSearches\(\);/);assert.match(source,/await stopPrevious\(value.id\)/)});
