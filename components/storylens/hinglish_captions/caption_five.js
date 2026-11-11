// Caption 5 shares its word roles, sizes and speech-driven motion with export.
(() => {
  const config=project.caption_five_profile;if(!config)return;
  const normalize=text=>String(text).toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]/gu,'');
  function planFor(words){
    const key=words.map(normalize).join(' ');let known=[...config.demo_phrases,...config.recipes].find(r=>r.text.split(/\s+/).map(normalize).join(' ')===key);
    if(storylensTemplateRebound(words))known=null;
    if(!words.length)return {rows:[],mode:'stack',tone:'red',condensed:false};
    if(!known)known=storylensTemplatePattern(words,[...config.demo_phrases,...config.recipes]);
    const numbers=words.map((w,i)=>/^\d+$/.test(normalize(w))?i:-1).filter(i=>i>=0),stops=new Set(config.stop_words);let hero=numbers[0]??known?.hero??0,score=-Infinity;
    if(!known&&!numbers.length)words.forEach((w,i)=>{const value=[...normalize(w)].length-(stops.has(normalize(w))?100:0);if(value>score){hero=i;score=value}});
    const rows=[];if(hero)rows.push({role:'header',words:words.slice(0,hero).map((_,i)=>i)});rows.push({role:'main',words:[hero]});
    if(hero+1<words.length)rows.push({role:'footer',words:words.slice(hero+1).map((_,i)=>i+hero+1)});
    return {rows,adapted:Boolean(known?.adapted),mode:known?.mode??'flank',tone:known?.tone??'red',condensed:known?.condensed??normalize(words[hero]).length>=8,number:numbers.includes(hero),support_focus:known?.support_focus??-1};
  }
  function smooth(value){const p=Math.max(0,Math.min(1,value));return p*p*(3-2*p)}
  function motionState(age,available,main=false,condensed=false){
    const m=config.motion,duration=Math.min(main?m.main_seconds:m.support_seconds,Math.max(.06,available*.60)),p=Math.max(0,Math.min(1,age/duration)),remaining=(1-p)**3;
    const fade=Math.min(condensed&&main?m.condensed_fade:main?m.main_fade:m.support_fade,Math.max(.025,available*.28));
    return [smooth(age/fade),condensed&&main?m.condensed_slide*remaining:0,(main&&!condensed?m.main_rise:!main?m.support_rise:0)*remaining,1-(main?m.main_scale:m.support_scale)*remaining];
  }
  const canvas=document.createElement('canvas');canvas.width=720;canvas.style.cssText='display:block;width:100%;height:auto;margin:0';canvas.setAttribute('role','img');
  const pen=canvas.getContext('2d'),measure=document.createElement('canvas').getContext('2d'),baseDraw=draw,assets=new Map(),layouts=new Map();let assetKey='';
  function layout(words,W,unit){
    const key=JSON.stringify([words,W,unit,$('#font').value]);if(layouts.has(key))return layouts.get(key);
    let plan=planFor(words),ratio=unit/720;const chosen=$('#font').value,regular=chosen==='template'?'"Inter Caption 2"':fonts[chosen].css,heroFamily=chosen==='template'&&plan.condensed?'Impact':regular;
    const lines=plan.rows.map(row=>{
      const main=row.role==='main',family=main?heroFamily:regular;
      const base=main&&plan.number?config.number_size:main&&plan.condensed?config.condensed_size:main?config.main_size:config.support_size;
      function runsFor(baseSize){
        let cursor=0;const runs=row.words.map(i=>{
          const size=Math.max(2,Math.round((!main&&i===plan.support_focus?config.support_focus_size:baseSize)*ratio)),css=`${family==='Impact'?'400':'900'} ${size}px ${family}`,tracking=config.tracking,text=main?words[i].toUpperCase():words[i];measure.font=css;
          let left=Infinity,right=-Infinity,top=Infinity,bottom=-Infinity;
          [...text].forEach((c,j)=>{if(/\s/.test(c))return;const p=measure.measureText(text.slice(0,j)).width+j*size*tracking,m=measure.measureText(c);left=Math.min(left,p-m.actualBoundingBoxLeft);right=Math.max(right,p+m.actualBoundingBoxRight);top=Math.min(top,-m.actualBoundingBoxAscent);bottom=Math.max(bottom,m.actualBoundingBoxDescent)});
          if(!Number.isFinite(left)){left=right=top=bottom=0}
          const run={i,text,size,css,tracking,x:cursor,left,right,top,bottom};cursor+=measure.measureText(text).width+Math.max(0,text.length-1)*size*tracking+size*config.space;return run;
        });
        const left=Math.min(...runs.map(r=>r.x+r.left)),right=Math.max(...runs.map(r=>r.x+r.right));return {row,runs,left,width:right-left,top:Math.min(...runs.map(r=>r.top)),bottom:Math.max(...runs.map(r=>r.bottom))};
      }
      let line=runsFor(base);if(!plan.adapted&&main&&line.width>unit*config.safe_width)line=runsFor(base*unit*config.safe_width/line.width);return line;
    });
    if(!lines.length)return {plan,lines,ratio};
    if(plan.adapted){const fit=Math.min(1,...lines.map(l=>unit*config.safe_width/Math.max(1,l.width)),plan.mode==='flank'?unit*config.safe_width/Math.max(1,lines.reduce((a,l)=>a+l.width,0)+Math.max(0,lines.length-1)*config.gap*ratio):1);if(fit<1){ratio*=fit;for(const line of lines){for(const k of ['left','width','top','bottom'])line[k]*=fit;for(const r of line.runs){for(const k of ['x','left','right','top','bottom'])r[k]*=fit;r.size=Math.max(2,Math.round(r.size*fit));r.css=r.css.replace(/[\d.]+px/,r.size+'px')}}}}
    const main=lines.find(l=>l.row.role==='main'),header=lines.find(l=>l.row.role==='header'),footer=lines.find(l=>l.row.role==='footer'),gap=config.gap*ratio;
    const combined=lines.reduce((sum,l)=>sum+l.width,0)+Math.max(0,lines.length-1)*gap,flank=plan.mode==='flank'&&combined<=unit*config.safe_width+1;plan={...plan,arrangement:flank?'flank':'stack'};
    if(flank){
      let cursor=(W-combined)/2;
      // Match export: support words and the hero share one alphabetic baseline.
      [...(header?[header]:[]),main,...(footer?[footer]:[])].forEach(line=>{line.x=cursor-line.left;cursor+=line.width+gap;line.y=0});
    }else{
      lines.forEach(line=>{const role=line.row.role;line.x=(W-line.width)/2-line.left;line.y=role==='main'?0:role==='header'?main.top-gap-line.bottom:main.bottom+gap-line.top});
      if(header&&plan.mode==='offset')header.x=Math.max(W*.08,(W-main.width)/2-header.left);
      if(footer&&plan.mode==='offset')footer.x=Math.min(W*.92-footer.width,(W+main.width)/2-footer.width)-footer.left;
    }
    if(plan.adapted){const margin=(W-unit*config.safe_width)/2;for(const line of lines)line.x=Math.max(margin-line.left,Math.min(line.x,W-margin-line.width-line.left))}
    const top=Math.min(...lines.map(l=>l.y+l.top)),bottom=Math.max(...lines.map(l=>l.y+l.bottom)),center=(top+bottom)/2;lines.forEach(line=>line.y-=center);
    const result={plan,lines,ratio};if(layouts.size>=512)layouts.clear();layouts.set(key,result);return result;
  }
  function pagesFor(q,words,W,unit){
    const pages=[];let start=0;
    while(start<words.length){
      const fits=[];for(let count=1;count<=Math.min(config.max_words,words.length-start);count++){const l=layout(words.slice(start,start+count),W,unit);if(l.lines.every(line=>line.width<=unit*config.safe_width+unit/720))fits.push(count)}
      let split=Math.max(1,...fits);if(words.length-start-split===1){const other=fits.filter(n=>n<split&&words.length-start-n>=2);if(other.length)split=Math.max(...other)}
      pages.push({start,end:start+split,onset:start?q.words[start].start:q.start});start+=split;
    }return pages.map((p,i)=>({...p,until:pages[i+1]?.onset??q.end}));
  }
  function paint(source,index,now){
    const W=canvas.width,unit=Math.min(W,W*stage.clientHeight/Math.max(1,stage.clientWidth)*1.75),H=Math.round(unit*1.05),all=wordsAt(index);if(canvas.height!==H)canvas.height=H;pen.clearRect(0,0,W,H);
    if(!all.length){canvas.textContent='';canvas.setAttribute('aria-label','');return}
    const page=pagesFor(source,all,W,unit).find(p=>p.onset<=now&&now<p.until);if(!page)return;
    const words=all.slice(page.start,page.end),q={start:page.onset,end:page.until,words:source.words.slice(page.start,page.end)},colors=(wordColors[index]||[]).slice(page.start,page.end),{plan,lines,ratio}=layout(words,W,unit),center=H/2;
    const key=JSON.stringify([index,W,H,words,colors,$('#font').value]);if(key!==assetKey){assets.clear();assetKey=key}
    const shown=i=>q.words[i].start<=now&&(visibility!=='styled_spoken'||now<q.words[i].end);
    for(const line of lines)for(const run of line.runs){
      if(!shown(run.i))continue;const word=q.words[run.i],main=line.row.role==='main',[alpha,dx,dy,scale]=motionState(now-word.start,q.end-word.start,main,plan.condensed),x=line.x+run.x,y=center+line.y,color=colors[run.i]||config[main?plan.tone:'black'];
      const token=JSON.stringify([run.i,run.css,run.text,x,y,color]);let glyph=assets.get(token);
      if(!glyph){glyph=document.createElement('canvas');glyph.width=W;glyph.height=H;const gp=glyph.getContext('2d');gp.font=run.css;gp.textBaseline='alphabetic';gp.fillStyle=color;[...run.text].forEach((c,j)=>gp.fillText(c,x+gp.measureText(run.text.slice(0,j)).width+j*run.size*run.tracking,y));assets.set(token,glyph)}
      const ax=x+(run.left+run.right)/2,ay=y+(run.top+run.bottom)/2;
      pen.save();pen.globalAlpha=alpha;pen.translate(ax+dx*ratio,ay+dy*ratio);pen.scale(scale,scale);pen.translate(-ax,-ay);pen.drawImage(glyph,0,0);pen.restore();
    }
    const visible=words.map((_,i)=>i).filter(shown);canvas.setAttribute('aria-label',visible.map(i=>words[i]).join(' '));canvas.textContent=visible.map(i=>words[i]).join(' ');canvas.dataset.style='caption_5';canvas.dataset.wordIndices=visible.map(i=>i+page.start).join(',');
  }
  draw=function(){
    baseDraw();if(currentStyle!=='caption_5'||visibility==='spoken')return;
    const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end);if(index<0){caption.replaceChildren();return}
    caption.replaceChildren(canvas);caption.className='caption-five-reference';
    Object.assign(caption.style,{left:'0',right:'0',top:templates.caption_5.default_position*100+'%',width:'100%',maxWidth:'none',transform:'translateY(-50%)',filter:'none',opacity:'1',background:'transparent',visibility:'visible',padding:'0',textShadow:'none'});
    paint(cues[index],index,now);updateSelection();
  };
  video.addEventListener('seeked',draw);video.addEventListener('pause',draw);window.addEventListener('resize',draw);
  Promise.all([document.fonts.load('900 104px "Inter Caption 2"'),document.fonts.load('400 112px Impact')]).then(()=>{assets.clear();layouts.clear();assetKey='';draw()});
})();
