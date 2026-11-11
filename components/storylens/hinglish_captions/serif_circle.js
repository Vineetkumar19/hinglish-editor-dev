// Second reference draft: short captions, italic emphasis, drawn annotations.
(()=>{
 const cfg=project.serif_circle_profile;if(!cfg)return;
 // Saved reports may embed revision 3 while the shared service is still running.
 // Upgrade this style in memory as well; the saved profile remains on disk.
 if((cfg.revision||0)<4){
  const green=[[[203,123],[300,174],[520,174],[552,125]],[[552,125],[584,79],[447,41],[313,37]],[[313,37],[188,29],[152,64],[200,92]],[[200,92],[238,119],[340,142],[426,142]]],red=[[[200,205],[310,258],[565,219],[590,118]],[[590,118],[625,5],[445,-15],[265,21]],[[265,21],[125,45],[100,108],[160,152]],[[160,152],[200,189],[320,211],[450,184]]],underline=[[[205,166],[310,160],[520,158],[520,166]],[[520,166],[512,178],[265,190],[250,198]],[[250,198],[240,207],[433,211],[427,224]]];
  for(const [from,to] of [[12,0],[14,2],[15,3],[16,5],[18,6]]){
   const fallback=to===0?{kind:'circle',trigger:3,path:green,color:'#21E890',stroke:4}:to===2||to===5?{kind:'scribble',trigger:2,path:to===5?underline.map(s=>s.map(([x,y])=>[x,y-15])):underline,color:to===5?'#21E890':'#FFFFFF',stroke:2.5,glow:true,taper:true}:{kind:'circle',trigger:to===6?2:0,path:to===6?red.map(s=>s.map(([x,y])=>[360+(x-360)*.82,y+8])):red,color:'#F00031',stroke:to===6?5:6};
   cfg.recipes[to].decorations=JSON.parse(JSON.stringify(cfg.recipes[from]?.decorations||[{...fallback,y:0}]));if(to===0)cfg.recipes[to].decorations[0].trigger=3;if(to===6)cfg.recipes[to].decorations[0].trigger=2;
  }
  const bands={0:[0,1,2,3],5:[0,0,1,2],6:[0,0,1,2],11:[0,0],16:[0,0,1,2],18:[0,0,1,2]},targets={0:[2,3],2:[2,3],3:[0,1,2],5:[2,3],6:[0,1,2,3],12:[2,3],14:[2,3],15:[0,1,2],16:[2,3],18:[0,1,2,3]};
  cfg.recipes.forEach((r,i)=>{r.reference_pattern=i<12;r.rows.forEach((row,j)=>Object.assign(row,{source_row:j,band:bands[i]?.[j]??j,reveal:'row',role:row.face==='serif'?'emphasis':'support'}));for(const d of r.decorations||[]){d.target_rows=targets[i];d.linear=true;d.duration=d.kind==='circle'&&[0,12].includes(i)?.45:.60;d.delay=d.kind==='circle'?([0,12].includes(i)?0:.20):.10;if(d.kind!=='circle')d.taper=true}});
  cfg.recipes[4].rows[1].band=0;cfg.revision=4;
 }
 for(const index of [3,15])for(const row of cfg.recipes[index]?.rows||[])row.case='upper';
 templates.serif_circle_draft.default_position=.65;
 const recipeCache=new Map();
 const oldDraw=draw,canvas=document.createElement('canvas'),ctx=canvas.getContext('2d'),glowCanvas=document.createElement('canvas'),glowCtx=glowCanvas.getContext('2d');
 canvas.style.cssText='display:block;width:100%;height:auto';canvas.setAttribute('role','img');
 const norm=text=>text.toLowerCase().split(/\s+/).map(w=>w.replace(/[^\p{L}\p{N}]/gu,'')).join(' ');
 function recipeFor(words){
  if(!words.length)return null;
  const active=cues.find(q=>q.start<=video.currentTime&&video.currentTime<q.end),original=norm(active?.template_source||''),key=norm(words.join(' '));
  const cacheKey=JSON.stringify([words,original,active?.template_slot,$('#font').value]);if(recipeCache.has(cacheKey))return recipeCache.get(cacheKey);
  const saved=(!original||original===key)?cfg.recipes.find(r=>norm(r.text)===key):null;
  const candidates=cfg.recipes.filter(r=>r.reference_pattern||norm(r.text)===original);
  const result=fitNewWords(saved?JSON.parse(JSON.stringify(saved)):storylensTemplatePattern(words,candidates.length?candidates:cfg.recipes),words);if(recipeCache.size>=128)recipeCache.clear();recipeCache.set(cacheKey,result);return result;
 }

 function fitNewWords(plan,words){
  const original=cfg.recipes.find(r=>r.text===(plan.template_pattern||plan.text)),oldWords=original.text.split(/\s+/),oldRows=original.rows;
  const emphasis=oldRows.find(r=>r.face==='serif');
  if(emphasis&&!plan.rows.some(r=>r.face==='serif')){const focus=Math.min(words.length-1,Math.floor((emphasis.words[0]+.5)*words.length/oldWords.length));plan.rows=plan.rows.flatMap(row=>{row.words=row.words.filter(i=>i!==focus);return row.words.length?[row]:[]});plan.rows.push({...JSON.parse(JSON.stringify(emphasis)),words:[focus]});plan.rows.sort((a,b)=>a.source_row-b.source_row)}
  if(original.replace_words){plan.replace_words=true;plan.rows=words.map((_,i)=>{const j=Math.min(oldRows.length-1,Math.floor((i+.5)*oldRows.length/words.length));return {...oldRows[j],words:[i],reveal:'word'}})}
  const rowCaps=oldRows.map(()=>600);
  for(const spec of original.decorations||[]){if(spec.kind!=='circle')continue;const ids=spec.target_rows,old=union(ids.map(i=>rowBounds(oldRows[i],oldWords))),xy=points(spec,1),span=Math.max(...xy.map(p=>p[0]))-Math.min(...xy.map(p=>p[0])),cap=Math.max(160,Math.min(600,590*(old[2]-old[0]+24)/Math.max(1,span)-24));for(const i of ids)rowCaps[i]=Math.min(rowCaps[i],cap)}
  for(const row of plan.rows){row.source_row??=oldRows.findIndex(r=>r.y===row.y&&(r.x??360)===(row.x??360));row.band??=oldRows[row.source_row].band??row.source_row;const b=rowBounds(row,words);row.size=(row.size||cfg.size)*Math.min(1,rowCaps[row.source_row]/Math.max(1,b[2]-b[0]))}
  let previous=null,previousSource=null;
  for(const band of [...new Set(plan.rows.map(r=>r.band))].sort((a,b)=>a-b)){
   const rows=plan.rows.filter(r=>r.band===band),source=oldRows.filter(r=>(r.band??r.source_row)===band),desired=union(rows.map(r=>rowBounds(r,words)));let right=null;
   for(const row of [...rows].sort((a,b)=>(a.x??360)-(b.x??360))){const b=rowBounds(row,words);if(right!==null&&!plan.replace_words)row.x=(row.x??360)+Math.max(0,right+8-b[0]);right=rowBounds(row,words)[2]}
   let packed=union(rows.map(r=>rowBounds(r,words)));const shift=(desired[0]+desired[2]-packed[0]-packed[2])/2;
   for(const row of rows)row.x=(row.x??360)+shift;
   packed=union(rows.map(r=>rowBounds(r,words)));const fit=Math.min(1,600/Math.max(1,packed[2]-packed[0])),center=(packed[0]+packed[2])/2;
   for(const row of rows){row.x=center+(row.x-center)*fit;row.size*=fit}
   const box=union(rows.map(r=>rowBounds(r,words))),sourceBox=union(source.map(r=>rowBounds(r,oldWords)));
   if(previous){const gap=Math.max(3,Math.min(8,sourceBox[1]-previousSource[3])),dy=previous[3]+gap-box[1];for(const row of rows)row.y+=dy}
   previous=union(rows.map(r=>rowBounds(r,words)));previousSource=sourceBox;
  }
  for(const [index,spec] of (plan.decorations||[]).entries()){
   const oldSpec=original.decorations[index],ids=oldSpec.target_rows||oldRows.map((_,i)=>i);let targets=plan.rows.filter(r=>ids.includes(r.source_row));
   if(!targets.length)targets=[plan.rows.reduce((a,b)=>Math.min(...ids.map(i=>Math.abs(b.source_row-i)))<Math.min(...ids.map(i=>Math.abs(a.source_row-i)))?b:a)];
   const old=union(ids.map(i=>rowBounds(oldRows[i],oldWords))),next=union(targets.map(r=>rowBounds(r,words))),sx=(next[2]-next[0]+24)/Math.max(1,old[2]-old[0]+24),sy=spec.kind==='circle'?(next[3]-next[1]+16)/Math.max(1,old[3]-old[1]+16):1;
   const point=(x,y)=>[(next[0]+next[2])/2+(x-(old[0]+old[2])/2)*sx,spec.kind==='circle'?(next[1]+next[3])/2+(y-(old[1]+old[3])/2)*sy:next[3]+y-old[3]];
   spec.path=oldSpec.path.map(seg=>seg.map(([x,y])=>point(x,y+(oldSpec.y||0))));spec.y=0;
  }
  const boxes=plan.rows.map(r=>rowBounds(r,words));
  for(const spec of plan.decorations||[]){const xy=points(spec,1),pad=(spec.stroke||3)/2+(spec.glow?6:0);boxes.push([Math.min(...xy.map(p=>p[0]))-pad,Math.min(...xy.map(p=>p[1]))-pad,Math.max(...xy.map(p=>p[0]))+pad,Math.max(...xy.map(p=>p[1]))+pad])}
  const box=union(boxes),dx=360-(box[0]+box[2])/2,dy=-(box[1]+box[3])/2;
  for(const row of plan.rows){row.x=(row.x??360)+dx;row.y+=dy}
  for(const spec of plan.decorations||[])spec.path=spec.path.map(seg=>seg.map(([x,y])=>[x+dx,y+dy]));
  plan.bounds=[box[0]+dx,box[1]+dy,box[2]+dx,box[3]+dy];return plan;
 }
 const union=boxes=>[Math.min(...boxes.map(b=>b[0])),Math.min(...boxes.map(b=>b[1])),Math.max(...boxes.map(b=>b[2])),Math.max(...boxes.map(b=>b[3]))];
 function ink(text,face,size,tracking){setFont(face,size);return union([...text].map((c,j)=>{const m=ctx.measureText(c),x=ctx.measureText(text.slice(0,j)).width+j*size*tracking;return [x-m.actualBoundingBoxLeft,-m.actualBoundingBoxAscent,x+m.actualBoundingBoxRight,m.actualBoundingBoxDescent]}))}
 function rowGeometry(row,words){const size=row.size||cfg.size,face=row.face||'sans',tracking=row.tracking??cfg.tracking,items=[];let cursor=0;for(const i of row.words){const text=row.case==='upper'?words[i].toUpperCase():words[i],b=ink(text,face,size,tracking);items.push({index:i,x:cursor,box:b});cursor+=measure(text,face,size,tracking)+size*.2}return {items,box:union(items.map(r=>[r.x+r.box[0],r.box[1],r.x+r.box[2],r.box[3]]))}}
 function rowBounds(row,words){const b=rowGeometry(row,words).box,x=row.x??360,y=row.y;return [x-(b[2]-b[0])/2,y-(b[3]-b[1])/2,x+(b[2]-b[0])/2,y+(b[3]-b[1])/2]}
 function setFont(face,size){
  const chosen=$('#font').value;
  ctx.font=chosen!=='template'?`400 ${size}px ${fonts[chosen].css}`:face==='serif'?`700 ${size}px "Circle Serif"`:face==='italic'?`600 ${size}px "Circle Italic"`:`600 ${size}px "Circle Sans"`;
 }
 function measure(text,face,size,tracking){setFont(face,size);return ctx.measureText(text).width+Math.max(0,text.length-1)*size*tracking}
 function plan(words,recipe){
  recipe||=recipeFor(words);const rows=recipe?.rows||[{words:words.map((_,i)=>i),y:0}],runs=[];
  for(const row of rows){const face=row.face||'sans',size=row.size||cfg.size,tracking=row.tracking??cfg.tracking,ids=row.words,{items,box}=rowGeometry(row,words),left=(row.x??360)-(box[0]+box[2])/2,baseline=row.y-(box[1]+box[3])/2;
   for(const {index:i,x,box:b} of items)runs.push({index:i,text:row.case==='upper'?words[i].toUpperCase():words[i],x:left+x+(b[0]+b[2])/2,y:baseline+(b[1]+b[3])/2,origin_x:left+x,baseline,size,face,tracking,color:row.color||'#FFFFFF',reveal_with:row.reveal==='row'?ids[0]:i,motion:recipe?.motion||'cut'});
  }return runs.sort((a,b)=>a.index-b.index);
 }
 function points(spec,progress){const result=[];
  if(spec.path){const path=[];for(const seg of spec.path){for(let i=0;i<=60;i++){const t=i/60;path.push([0,1].map(d=>(1-t)**3*seg[0][d]+3*(1-t)**2*t*seg[1][d]+3*(1-t)*t*t*seg[2][d]+t**3*seg[3][d]+(d===1?(spec.y||0):0)))}}
   const lengths=[0];for(let i=1;i<path.length;i++)lengths.push(lengths[i-1]+Math.hypot(path[i][0]-path[i-1][0],path[i][1]-path[i-1][1]));
   const cutoff=lengths[lengths.length-1]*progress;result.push(path[0]);for(let i=1;i<path.length;i++){if(lengths[i]<=cutoff){result.push(path[i]);continue}const f=(cutoff-lengths[i-1])/Math.max(.00001,lengths[i]-lengths[i-1]);result.push([0,1].map(d=>path[i-1][d]+f*(path[i][d]-path[i-1][d])));break}return result;
  }
  const source=cfg.recipes.flatMap(r=>r.decorations||[]).find(d=>d.kind===spec.kind&&d.path);return points(source,progress);
 }
 draw=function(){oldDraw();if(currentStyle!=='serif_circle_draft'||visibility==='spoken')return;
  const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end);if(index<0){caption.replaceChildren();return}
  const q=cues[index],all=wordsAt(index),W=1280,H=Math.round(W*stage.clientHeight/stage.clientWidth),limit=H>=W?4:7;
  let a=0,b=all.length;for(let i=0;i<all.length;){const remain=all.length-i,n=remain>limit&&remain-limit===1?limit-1:Math.min(limit,remain),j=i+n;if((i?q.words[i].start:q.start)<=now){a=i;b=j}i=j}
  if(limit===4&&all.length===7&&recipeFor(all)){a=now<q.words[3].start?0:3;b=a===0?3:7}
  canvas.width=W;canvas.height=H;
  const local=all.slice(a,b);let recipe=recipeFor(local),runs=plan(local,recipe).map(r=>({...r,index:r.index+a,reveal_with:r.reveal_with+a}));
  recipe={...recipe,decorations:(recipe.decorations||[]).map(d=>({...d,trigger:d.trigger+a}))};const yshift=0;
  // Studio applies saved drag/size transforms outside this canvas. Standalone
  // reports use the controls directly. In both cases the complete layout is fixed.
  const studio=typeof cueLayouts!=='undefined',position=studio?templates[currentStyle].default_position:Number($('#position').value)/100,size=studio?1:Number($('#size').value)/100,box=recipe.bounds;
  const ratio=Math.min(Math.min(W/720,H/720)*size,W*.84/Math.max(1,box[2]-box[0]),H*Math.max(.01,position-.04)/Math.max(1,-box[1]+24),H*Math.max(.01,.96-position)/Math.max(1,box[3]+56));
  for(const r of runs){const age=now-q.words[Math.max(a,r.reveal_with)].start;if(age<0||(visibility==='styled_spoken'&&!(q.words[r.index].start<=now&&now<q.words[r.index].end)))continue;
   const p=Math.max(0,Math.min(1,age/.23)),ease=1-(1-p)**3,fade=Math.max(0,Math.min(1,age/.14)),alpha=r.motion==='cut'?1:fade*fade*(3-2*fade),rise=r.motion==='cut'?0:46*(1-ease),blur=r.motion==='cut'?0:7.5*(1-p)**2;
   setFont(r.face,r.size*ratio);
   if(recipe?.replace_words&&!(q.words[r.index].start<=now&&now<q.words[r.index].end))continue;
   const actual=ink(r.text,r.face,r.size*ratio,r.tracking),x=W/2+(r.x-360)*ratio-(actual[0]+actual[2])/2,y=H*position+(r.baseline+rise)*ratio;
   ctx.save();ctx.globalAlpha=alpha;ctx.filter=`blur(${blur*ratio}px)`;ctx.fillStyle=wordColors[index]?.[r.index]||r.color;
   for(let j=0;j<r.text.length;j++){ctx.fillText(r.text[j],x+ctx.measureText(r.text.slice(0,j)).width+j*r.size*ratio*r.tracking,y)}ctx.restore();
  }
  for(const source of recipe?.decorations||[]){if(source.trigger<a||source.trigger>=b)continue;const age=now-q.words[source.trigger].start-(source.delay||0);if(age<=0)continue;
   const raw=Math.min(1,age/(source.duration||.65)),p=source.linear?raw:1-(1-raw)**2,spec={...source,y:source.y-yshift};let xy=points(spec,p).map(([x,y])=>[W/2+(x-360)*ratio,H*position+y*ratio]);
   ctx.save();ctx.strokeStyle=source.color;ctx.fillStyle=source.color;ctx.lineWidth=(source.stroke||3)*ratio;ctx.lineCap='round';ctx.lineJoin='round';
   if(source.taper){const left=[],right=[];xy.forEach(([x,y],i)=>{const a=xy[Math.max(0,i-1)],b=xy[Math.min(xy.length-1,i+1)],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.max(.001,Math.hypot(dx,dy)),t=p*i/Math.max(1,xy.length-1),half=ctx.lineWidth*(.12+.88*Math.sin(Math.PI*t)**.6)/2;left.push([x-dy/length*half,y+dx/length*half]);right.push([x+dy/length*half,y-dx/length*half])});xy=left.concat(right.reverse())}
   const paint=target=>{target.beginPath();xy.forEach(([x,y],j)=>target[j?'lineTo':'moveTo'](x,y));if(source.taper){target.closePath();target.fill()}else target.stroke()};
   if(source.glow){
    if(glowCanvas.width!==W||glowCanvas.height!==H){glowCanvas.width=W;glowCanvas.height=H}else glowCtx.clearRect(0,0,W,H);
    glowCtx.strokeStyle=source.color;glowCtx.fillStyle=source.color;glowCtx.lineWidth=ctx.lineWidth;glowCtx.lineCap='round';glowCtx.lineJoin='round';paint(glowCtx);
    ctx.save();ctx.filter=`blur(${6*ratio}px)`;ctx.globalAlpha=.55;ctx.drawImage(glowCanvas,0,0);ctx.restore();
   }
   paint(ctx);ctx.restore();
  }
  canvas.setAttribute('aria-label',runs.filter(r=>now>=q.words[Math.max(a,r.reveal_with)].start&&(!recipe?.replace_words||now<q.words[r.index].end)).map(r=>r.text).join(' '));caption.replaceChildren(canvas);caption.className='serif-circle-caption';
  Object.assign(caption.style,{left:'0',right:'0',top:'50%',width:'100%',maxWidth:'none',transform:'translateY(-50%)',padding:'0',background:'transparent',opacity:'1',filter:'none',visibility:'visible'});updateSelection();
 };
 Promise.all([document.fonts.load('600 56px "Circle Sans"'),document.fonts.load('700 88px "Circle Serif"'),document.fonts.load('600 56px "Circle Italic"')]).then(()=>{recipeCache.clear();draw()});
 video.addEventListener('seeked',draw);video.addEventListener('pause',draw);
})();
