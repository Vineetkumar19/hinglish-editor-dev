// First reference draft: measured gold emphasis, white support, word entrances.
(()=>{
 let cfg=project.kinetic_gold_profile;if(!cfg)return;
 let profileLoading=null;
 const originalDraw=draw,canvas=document.createElement('canvas'),pen=canvas.getContext('2d');
 canvas.style.cssText='display:block;width:100%;height:auto';canvas.setAttribute('role','img');
 const normalize=text=>text.toLowerCase().split(/\s+/).map(w=>w.replace(/[^\p{L}\p{N}]/gu,'')).join(' ');
 function fontFor(file,points){
  const chosen=$('#font').value;
  if(chosen!=='template')return `400 ${points}px ${fonts[chosen].css}`;
  return file.includes('Barlow')?`600 ${points}px "Barlow Condensed"`:file.includes('RobotoCondensed')?`700 ${points}px "Roboto Condensed"`:file==='Inter-Bold.otf'?`700 ${points}px "Inter Caption 1"`:`${file==='arial.ttf'?400:700} ${points}px Arial`;
 }
 function measure(text,file,size){pen.font=fontFor(file,size);return pen.measureText(text).width}
 function recipeFor(words){
  if(!words.length)return null;
  const active=cues.find(q=>q.start<=video.currentTime&&video.currentTime<q.end),key=normalize(words.join(' ')),original=normalize(active?.template_source||'');
  const saved=cfg.recipes.find(r=>normalize(r.text)===(original||key))||(active?.template_slot>=0?cfg.recipes[active.template_slot%cfg.recipes.length]:cfg.recipes.reduce((a,b)=>Math.abs(b.text.split(/\s+/).length-words.length)<Math.abs(a.text.split(/\s+/).length-words.length)?b:a));
  return {...saved,adapted:normalize(saved.text)!==key};
 }
 function ink(text,file,size){pen.font=fontFor(file,size);const m=pen.measureText(text);return [m.actualBoundingBoxLeft+m.actualBoundingBoxRight,m.actualBoundingBoxAscent+m.actualBoundingBoxDescent]}
 function bounds(runs){return [Math.min(...runs.map(r=>r.x-r.width/2)),Math.min(...runs.map(r=>r.y-r.height/2)),Math.max(...runs.map(r=>r.x+r.width/2)),Math.max(...runs.map(r=>r.y+r.height/2))]}
 function plan(words,portrait,sourceWords=null,offset=0){
  if(!words.length)return [];
  const recipe=recipeFor(sourceWords||words),old=recipe.text.split(/\s+/),slots=recipe.runs,n=words.length,m=old.length;
  const mapping=words.map((_,i)=>Math.min(m-1,Math.floor((i+.5)*m/n))),mains=slots.flatMap((r,i)=>r.role==='main'?[i]:[]);
  if(mains.length&&!mapping.some(j=>mains.includes(j))){const hero=mains[0],nearest=mapping.reduce((a,j,i)=>Math.abs(j-hero)<Math.abs(mapping[a]-hero)?i:a,0);mapping[nearest]=hero}
  const exact=normalize(words.join(' '))===normalize(recipe.text),runs=mapping.map((j,i)=>{
   const r={...slots[j],text:words[i],index:i,source_index:j};
   if(!exact){const [ow,oh]=ink(old[j],r.font,r.size),[nw,nh]=ink(words[i],r.font,r.size);r.width*=nw/Math.max(1,ow);r.height*=nh/Math.max(1,oh)}
   return r;
  });
  if(!exact){
   const rows=[...new Set(runs.map(r=>r.row))].sort((a,b)=>a-b);
   for(const row of rows){
    const band=runs.filter(r=>r.row===row),source=slots.filter(r=>r.row===row),box=bounds(source),center=(box[0]+box[2])/2,gaps=[];
    const sourceIds=slots.flatMap((r,i)=>r.row===row?[i]:[]),sourceGaps=source.slice(1).map((b,i)=>Math.max(8,b.x-b.width/2-source[i].x-source[i].width/2)).sort((a,b)=>a-b),middle=Math.floor(sourceGaps.length/2),typicalGap=sourceGaps.length?(sourceGaps.length%2?sourceGaps[middle]:(sourceGaps[middle-1]+sourceGaps[middle])/2):8;
    for(let k=0;k<band.length-1;k++){const left=band[k],right=band[k+1],a=slots[left.source_index],b=slots[right.source_index],gap=b.x-b.width/2-a.x-a.width/2,skipped=sourceIds.indexOf(right.source_index)-sourceIds.indexOf(left.source_index)>1;gaps.push(skipped?typicalGap:left.source_index!==right.source_index?Math.max(8,gap):8)}
    const span=band.reduce((sum,r)=>sum+r.width,0)+gaps.reduce((a,b)=>a+b,0),fit=Math.min(1,650/Math.max(1,span));let cursor=center-span*fit/2;
    band.forEach((r,k)=>{r.size*=fit;r.width*=fit;r.height*=fit;r.x=cursor+r.width/2;cursor+=r.width+(gaps[k]||0)*fit});
   }
   const done=[];
   for(const row of rows){const band=runs.filter(r=>r.row===row);let dy=0;
    for(const r of band)for(const previous of done)if(Math.min(r.x+r.width/2,previous.x+previous.width/2)>Math.max(r.x-r.width/2,previous.x-previous.width/2))dy=Math.max(dy,previous.y+previous.height/2+4-(r.y-r.height/2));
    for(const r of band)r.y+=dy;done.push(...band);
   }
  }
  const [left,top,right,bottom]=bounds(runs),dx=368-(left+right)/2,dy=207-(top+bottom)/2;
  for(const r of runs){r.x+=dx;r.y+=dy}return runs;
 }

 draw=function(){
  originalDraw();if(currentStyle!=='kinetic_gold_draft')return;
  if(cfg.revision<6||cfg.recipes.some(r=>!r.runs?.every(s=>s.width&&s.height&&s.row!==undefined))){
   if(!profileLoading)profileLoading=(window.storylensFetch||fetch)('/kinetic-gold-profile.json',{cache:'no-store'}).then(response=>window.storylensResponse?window.storylensResponse(response):response.json()).then(fresh=>{
    if(fresh.revision<6)throw Error('The saved caption style needs to be refreshed. Reopen Kinetic Gold from Storylens.');
    cfg=fresh;project.kinetic_gold_profile=fresh;Object.assign(templates.kinetic_gold_draft,{default_position:fresh.anchor?.y??.65,max_words:fresh.max_page_words});draw();
   }).catch(error=>{$('#status').textContent=window.storylensError?window.storylensError(error):'The caption style could not load. Refresh Storylens and reopen Kinetic Gold.'});
   return;
  }
  $$('.ratios button').forEach(button=>button.textContent=button.dataset.format==='youtube_horizontal'?'16:9':button.dataset.format==='square'?'1:1':'9:16');
  if(visibility==='spoken')return;
  const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end);
  if(index<0){caption.replaceChildren();return}
  const q=cues[index],all=wordsAt(index),W=1280,H=Math.round(W*stage.clientHeight/stage.clientWidth),portrait=H>=W,limit=cfg.max_page_words||9;
  if(!all.length){caption.replaceChildren();return}
  const times=all.map((_,i)=>q.words?.length===all.length?q.words[i]:{start:q.start+(q.end-q.start)*i/all.length,end:q.start+(q.end-q.start)*(i+1)/all.length});
  let a=0,b=all.length;
  for(let i=0;i<all.length;){const remaining=all.length-i,n=remaining>limit&&remaining-limit===1?limit-1:Math.min(limit,remaining),j=i+n;if((i?times[i].start:q.start)<=now){a=i;b=j}i=j}
  const start=a?times[a].start:q.start,end=b<all.length?times[b].start:q.end;
  canvas.width=W;canvas.height=H;
  const runs=plan(all.slice(a,b),portrait,all,a),camera=1+cfg.camera_zoom*Math.min(1,Math.max(0,(now-start)/(end-start)));
  // The studio's position layer applies saved per-cue x/y and size once.
  let ratio=Math.min(W/736,H/414)*(portrait?1.15:1);
  if(runs.length){const extent=Math.max(...runs.map(r=>Math.abs(r.x-368)+(r.width??measure(r.text,r.font||(r.role==='main'?cfg.main_font:cfg.support_font),r.size))/2+(r.motion==='right'?50:0)));ratio=Math.min(ratio,W*.90/Math.max(1,extent*2*(1+cfg.camera_zoom)))}
  pen.save();pen.translate(W/2,H/2);pen.scale(camera,camera);pen.translate(-W/2,-H/2);
  for(const r of runs){
   const i=a+r.index,word=times[i],age=now-word.start-(r.delay||0);
   if(age<0||(visibility==='styled_spoken'&&now>=word.end))continue;
   const p=Math.min(1,age/(r.duration||cfg.entrance_seconds)),ease=1-(1-p)**3,file=r.font||(r.role==='main'?cfg.main_font:cfg.support_font),kind=r.motion||'rise';
   const alpha=['cut','drop','right'].includes(kind)?1:ease,dx=kind==='right'?50*(1-ease):0,dy=kind==='drop'?(r.rise??-32)*(1-ease):kind==='rise'?(r.rise??18)*(1-ease):0,scale=kind==='grow'?.70+.30*ease:1;
   const wordRatio=r.echo?ratio*Math.min(1,W*.90/((r.width*1.18+24)*ratio)):ratio;
   pen.font=fontFor(file,r.size*wordRatio);const m=pen.measureText(r.text),ink=m.actualBoundingBoxLeft+m.actualBoundingBoxRight,sx=(r.width?r.width*wordRatio/ink:1)*scale,sy=(r.height?r.height*wordRatio/(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent):1)*scale;
   const x=W/2+(r.x-368+dx)*ratio,y=H/2+(r.y-207+dy)*ratio;
   const left=(m.actualBoundingBoxLeft-m.actualBoundingBoxRight)/2,baseline=(m.actualBoundingBoxAscent-m.actualBoundingBoxDescent)/2;
   pen.fillStyle=wordColors[index]?.[i]||(r.role==='main'?cfg.accent:'#FFFFFF');
   if(r.echo){
    const progress=Math.max(0,Math.min(1,age/.95)),settle=1-(1-progress)**3,fade=Math.max(0,Math.min(1,age/(r.echo_fade_seconds??.30)));
    const maximum=Math.min(1.42,(W*.90-24*wordRatio)/(r.width*wordRatio)),echoScale=maximum-.12*settle;
    pen.save();pen.translate(x+(-12+22*settle)*wordRatio,y+(5-10*settle)*wordRatio);
    pen.scale(sx/Math.max(scale,.001)*echoScale,sy/Math.max(scale,.001)*echoScale);pen.globalAlpha=(r.echo_opacity??.18)*fade*fade*(3-2*fade);if(r.echo_color)pen.fillStyle=r.echo_color;
    if(r.outline_echo){pen.strokeStyle=pen.fillStyle;pen.lineWidth=1.2*wordRatio;pen.strokeText(r.text,left,baseline)}else pen.fillText(r.text,left,baseline);pen.restore();
   }
   pen.save();pen.translate(x,y);pen.scale(sx,sy);pen.globalAlpha=alpha;
   if(r.typewriter){pen.beginPath();pen.rect(left,-H,m.width*Math.min(1,age/r.typewriter),H*2);pen.clip()}
   pen.fillText(r.text,left,baseline);pen.restore();
  }
  let recipe=recipeFor(all);if(recipe?.adapted){recipe=recipeFor(all.slice(a,b));const main=runs.find(r=>r.role==='main');if(main)recipe={...recipe,hero:main.index+a}};
  if(recipe?.underline&&recipe.hero>=a&&recipe.hero<b){
   const progress=Math.max(0,Math.min(1,(now-times[recipe.hero].start)/.48)),reveal=1-(1-progress)**3;
   if(reveal){const upper=[],lower=[],[x0,y0,x1,y1,thickness]=recipe.underline_path||[296,258,575,220,6];for(let k=0;k<=64;k++){const t=reveal*k/64,x=x0+(x1-x0)*t,y=y0+(y1-y0)*t-4*Math.sin(Math.PI*t),half=thickness*Math.sin(Math.PI*t)**.72;upper.push([x,y-half]);lower.push([x,y+half])}
    let points=upper.concat(lower.reverse());
    if(runs.length){const [left,top,right,bottom]=bounds(runs),[oldLeft,oldTop,oldRight,oldBottom]=bounds(recipe.runs),sx=(right-left)/Math.max(1,oldRight-oldLeft),sy=(bottom-top)/Math.max(1,oldBottom-oldTop);points=points.map(([x,y])=>[(left+right)/2+(x-(oldLeft+oldRight)/2)*sx,bottom+(y-oldBottom)*sy])}
    pen.beginPath();points.forEach(([x,y],j)=>pen[j?'lineTo':'moveTo'](W/2+(x-368)*ratio,H/2+(y-207)*ratio));pen.closePath();pen.fillStyle=recipe.underline;pen.fill();
   }
  }
  pen.restore();canvas.setAttribute('aria-label',all.slice(a,b).filter((_,i)=>now>=times[a+i].start).join(' '));
  caption.replaceChildren(canvas);caption.className='kinetic-gold-caption';
  Object.assign(caption.style,{left:'0',right:'0',top:(templates[currentStyle].default_position*100)+'%',width:'100%',maxWidth:'none',transform:'translateY(-50%)',padding:'0',background:'transparent',opacity:'1',filter:'none',visibility:'visible'});updateSelection();
 };
 Promise.all([document.fonts.load('600 100px "Barlow Condensed"'),document.fonts.load('700 32px "Roboto Condensed"'),document.fonts.load('700 32px "Inter Caption 1"')]).then(()=>draw());
 video.addEventListener('seeked',draw);video.addEventListener('pause',draw);
})();
