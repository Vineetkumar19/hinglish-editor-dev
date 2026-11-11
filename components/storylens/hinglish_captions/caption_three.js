// Caption 3 uses the same compositions and continuous focus clocks as export.
(() => {
  const config=project.caption_three_profile;if(!config)return;
  const normalize=text=>String(text).toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]/gu,'');
  const phraseKey=text=>String(text).split(/\s+/).map(normalize).join(' ');
  function activeContext(){return typeof cues!=='undefined'&&typeof video!=='undefined'?cues.find(q=>q.start<=video.currentTime&&video.currentTime<q.end)||{}:{}}
  function planFor(words,context=null){
    if(!words.length)return {rows:[],motion:'in'};
    if(!context||typeof context!=='object')context=activeContext();
    const recipes=[...config.recipes,...(config.continuations||[])],key=words.map(normalize).join(' '),original=context.template_source||'';
    const changed=original&&phraseKey(original)!==key,known=changed?null:recipes.find(r=>phraseKey(r.text)===key);if(known)return known;
    const saved=recipes.find(r=>original&&phraseKey(r.text)===phraseKey(original)),candidates=saved?[saved]:config.recipes,target=original?original.split(/\s+/):words;
    const source=saved||(context.template_slot>=0?candidates[context.template_slot%candidates.length]:candidates.reduce((a,b)=>Math.abs(b.text.split(/\s+/).length-target.length)<Math.abs(a.text.split(/\s+/).length-target.length)?b:a));
    const old=source.text.split(/\s+/),mapping=words.map((_,i)=>Math.min(old.length-1,Math.floor((i+.5)*old.length/words.length))),main=source.rows.find(r=>r.role==='main');
    if(main&&!mapping.some(j=>main.words.includes(j))){const hero=main.words[0],nearest=mapping.reduce((best,v,i)=>Math.abs(v-hero)<Math.abs(mapping[best]-hero)?i:best,0);mapping[nearest]=hero}
    const out=JSON.parse(JSON.stringify(source));for(const key of ['start','end','starts','sample_beats','display','hero_frame','replace_words'])delete out[key];
    Object.assign(out,{text:words.join(' '),template_pattern:source.text,adapted:true});
    out.rows=source.rows.flatMap(row=>{const ids=mapping.flatMap((j,i)=>row.words.includes(j)?[i]:[]);if(!ids.length)return [];const r={...JSON.parse(JSON.stringify(row)),words:ids};delete r.frame;return [r]});return out;
  }
  function smooth(value){const p=Math.max(0,Math.min(1,value));return p*p*p*(p*(p*6-15)+10)}
  function motionState(age,remaining,available=1,main=false,exitSeconds=.12){
    const m=config.motion,duration=Math.min(m.focus_seconds,Math.max(.06,available*.60)),p=smooth(age/duration),fade=smooth(age/Math.min(m.fade_seconds,Math.max(.045,available*.28))),leave=smooth(remaining/Math.max(.015,exitSeconds));
    return [fade*leave,m.blur*(1-p)+m.exit_blur*(1-leave),(main?m.main_rise:m.support_rise)*(1-p)];
  }
  function cameraState(age,mode='in'){const m=config.motion,p=smooth(age/m.camera_seconds);return [1+m.camera_zoom*(mode==='in'?p:1-p),m.camera_drift*p]}
  function transitionState(remaining,mode='focus'){const p=smooth(1-remaining/config.motion.transition_seconds);return [mode==='slide_left'?-500*p:0,mode==='slide_up'?-380*p:0]}
  function splitRanges(words,context=null){
    if(!words.length)return [];
    context=context||activeContext();const origin=context.template_source||words.join(' ');let spread=(config.legacy_spreads||[]).find(s=>phraseKey(s.text)===phraseKey(origin));
    if(!spread&&![...config.recipes,...(config.continuations||[])].some(r=>phraseKey(r.text)===phraseKey(origin))){const selected=planFor(words,context);spread=(config.legacy_spreads||[]).find(s=>selected.template_pattern===s.page_sources[0])}
    if(spread){
      const n=words.length,weights=spread.page_word_weights,split=n>1?Math.max(1,Math.min(n-1,Math.floor(n*weights[0]/(weights[0]+weights[1])+.5))):n;
      return [{start:0,count:split},{start:split,count:n-split}].flatMap((group,i)=>group.count?splitRanges(words.slice(group.start,group.start+group.count),{template_source:spread.page_sources[i],template_slot:context.template_slot}).map(page=>({...page,start:page.start+group.start})):[]);
    }
    const plan=planFor(words,context),maximum=plan.adapted?(plan.page_words??config.max_words):words.length,ranges=[];let start=0;
    while(start<words.length){let count=Math.min(maximum,words.length-start);if(words.length-start-count===1&&count>2)count--;ranges.push({start,count,template_source:context.template_source||words.join(' '),template_slot:context.template_slot??-1});start+=count}return ranges;
  }
  function arrowPoints(){
    const points=[];
    for(const [a,b,c,d] of [[[0,0],[10,35],[31,39],[28,12]],[[28,12],[24,-11],[-27,0],[-12,19]],[[-12,19],[9,36],[49,11],[21,52]],[[21,52],[13,62],[4,69],[-4,76]]])for(let i=0;i<40;i++){const t=i/40,u=1-t;points.push([u*u*u*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t*t*t*d[0],u*u*u*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t*t*t*d[1]])}
    return [...points,[-4,76],[2,59],[-4,76],[13,70]];
  }
  const canvas=document.createElement('canvas');canvas.width=720;canvas.style.cssText='display:block;width:100%;height:auto;margin:0';canvas.setAttribute('role','img');
  const pen=canvas.getContext('2d'),measure=document.createElement('canvas').getContext('2d'),baseDraw=draw,assets=new Map(),layouts=new Map();
  function inkOutline(line){
    const extent=Math.max(...line.runs.map(r=>r.size))*2,mask=document.createElement('canvas');mask.width=Math.max(1,Math.trunc(line.width+8));mask.height=extent*2;
    const gp=mask.getContext('2d',{willReadFrequently:true});gp.textBaseline='alphabetic';gp.fillStyle='#000';
    for(const run of line.runs){gp.font=run.css;[...run.text].forEach((c,j)=>gp.fillText(c,run.x-line.left+3+gp.measureText(run.text.slice(0,j)).width+j*run.size*run.tracking,extent))}
    const pixels=gp.getImageData(0,0,mask.width,mask.height).data,top=Array(mask.width).fill(Infinity),bottom=Array(mask.width).fill(-Infinity);
    for(let y=0;y<mask.height;y++)for(let x=0;x<mask.width;x++)if(pixels[(y*mask.width+x)*4+3]>48){top[x]=Math.min(top[x],y-extent);bottom[x]=y-extent}
    return {offset:line.left-3,top,bottom};
  }
  function baselineDistance(above,below,gap){
    const a=above.outline??=inkOutline(above),b=below.outline??=inkOutline(below),shift=below.x+b.offset-above.x-a.offset;let optical=-Infinity;
    b.top.forEach((top,i)=>{const j=Math.floor(i+shift+.5);if(j>=0&&j<a.bottom.length&&Number.isFinite(top)&&Number.isFinite(a.bottom[j]))optical=Math.max(optical,a.bottom[j]-top)});
    if(!Number.isFinite(optical))optical=above.bottom-below.top;
    const cap=above.bottom-below.top-Math.max(...below.runs.map(r=>r.size))*.18;return Math.max(optical,cap)+gap;
  }
  function layoutFor(words,W,frameHeight,chosen,context){
    const plan=planFor(words,context),unit=Math.min(W,frameHeight*.75),ratio=unit/720,limit=unit*config.safe_width/(1+config.motion.camera_zoom),lines=[];
    const custom=fonts[chosen],customWeight=/(bd|uib|b)\.ttf$/i.test(custom?.file||'')?700:400;
    for(const row of plan.rows){
      const kind=row.font_override??row.font??'support';
      const family=chosen!=='template'?custom.css:kind==='playful'?'"Caption Three Playful",cursive':kind==='blue'?'Arial,sans-serif':'"Caption Three Serif",serif';
      const style=chosen==='template'&&kind==='blue'?'italic':'normal',weight=chosen==='template'?(row.weight??400):customWeight,tracking=row.font==='main'?config.tracking:config.support_tracking;
      function measureRow(size){
        const css=`${style} ${weight} ${size}px ${family}`;measure.font=css;const runs=[];let cursor=0;
        for(const i of row.words){
          const text=words[i];let left=Infinity,right=-Infinity,top=0,bottom=0;
          [...text].forEach((c,j)=>{if(/\s/u.test(c))return;const p=measure.measureText(text.slice(0,j)).width+j*size*tracking,m=measure.measureText(c);left=Math.min(left,p-m.actualBoundingBoxLeft);right=Math.max(right,p+m.actualBoundingBoxRight);top=Math.min(top,-m.actualBoundingBoxAscent);bottom=Math.max(bottom,m.actualBoundingBoxDescent)});
          const advance=measure.measureText(text).width+Math.max(0,text.length-1)*size*tracking;
          runs.push({i,text,size,css,tracking,x:cursor,left,right,top,bottom});cursor+=advance+size*config.space;
        }
        const left=Math.min(...runs.map(r=>r.x+r.left)),right=Math.max(...runs.map(r=>r.x+r.right));return {runs,left,width:right-left};
      }
      let size=Math.max(2,Math.round(row.size*ratio)),line=measureRow(size);
      while(line.width>limit&&size>2){size=Math.max(2,Math.min(size-1,Math.floor(size*limit/line.width)));line=measureRow(size)}
      const room=Math.max(0,(limit-line.width)/2),offset=Math.max(-room,Math.min(room,(row.offset??0)*ratio));
      lines.push({...line,row,top:Math.min(...line.runs.map(r=>r.top)),bottom:Math.max(...line.runs.map(r=>r.bottom)),x:offset-line.width/2-line.left});
    }
    let cursor=0;
    lines.forEach((line,n)=>{if(!n)line.y=-line.top;else if(line.row.gap_before)line.y=lines[n-1].y+lines[n-1].bottom+Math.max(config.readable_line_gap,line.row.gap_before)*ratio-line.top;else line.y=lines[n-1].y+baselineDistance(lines[n-1],line,config.readable_line_gap*ratio);cursor=Math.max(cursor,line.y+line.bottom)});
    const left=Math.min(0,...lines.map(l=>l.x+l.left)),right=Math.max(0,...lines.map(l=>l.x+l.left+l.width)),H=Math.max(Math.round(unit*1.3),Math.round(cursor+unit*.24));
    lines.forEach(line=>{line.x+=W/2-(left+right)/2;line.y+=(H-cursor)/2});return {plan,lines,ratio,H};
  }
  function paint(q,index,now){
    const W=canvas.width,frameHeight=W*stage.clientHeight/Math.max(1,stage.clientWidth),allWords=wordsAt(index),chosen=$('#font').value;
    if(!allWords.length){pen.clearRect(0,0,W,canvas.height);canvas.textContent='';canvas.dataset.wordIndices='';return}
    const ranges=splitRanges(allWords,q);let pageIndex=0;
    for(let i=1;i<ranges.length;i++)if(q.words[ranges[i].start].start<=now)pageIndex=i;
    const page=ranges[pageIndex],pageStart=page.start,words=allWords.slice(page.start,page.start+page.count),colors=(wordColors[index]||[]).slice(page.start,page.start+page.count);
    q={...q,template_source:page.template_source,template_slot:page.template_slot,start:pageIndex?q.words[page.start].start:q.start,end:pageIndex+1<ranges.length?q.words[ranges[pageIndex+1].start].start:q.end,words:q.words.slice(page.start,page.start+page.count)};
    const key=JSON.stringify([W,frameHeight,words,chosen,q.template_source,q.template_slot]);let layout=layouts.get(key);
    if(!layout){layout=layoutFor(words,W,frameHeight,chosen,q);if(layouts.size>128)layouts.clear();layouts.set(key,layout)}
    const {plan,lines,ratio,H}=layout;if(canvas.height!==H)canvas.height=H;pen.clearRect(0,0,W,H);
    const exitSeconds=Math.min(config.motion.exit_seconds,Math.max(.015,(q.end-q.words.at(-1).start)*.25)),shown=i=>q.words[i].start<=now&&(visibility!=='styled_spoken'||now<q.words[i].end);
    const [scale,drift]=cameraState(now-q.start,plan.motion??'in'),[dx,dy]=transitionState(q.end-now,plan.transition??'focus');
    pen.save();pen.translate(W/2+dx*ratio,H/2+(drift+dy)*ratio);pen.scale(scale,scale);pen.translate(-W/2,-H/2);
    for(const line of lines){
      const row=line.row,first=q.words[row.words[0]].start,main=['main','accent'].includes(row.role),rowDy=motionState(now-first,q.end-now,q.end-first,main,exitSeconds)[2];
      for(const run of line.runs){
        if(!shown(run.i))continue;
        const word=q.words[run.i],[alpha,blur]=motionState(now-word.start,q.end-now,q.end-word.start,main,exitSeconds),x=line.x+run.x,y=line.y,color=colors[run.i]||config[row.tone_override??row.tone??'ink']||config.ink;
        const token=JSON.stringify([W,H,run.css,run.text,run.tracking,x,y,color]);let glyph=assets.get(token);
        if(!glyph){glyph=document.createElement('canvas');glyph.width=W;glyph.height=H;const gp=glyph.getContext('2d');gp.font=run.css;gp.textBaseline='alphabetic';gp.fillStyle=color;
          [...run.text].forEach((c,j)=>gp.fillText(c,x+gp.measureText(run.text.slice(0,j)).width+j*run.size*run.tracking,y));if(assets.size>256)assets.clear();assets.set(token,glyph)}
        pen.save();pen.globalAlpha=alpha;pen.filter=blur>.08?`blur(${blur*ratio}px)`:'none';pen.drawImage(glyph,0,rowDy*ratio);pen.restore();
      }
      if(plan.dash&&row.role==='main'&&now>=first){
        const opacity=motionState(now-first,q.end-now,q.end-first,true,exitSeconds)[0],x=line.x+line.left+line.width+12*ratio,y=line.y+(line.top+line.bottom)/2+rowDy*ratio;
        pen.save();pen.globalAlpha=opacity;pen.strokeStyle=config.ink;pen.lineWidth=Math.max(1,Math.round(2*ratio));pen.beginPath();pen.moveTo(x,y);pen.lineTo(x+42*ratio,y);pen.stroke();pen.restore();
      }
    }
    if(plan.arrow&&lines.length>1){
      const last=lines.at(-1),prior=lines.at(-2),trigger=q.words[last.runs[0].i].start-.24,points=arrowPoints(),count=Math.min(points.length,Math.trunc(smooth((now-trigger)/.65)*points.length));
      if(count>1){const y=Math.max(last.y+last.top-78*ratio,prior.y+prior.bottom+10*ratio);pen.save();pen.globalAlpha=smooth((q.end-now)/exitSeconds);pen.strokeStyle=config.ink;pen.lineWidth=Math.max(1,Math.round(1.6*ratio));pen.lineCap='round';pen.lineJoin='round';pen.beginPath();points.slice(0,count).forEach(([x,v],i)=>i?pen.lineTo(W/2+x*ratio,y+v*ratio):pen.moveTo(W/2+x*ratio,y+v*ratio));pen.stroke();pen.restore()}
    }
    pen.restore();const visible=words.map((_,i)=>i).filter(shown);canvas.setAttribute('aria-label',visible.map(i=>words[i]).join(' '));canvas.textContent=visible.map(i=>words[i]).join(' ');canvas.dataset.style='caption_3';canvas.dataset.wordIndices=visible.map(i=>i+pageStart).join(',');
  }
  draw=function(){
    baseDraw();if(currentStyle!=='caption_3'||visibility==='spoken')return;
    const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end);if(index<0){caption.replaceChildren();return}
    caption.replaceChildren(canvas);caption.className='caption-three-reference';Object.assign(caption.style,{left:'0',right:'0',top:templates.caption_3.default_position*100+'%',width:'100%',maxWidth:'none',transform:'translateY(-50%)',filter:'none',opacity:'1',background:'transparent',visibility:'visible',padding:'0',textShadow:'none'});
    paint(cues[index],index,now);updateSelection();
  };
  video.addEventListener('seeked',draw);video.addEventListener('pause',draw);window.addEventListener('resize',draw);
  Promise.all([document.fonts.load('700 148px "Caption Three Serif"'),document.fonts.load('400 56px "Caption Three Serif"'),document.fonts.load('400 86px "Caption Three Playful"')]).then(()=>{assets.clear();layouts.clear();draw()});
})();
