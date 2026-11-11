const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const html=fs.readFileSync('hinglish_app/static/publisher.html','utf8'),css=fs.readFileSync('hinglish_app/static/publisher.css','utf8');
test('all three disclosures share a header contract and retain their content',()=>{
 for(const id of ['preparationHistory','publishingQueue','creatorMemory']){
  const tag=html.match(new RegExp('<details[^>]*id="'+id+'"[^>]*>'))?.[0];
  assert.match(tag,/learning-memory/);assert.doesNotMatch(tag,/\bhidden\b/);
 }
 for(const id of ['tasks','queue','memoryList'])assert.ok(html.includes('id="'+id+'"'));
});
test('common disclosure headers have matching grid, padding and minimum height',()=>{
 assert.match(css,/\.publishing-page \.learning-memory\{padding:0\}/);
 assert.match(css,/\.publishing-page \.learning-memory>summary\{[^}]*display:grid[^}]*grid-template-columns:20px minmax\(0,1fr\) auto[^}]*min-height:48px[^}]*padding:12px 20px/);
 assert.match(css,/\.publishing-page \.learning-memory>summary>small\{[^}]*justify-self:end/);
});
