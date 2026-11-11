const profile=require('./profile.json');
const {rowWidth}=require('./widths.cjs');
const captionTokens=require('./tokens.cjs');
const stops=new Set(('a an the and or of to in at on for is it that with we you your our can but as if so be have has been are this these those i its my they them hai ka ki ke ko se aur hum tum apne ke liye ek bhi').split(' '));
const openEnds=new Set('a an the of to for with in at on and or but as ke ki ka ko se aur'.split(' '));
const normal=s=>String(s).toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
function timed(tokens,input,duration){
 if(input.words!==undefined){
  if(!Array.isArray(input.words)||input.words.length!==tokens.length)throw Error('Speech timings do not match this script. Correct the script or choose Script duration.');
  return input.words.map((w,i)=>{const start=Number(w.start),end=Number(w.end);if(normal(w.text)!==normal(tokens[i])||!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>duration+.02||(i&&start<Number(input.words[i-1].start)))throw Error('Speech timings do not match this script. Correct the script or choose Script duration.');return {source:tokens[i],start,end,...(w.review_reason?{review_reason:String(w.review_reason).slice(0,200)}:{}),...(w.alignment?{alignment:String(w.alignment).slice(0,40)}:{})};});
 }
 const weights=tokens.map(t=>Math.max(3,Math.min(12,t.length))),total=weights.reduce((a,b)=>a+b,0);let clock=0;
 return tokens.map((source,i)=>{const start=clock;clock=i===tokens.length-1?duration:clock+.04+(duration-.04*tokens.length)*weights[i]/total;return {source,start,end:clock};});
}
function count(words,offset,pattern){let n=Math.min(pattern==='inline'?3:pattern==='pair'?2:6,words.length-offset);const max=pattern==='inline'?28:45;while(n>Math.min(3,words.length-offset)&&words.slice(offset,offset+n).reduce((s,w)=>s+normal(w.source).length,0)>max)n--;for(let i=0;i<n;i++){if(i&&words[offset+i].start-words[offset+i-1].end>.6){n=i;break;}if(/[.!?]$/.test(words[offset+i].source)){n=i+1;break;}}if(pattern!=='inline'&&pattern!=='pair')while(n>3&&offset+n<words.length&&openEnds.has(normal(words[offset+n-1].source)))n--;if((pattern==='inline'||pattern==='pair')&&n>1){const hero=n===3?1:n-1;if(stops.has(normal(words[offset+hero].source))&&!stops.has(normal(words[offset].source)))n=1;}return n;}
function decorated(group,recipe,pattern,cursor=0){const words=[],n=group.length;
 for(const r of recipe.rows)for(const i of r.ids){const w=group[i],inlineHero=recipe.kind==='inline'&&i===(n===3?1:n-1),main=r.id==='main',mixed=pattern==='mixed'&&!main,big=main||inlineHero||(mixed&&!stops.has(normal(w.source))),functionWord=mixed&&stops.has(normal(w.source));words[i]={...w,index:cursor+i,slot:i,row:r.id,role:functionWord?'function':big?'main':'support',text:main&&recipe.kind==='stack'?w.source.toUpperCase():w.source.toLowerCase(),size:big?profile.main_size:profile.support_size,font:big?'bold':'support',gradient:main&&recipe.kind==='stack'&&pattern!=='stack_white',motion:big?{x:0,y:profile.motion.main_y,rotation:profile.motion.main_rotation,seconds:profile.motion.main_seconds,fade_seconds:profile.motion.fade_seconds}:{x:profile.motion.support_x,y:0,rotation:0,seconds:profile.motion.support_seconds,fade_seconds:profile.motion.fade_seconds}};}
 return words;
}
function fits(group,recipe,pattern){const words=decorated(group,recipe,pattern);return recipe.rows.every(r=>rowWidth(r.ids.map(i=>words[i]),profile)<=720*profile.safe_width_fraction);}
function stackRows(n,top,main){return {kind:'stack',rows:[{id:'top',ids:Array.from({length:top},(_,i)=>i)},{id:'main',ids:Array.from({length:main},(_,i)=>top+i)},{id:'bottom',ids:Array.from({length:n-top-main},(_,i)=>top+main+i)}]};}
function rowsFor(group,pattern){const n=group.length;
 if(n===1)return {kind:'solo',rows:[{id:'main',ids:[0]}]};
 if(pattern==='inline')return {kind:'inline',rows:[{id:'inline',ids:Array.from({length:n},(_,i)=>i)}]};
 if(pattern==='pair'||n===2)return {kind:'pair',rows:[{id:'top',ids:Array.from({length:n-1},(_,i)=>i)},{id:'main',ids:[n-1]}]};
 const defaultTop=pattern==='mixed'&&n>=5?2:1,defaultMain=pattern==='mixed'?1:Math.max(1,n-defaultTop-2);let top=defaultTop,main=defaultMain,best=-Infinity;
 for(let a=1;a<n-1;a++)for(let b=1;b<=Math.min(3,n-a-1);b++){const middle=group.slice(a,a+b),content=middle.filter(w=>!stops.has(normal(w.source))).reduce((v,w)=>v+normal(w.source).length,0);if(!content||!fits(group,stackRows(n,a,b),pattern))continue;const score=content-(pattern==='mixed'?5:1)*Math.abs(b-defaultMain)-.5*Math.abs(a-defaultTop);if(score>best){best=score;top=a;main=b;}}
 return stackRows(n,top,main);
}
function prepareWords(input={}){
 if(typeof input.script!=='string'||!input.script.trim()||input.script.length>6000||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(input.script))throw Error('Paste a script of up to 6,000 characters.');
 const tokens=captionTokens(input.script),duration=Number(input.duration);if(!tokens.length)throw Error('Paste spoken words, rather than punctuation alone.');if(tokens.length>1000||typeof input.duration==='boolean'||!Number.isFinite(duration)||duration<=0||duration>3600||tokens.length*.04>duration)throw Error('Choose enough caption time for this script (up to one hour).');
 const words=timed(tokens,input,duration);
 return {version:1,script:input.script.trim(),duration,timing_method:input.words?'speech':'script_duration',words};
}
function prepare(input={}){
 const intake=prepareWords(input),words=intake.words,duration=intake.duration,pages=[];let cursor=0;
 while(cursor<words.length){const pattern=profile.cycle[pages.length%profile.cycle.length];let minimum=1;while(cursor+minimum<words.length&&words[cursor+minimum].start===words[cursor].start)minimum++;if(minimum>(pattern==='inline'?3:6))throw Error('A long phrase shares one audio time. Review that script phrase against the recording before adding captions.');let n=Math.max(minimum,count(words,cursor,pattern)),group,recipe;do{while(n>minimum&&cursor+n<words.length&&words[cursor+n-1].start===words[cursor+n].start)n--;group=words.slice(cursor,cursor+n);recipe=rowsFor(group,pattern);if(fits(group,recipe,pattern)||n===minimum)break;n--;}while(n);
  const last=Math.min(duration,group[group.length-1].end),page={index:pages.length,pattern_id:pattern,kind:recipe.kind,start:group[0].start,end:last,source_start:cursor,word_gap_em:profile.word_gap_em,safe_width_fraction:profile.safe_width_fraction,rows:recipe.rows.map(r=>({id:r.id,words:r.ids})),words:decorated(group,recipe,pattern,cursor)};
  pages.push(page);cursor+=n;
 }
 for(let i=0;i<pages.length;i++){const next=pages[i+1];pages[i].end=Math.min(next?next.start:duration,input.words?pages[i].end+.12:duration);if(pages[i].end<=pages[i].start)throw Error('Caption timings need a positive duration for every group.');}
 return {version:1,style:profile.id,reference_sha256:profile.reference_sha256,script:input.script.trim(),duration,timing_method:input.words?'speech':'script_duration',pages};
}
module.exports={prepare,prepareWords,profile};
