const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const file='tools/import_template_library_model.js';
function load(){const c={};vm.createContext(c);vm.runInContext(fs.readFileSync(file,'utf8'),c);return c.StorylensLibraryModel;}
test('only project files below the approved source root enter the import list',()=>{const m=load(),rows=m.plan([{path:'D:/Templates/one.aep'},{path:'D:/Templates/two.aet'},{path:'D:/Templates/../outside.aep'},{path:'D:/Templates2/x.aep'},{path:'D:/Templates/help.pdf'}],'D:/Templates');assert.equal(rows.length,2)});
test('same-name genuine variants stay separate and exact paths are idempotent',()=>{const m=load(),a={path:'D:/Templates/A/History.aep'},b={path:'D:/Templates/B/History.aep'},rows=m.plan([a,b,a],'D:/Templates');assert.equal(rows.length,2);assert.equal(m.pending(rows,[m.marker(a.path)]).length,1)});
test('safe source identity tolerates Windows separators and case without evaluating names',()=>{const m=load();assert.equal(m.marker('D:\\Templates\\Movie.aep'),m.marker('d:/templates/movie.aep'));const rows=m.plan([{path:'D:/Templates/\";evil();.aep'}],'D:/Templates');assert.equal(rows.length,1);assert.match(rows[0].path,/evil/)});
test('one version per package prefers main over precomp and newest explicit year',()=>{const m=load(),rows=m.plan([{path:'D:/Templates/One/Main (Precomp).aep'},{path:'D:/Templates/One/Main.aep'},{path:'D:/Templates/Two/History CC 2015.aep'},{path:'D:/Templates/Two/History CC 2023.aep'}],'D:/Templates');assert.equal(rows.length,2);assert.equal(rows[0].path,'D:/Templates/One/Main.aep');assert.match(rows[1].path,/2023/)});

function rows(n){return Array.from({length:n},(_,i)=>({path:'D:/Templates/Package'+i+'/Main.aep',folder:'Package'+i}));}
test('shuffled batches never exceed twenty and contain unique packages',()=>{const m=load(),r=rows(61),a=m.batch(r,[],[],()=>.37);assert.equal(a.length,20);assert.equal(new Set(a.map(x=>x.path)).size,20);assert.notEqual(a[0].path,r[0].path);assert.equal(m.batch(rows(3),[],[],()=>.2).length,3)});
test('rotation prioritizes unseen packages and fresh discoveries',()=>{const m=load(),r=rows(40),first=m.batch(r,[],[],()=>.5),second=m.batch(r,[],first.map(x=>m.marker(x.path)),()=>.5);assert.equal(second.length,20);assert.equal(second.some(x=>first.some(y=>y.path===x.path)),false);const newRow={path:'D:/Templates/New/Main.aep'};assert.equal(m.batch([newRow,...r],[],r.map(x=>m.marker(x.path)),()=>0)[0].path,newRow.path)});
test('an imported package is skipped even when its preferred version changes',()=>{const m=load(),r=rows(2);const comments=[m.marker(r[0].path)+'\n'+m.packageMarker(r[0].path,'D:/Templates')];const changed=[{path:'D:/Templates/Package0/Main CC 2026.aep'},r[1]];assert.equal(m.batch(changed,comments,[],()=>0,'D:/Templates').length,1)});
test('legacy source tags and CRLF comments prevent repeat imports',()=>{const m=load(),r=rows(2);assert.equal(m.batch(r,[m.marker(r[0].path)+'\r\nold note'],[],()=>0,'D:/Templates').length,1)});

test('compact rotation history keeps older batches behind new packages',()=>{const m=load(),r=rows(40),first=m.batch(r,[],[],()=>.5),next=m.batch(r,[],first.map(x=>m.historyKey(x.path)),()=>.5);assert.equal(next.some(x=>first.some(y=>y.path===x.path)),false)});

// Owner requested that final break findings be reported without fixing them.
test('review: reserved object-key package is omitted by the current planner',()=>{const m=load();assert.equal(m.plan([{path:'D:/Templates/__proto__/Main.aep'}],'D:/Templates').length,0)});
