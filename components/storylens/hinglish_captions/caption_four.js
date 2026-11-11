// Caption 4 mirrors the export's font geometry and second-based motion clocks.
(() => {
  const config=project.caption_four_profile;if(!config)return;
  const normalize=text=>String(text).toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]/gu,'');
  function planFor(words){
    const key=words.map(normalize).join(' ');let known=[...config.demo_phrases,...config.recipes].find(r=>r.text.split(/\s+/).map(normalize).join(' ')===key);
    if(storylensTemplateRebound(words))known=null;
    if(!words.length)return {rows:[],motion:'in'};
    if(!known)known=storylensTemplatePattern(words,config.recipes);
    const design=Object.fromEntries(['header_alignment','footer_alignment','header_inset','footer_outset','footer_bold','footer_size','main_size','main_words'].filter(k=>known&&k in known).map(k=>[k,known[k]]));
    const stops=new Set([...config.stop_words,...'your our their his her my its this that these those i me us them be been being am are was were have has had will would can could should do does did for from by as if then now hai hain ho tha thi'.split(' ')]);
    const eligible=words.map((_,i)=>i).filter(i=>normalize(words[i])&&!stops.has(normalize(words[i])));
    const hero=eligible.includes(known?.hero)?known.hero:eligible.length?eligible.reduce((a,b)=>[...normalize(words[b])].length>[...normalize(words[a])].length?b:a):null;
    if(hero===null)return {rows:[{role:'header',words:words.map((_,i)=>i)}],motion:known?.motion??'in',adapted:Boolean(known?.adapted),design};
    let count=Math.max(1,Math.min(design.main_words??1,words.length-hero));while(count>1&&words.slice(hero,hero+count).some((_,j)=>!eligible.includes(hero+j)))count--;
    const rows=[];if(hero)rows.push({role:'header',words:words.slice(0,hero).map((_,i)=>i)});
    rows.push({role:'main',words:words.slice(hero,hero+count).map((_,i)=>hero+i)});
    const footer=words.slice(hero+count).map((_,i)=>hero+count+i);
    if(footer.length)rows.push({role:'footer',words:footer});
    return {rows,motion:known?.motion??'in',adapted:Boolean(known?.adapted),design};
  }
  function smooth(value){const p=Math.max(0,Math.min(1,value));return p*p*p*(p*(p*6-15)+10)}
  function motionState(age,remaining,available,main=false,exitSeconds=.1){
    const m=config.motion,duration=Math.min(m.focus_seconds,Math.max(.06,available*.60)),p=smooth(age/duration),fade=smooth(age/Math.min(m.fade_seconds,Math.max(.045,available*.28))),leave=smooth(remaining/Math.max(.015,exitSeconds));
    return [fade*leave,m.blur*(1-p)+m.exit_blur*(1-leave),(main?m.main_rise:m.support_rise)*(1-p),1-(main?.10:.025)*(1-p)];
  }
  function cameraState(age,mode='in'){const m=config.motion,p=smooth(age/m.camera_seconds);return [mode==='in'?1+m.camera_zoom*p:1+m.camera_zoom*(1-p),m.camera_drift*p]}
  const canvas=document.createElement('canvas');canvas.width=720;canvas.style.cssText='display:block;width:100%;height:auto;margin:0';canvas.setAttribute('role','img');
  const pen=canvas.getContext('2d'),measure=document.createElement('canvas').getContext('2d'),baseDraw=draw;
  const assets=new Map(),inkProfiles=new Map(),layouts=new Map();let assetKey='';
  function inkProfile(line){
    const key=JSON.stringify(line.runs.map(r=>[r.css,r.text,r.tracking,r.x]));if(inkProfiles.has(key))return inkProfiles.get(key);
    const extent=Math.max(2,...line.runs.map(r=>r.size))*2,w=Math.max(1,Math.trunc(line.width+8)),h=extent*2;
    const mask=document.createElement('canvas');mask.width=w;mask.height=h;const gp=mask.getContext('2d',{willReadFrequently:true});gp.textBaseline='alphabetic';gp.fillStyle='#000';
    for(const run of line.runs){gp.font=run.css;[...run.text].forEach((c,j)=>gp.fillText(c,run.x-line.left+3+gp.measureText(run.text.slice(0,j)).width+j*run.size*run.tracking,extent))}
    const pixels=gp.getImageData(0,0,w,h).data,top=new Float64Array(w).fill(Infinity),bottom=new Float64Array(w).fill(-Infinity);
    for(let y=0;y<h;y++)for(let x=0;x<w;x++)if(pixels[(y*w+x)*4+3]>48){top[x]=Math.min(top[x],y-extent);bottom[x]=y-extent}
    const result={offset:line.left-3,top,bottom};if(inkProfiles.size>=512)inkProfiles.clear();inkProfiles.set(key,result);return result;
  }
  function opticalBaseline(main,line,gap,above=false){
    const m=inkProfile(main),p=inkProfile(line),shift=line.x+p.offset-main.x-m.offset;let value=above?Infinity:-Infinity;
    for(let x=0;x<p.top.length;x++){
      const mx=Math.round(x+shift);if(mx<0||mx>=m.top.length)continue;
      const difference=above?m.top[mx]-p.bottom[x]:m.bottom[mx]-p.top[x];
      if(Number.isFinite(difference))value=above?Math.min(value,difference):Math.max(value,difference);
    }
    if(above){const cap=main.top+Math.max(...main.runs.map(r=>r.size))*.22-line.bottom;return Math.min(Number.isFinite(value)?value:main.top-line.bottom,cap)-gap}
    return Math.max(Math.min(0,main.bottom)-line.top,Number.isFinite(value)?value:0)+gap;
  }
  function layout(words,W,unit){
    const plan=planFor(words),design=plan.design??{};
    const layoutKey=JSON.stringify([words,W,unit,$('#font').value,plan]);if(layouts.has(layoutKey))return layouts.get(layoutKey);
    let ratio=unit/720;const chosen=$('#font').value,family=chosen==='template'?'"Times New Roman"':fonts[chosen].css;
    const lines=plan.rows.map(row=>{
      const main=['main','accent'].includes(row.role)||(row.role==='footer'&&design.footer_bold),tracking=main?config.tracking:config.support_tracking;
      function runsFor(size){
        size=Math.max(2,Math.round(size*ratio));const css=`${chosen==='template'?'italic ':''}${main?'700':'400'} ${size}px ${family}`;measure.font=css;
        let cursor=0;const runs=row.words.map(i=>{
          const text=words[i];let left=Infinity,right=-Infinity,top=0,bottom=0;
          [...text].forEach((c,j)=>{const p=measure.measureText(text.slice(0,j)).width+j*size*tracking,m=measure.measureText(c);left=Math.min(left,p-m.actualBoundingBoxLeft);right=Math.max(right,p+m.actualBoundingBoxRight)});
          const metrics=measure.measureText(text);top=-metrics.actualBoundingBoxAscent;bottom=metrics.actualBoundingBoxDescent;
          const run={i,text,size,css,tracking,x:cursor,left,right,top,bottom};cursor+=metrics.width+Math.max(0,text.length-1)*size*tracking+size*config.space;return run;
        });
        const left=Math.min(...runs.map(r=>r.x+r.left)),right=Math.max(...runs.map(r=>r.x+r.right));return {row,runs,left,width:right-left,top:Math.min(...runs.map(r=>r.top)),bottom:Math.max(...runs.map(r=>r.bottom))};
      }
      let size=design[row.role+'_size']??config[row.role+'_size']??config.main_size,line=runsFor(size);if(line.width>unit*config.safe_width)line=runsFor(size*unit*config.safe_width/line.width);return line;
    });
    const main=lines.find(line=>line.row.role==='main'),safeWidth=unit*config.safe_width,maxOffset=unit*(config.max_support_offset??.12);
    lines.forEach(line=>{
      const role=line.row.role;let y;
      let offset=0;
      if(main&&role==='header'&&design.header_alignment!=='center')offset=(line.width-main.width)/2+(design.header_inset??0)*ratio;
      else if(main&&role==='footer'&&design.footer_alignment!=='center')offset=(main.width-line.width)/2+(design.footer_outset??0)*ratio;
      const room=Math.max(0,Math.min(maxOffset,(safeWidth-line.width)/2));offset=Math.max(-room,Math.min(room,offset));
      if(role==='main'||!main)y=0;
      else if(role==='header')y=main.top-config.header_gap*ratio-line.bottom;
      else y=main.bottom+config.footer_gap*ratio-line.top;
      line.x=offset-line.width/2-line.left;line.y=y;
    });
    const left=Math.min(0,...lines.map(l=>l.x+l.left)),right=Math.max(0,...lines.map(l=>l.x+l.left+l.width)),shift=W/2-(left+right)/2;
    lines.forEach(line=>{line.x+=shift});
    lines.forEach(line=>{if(main&&line.row.role==='header')line.y=opticalBaseline(main,line,config.header_gap*ratio,true);else if(main&&line.row.role==='footer')line.y=opticalBaseline(main,line,config.footer_gap*ratio)});
    const result={plan,lines,ratio};if(layouts.size>=512)layouts.clear();layouts.set(layoutKey,result);return result;
  }
  function pagesFor(q,words,W,unit){
    const pages=[];let start=0;
    while(start<words.length){
      const fits=[];for(let count=1;count<=Math.min(config.max_words,words.length-start);count++){const l=layout(words.slice(start,start+count),W,unit);if(l.lines.every(line=>line.width<=unit*config.safe_width+ratioTolerance(unit)))fits.push(count)}
      let split=Math.max(1,...fits);if(words.length-start-split===1){const other=fits.filter(n=>n<split&&words.length-start-n>=2);if(other.length)split=Math.max(...other)}
      pages.push({start,end:start+split,onset:start?q.words[start].start:q.start});start+=split;
    }
    return pages.map((p,i)=>({...p,until:pages[i+1]?.onset??q.end}));
  }
  function ratioTolerance(unit){return unit/720}
  function paint(source,index,now){
    const W=canvas.width,unit=Math.min(W,W*stage.clientHeight/Math.max(1,stage.clientWidth)*.75),H=Math.round(unit*.85),all=wordsAt(index);
    if(canvas.height!==H)canvas.height=H;pen.clearRect(0,0,W,H);if(!all.length){canvas.textContent='';canvas.setAttribute('aria-label','');return}
    const page=pagesFor(source,all,W,unit).find(p=>p.onset<=now&&now<p.until);if(!page)return;
    const words=all.slice(page.start,page.end),q={start:page.onset,end:page.until,words:source.words.slice(page.start,page.end)},colors=(wordColors[index]||[]).slice(page.start,page.end),{plan,lines,ratio}=layout(words,W,unit),center=H*.5;
    const key=JSON.stringify([index,W,H,words,colors,$('#font').value]);if(key!==assetKey){assets.clear();assetKey=key}
    const [scale,drift]=cameraState(now-q.start,plan.motion),ax=W/2,ay=center-25*ratio,exitSeconds=Math.min(config.motion.exit_seconds,Math.max(.015,(q.end-q.words.at(-1).start)*.20));
    pen.save();pen.translate(ax,ay+drift*ratio);pen.scale(scale,scale);pen.translate(-ax,-ay);
    const shown=i=>q.words[i].start<=now&&(visibility!=='styled_spoken'||now<q.words[i].end);
    for(const line of lines)for(const run of line.runs){
      if(!shown(run.i))continue;
      const prominent=['main','accent'].includes(line.row.role)||(line.row.role==='footer'&&plan.design?.footer_bold);
      const word=q.words[run.i],[alpha,blur,dy,localScale]=motionState(now-word.start,q.end-now,q.end-word.start,prominent,exitSeconds),x=line.x+run.x,y=center+line.y;
      const token=JSON.stringify([run.i,run.css,run.text,x,y,colors[run.i]]);let glyph=assets.get(token);
      if(!glyph){glyph=document.createElement('canvas');glyph.width=W;glyph.height=H;const gp=glyph.getContext('2d');gp.font=run.css;gp.textBaseline='alphabetic';gp.fillStyle=colors[run.i]||config.ink;[...run.text].forEach((c,j)=>gp.fillText(c,x+gp.measureText(run.text.slice(0,j)).width+j*run.size*run.tracking,y));assets.set(token,glyph)}
      const cx=x+(run.left+run.right)/2,cy=y+(run.top+run.bottom)/2;
      pen.save();pen.globalAlpha=alpha;pen.filter=blur>.08?`blur(${blur*ratio}px)`:'none';pen.translate(cx,cy+dy*ratio);pen.scale(localScale,localScale);pen.translate(-cx,-cy);pen.drawImage(glyph,0,0);pen.restore();
    }
    pen.restore();const visible=words.map((_,i)=>i).filter(shown);canvas.setAttribute('aria-label',visible.map(i=>words[i]).join(' '));canvas.textContent=visible.map(i=>words[i]).join(' ');canvas.dataset.style='caption_4';canvas.dataset.wordIndices=visible.map(i=>i+page.start).join(',');
  }
  draw=function(){
    baseDraw();if(currentStyle!=='caption_4'||visibility==='spoken')return;
    const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end);if(index<0){caption.replaceChildren();return}
    caption.replaceChildren(canvas);caption.className='caption-four-reference';
    Object.assign(caption.style,{left:'0',right:'0',top:templates.caption_4.default_position*100+'%',width:'100%',maxWidth:'none',transform:'translateY(-50%)',filter:'none',opacity:'1',background:'transparent',visibility:'visible',padding:'0',textShadow:'none'});
    paint(cues[index],index,now);updateSelection();
  };
  video.addEventListener('seeked',draw);video.addEventListener('pause',draw);window.addEventListener('resize',draw);
  Promise.all([document.fonts.load('italic 700 138px "Times New Roman"'),document.fonts.load('italic 400 52px "Times New Roman"')]).then(()=>{assets.clear();inkProfiles.clear();layouts.clear();assetKey='';draw()});
})();
