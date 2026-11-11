const assert=require('assert/strict'),{test}=require('node:test'),model=require('../editor_plugins/caption-patterns/model.cjs');
test('punctuation alone cannot create a silent caption generation',()=>assert.throws(()=>model.prepare({script:'— …',duration:3}),/spoken|words/i));
test('standalone punctuation stays attached to caption words and never needs its own audio onset',()=>{
 const script='Next episode — Rapido ka scam.',words=['Next','episode —','Rapido','ka','scam.'].map((text,i)=>({text,start:i*.4,end:i*.4+.3}));
 const plan=model.prepare({script,words,duration:4});assert.equal(plan.pages.flatMap(p=>p.words).length,5);assert.equal(plan.pages.flatMap(p=>p.words.map(w=>w.source)).join(' '),script);
});
test('shared phrase onsets stay on the same slide instead of creating invisible final words',()=>{
 const script='Bright smart ideas help new people grow today clearly',words=script.split(' ').map((text,i)=>({text,start:i===6?1.5:i*.3,end:(i===6?1.5:i*.3)+.25}));
 const p=model.prepare({script,words,duration:4});assert(p.pages.every(p=>p.words.every(w=>w.start<p.end)));for(let i=0;i<p.pages.length-1;i++)assert(p.pages[i].words.at(-1).start<p.pages[i+1].words[0].start);
});
test('acoustic review metadata survives the native caption plan',()=>{
 const words=['Review','these','words'].map((text,i)=>({text,start:i,end:i+.4,alignment:'acoustic_word',...(i===1?{review_reason:'Low-confidence wording'}:{})}));
 const p=model.prepare({script:'Review these words',words,duration:4});assert.equal(p.pages.flatMap(p=>p.words)[1].review_reason,'Low-confidence wording');
});
