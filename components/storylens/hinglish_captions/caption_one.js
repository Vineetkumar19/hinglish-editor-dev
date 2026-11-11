// Caption 1 uses the same measured rows, font files, and tracking as export.
(() => {
  const config=project.caption_one_profile;if(!config)return;
  const normalize=text=>String(text).toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]/gu,'');
  function planFor(words){
    if(!words.length)return {rows:[],hero:0};
    const key=words.map(normalize).join(' '),matchesPrefix=r=>r.text.split(/\s+/).slice(0,words.length).map(normalize).join(' ')===key;
    const known=config.recipes.find(matchesPrefix);
    const sample=(config.demo_phrases||[]).find(r=>matchesPrefix(r)&&r.hero<words.length);
    const stops=new Set(config.stop_words);let hero=0,score=-Infinity;
    const interior=words.length<2?[0]:words.map((_,i)=>i).filter(i=>i>0);
    const candidates=(known?known.rows.filter(r=>r.blue).flatMap(r=>r.words):[]).filter(i=>interior.includes(i));
    (candidates.length?candidates:interior).forEach(i=>{const n=normalize(words[i]),s=n.length-(stops.has(n)?100:0);if(s>score){hero=i;score=s}});
    if(sample)hero=sample.hero;
    const twoLines=[...normalize(words[hero])].length>=config.alignment.two_line_letters;
    const rows=[];
    if(hero)rows.push({words:words.slice(0,hero).map((_,i)=>i),size:46,align:'left',baseline:-.75});
    rows.push({words:[hero],size:80,align:'left',baseline:0,blue:true,upper:true});
    const footer=words.slice(hero+1).map((_,i)=>i+hero+1);
    if(footer.length&&!twoLines)rows.push({words:footer,size:46,align:'right',baseline:.54});
    const shown=new Set(rows.flatMap(r=>r.words));
    return {rows,hero,display:known?.display||{},hidden:words.map((_,i)=>i).filter(i=>!shown.has(i)),two_line:twoLines};
  }
  function motionState(elapsed,motion){
    const progress=Math.max(0,Math.min(1,elapsed/motion.duration));
    const eased=progress**3*(progress*(progress*6-15)+10),fade=Math.max(0,Math.min(1,elapsed/motion.fade));
    return [fade*fade*(3-2*fade),motion.x*(1-eased),motion.y*(1-eased)];
  }
  function motionFor(plan,row,index){
    const m=config.smooth_motion,main=index===plan.hero;
    return {duration:main?m.main_seconds:m.support_seconds,fade:main?m.main_fade_seconds:m.support_fade_seconds,x:main?0:m.slide_x,y:main?m.rise_y:0,start_word:main?index:row.words[0]};
  }
  function phaseAt(plan,words,now,end,mode='phrase'){
    const shown=new Set(plan.rows.flatMap(r=>r.words));
    const indices=mode==='styled_spoken'?words.map((_,i)=>i).filter(i=>shown.has(i)&&words[i].start<=now&&now<words[i].end)
      :plan.rows.filter(r=>words[r.words[0]].start<=now).flatMap(r=>r.words).sort((a,b)=>a-b);
    return {kind:'stack',indices,onset:words[0].start,end};
  }
  function splitFor(words,lineWidth){
    const pages=[];let start=0;
    while(start<words.length){
      const rest=words.slice(start),fits=[];
      for(let count=1;count<=rest.length;count++){
        const prefix=rest.slice(0,count),plan=planFor(prefix);
        if(plan.hidden.length)continue;
        const cap=lineWidth(prefix,[plan.hero],true)-Math.abs(config.smooth_motion.slide_x);
        if(plan.rows.every(row=>lineWidth(prefix,row.words,!!row.blue)<=(row.align==='right'?cap:config.native_width*config.max_width)))fits.push(count);
      }
      let split=fits.length?fits.at(-1):1;
      if(rest.length-split===1){const alternatives=fits.filter(n=>n<split&&rest.length-n>=2);if(alternatives.length)split=alternatives.at(-1)}
      pages.push({start,end:start+split});start+=split;
    }return pages;
  }
  const canvas=document.createElement('canvas');canvas.width=1080;canvas.style.cssText='display:block;width:100%;height:auto;margin:0';canvas.setAttribute('role','img');
  const pen=canvas.getContext('2d'),baseDraw=draw;
  // Build one opaque word mask first. Applying opacity to individual tracked
  // letters makes their overlaps brighter and creates false shiny outlines.
  let assetKey='';const wordAssets=new Map();
  function paint(q,index,now){
    const W=canvas.width,unit=Math.min(W,W*stage.clientHeight/Math.max(1,stage.clientWidth)*.75),H=Math.round(unit*config.region_ratio);
    if(canvas.height!==H)canvas.height=H;pen.clearRect(0,0,W,H);
    const allWords=wordsAt(index).map(w=>w.replace(/^[.,!?:;]+|[.,!?:;]+$/g,'')||w);
    const chosen=$('#font').value,selected=fonts[chosen],family=chosen==='template'?'"Inter Caption 1"':selected.css;
    const selectedWeight=/(bd|uib|b)\.ttf$/i.test(selected.file||'')?'700':'400';
    function nativeWidth(words,indices,main){
      const size=main?80:46,tracking=main?config.tracking:config.support_tracking;
      pen.font=`${chosen==='template'?(main?'700':'500'):selectedWeight} ${size}px ${family}`;
      let cursor=0,left=Infinity,right=-Infinity;
      indices.forEach(i=>{
        const text=main?words[i].toUpperCase():words[i];
        [...text].forEach((c,j)=>{const p=cursor+pen.measureText(text.slice(0,j)).width+j*size*tracking,m=pen.measureText(c);left=Math.min(left,p-m.actualBoundingBoxLeft);right=Math.max(right,p+m.actualBoundingBoxRight)});
        cursor+=pen.measureText(text).width+Math.max(0,text.length-1)*size*tracking+80*config.word_gap;
      });return indices.length?right-left:0;
    }
    const pages=splitFor(allWords,nativeWidth);
    const page=pages.find((p,i)=>i===pages.length-1||now<q.words[pages[i+1].start].start)||pages[0];
    const words=allWords.slice(page.start,page.end),colors=(wordColors[index]||[]).slice(page.start,page.end);
    q={...q,words:q.words.slice(page.start,page.end),end:pages.indexOf(page)<pages.length-1?q.words[page.end].start:q.end};
    const plan=planFor(words),phase=phaseAt(plan,q.words,now,q.end,visibility);
    words.forEach((word,i)=>{words[i]=plan.display?.[String(i)]??word});
    const nextKey=JSON.stringify([index,W,H,chosen,words,colors]);
    if(nextKey!==assetKey){wordAssets.clear();assetKey=nextKey}
    function makeLine(row,scale){
      const runs=row.words.map((i,j)=>{
        const nativeSize=row.sizes?.[j]??row.size??80,size=Math.max(2,Math.round(nativeSize*scale));
        const weight=chosen==='template'?(nativeSize>46?'700':'500'):selectedWeight,css=`${weight} ${size}px ${family}`;
        const text=row.upper?words[i].toUpperCase():words[i];pen.font=css;
        const tracking=nativeSize<=46?config.support_tracking:config.tracking;
        let inkLeft=Infinity,inkRight=-Infinity;
        [...text].forEach((c,j)=>{const p=pen.measureText(text.slice(0,j)).width+j*size*tracking,m=pen.measureText(c);inkLeft=Math.min(inkLeft,p-m.actualBoundingBoxLeft);inkRight=Math.max(inkRight,p+m.actualBoundingBoxRight)});
        return {i,text,size,css,tracking,width:pen.measureText(text).width+Math.max(0,text.length-1)*size*tracking,inkLeft,inkRight};
      });
      const mixed=new Set(row.sizes||[]).size>1,gap=80*scale*(mixed?.1:row.blue?0:config.word_gap);
      let cursor=0,inkLeft=Infinity,inkRight=-Infinity;
      runs.forEach(r=>{inkLeft=Math.min(inkLeft,cursor+r.inkLeft);inkRight=Math.max(inkRight,cursor+r.inkRight);cursor+=r.width+gap});
      return {row,runs,gap,width:inkRight-inkLeft,inkLeft};
    }
    function arrange(scale){
      return plan.rows.map(row=>makeLine(row,scale));
    }
    let scale=unit/config.native_width,lines=arrange(scale),widest=Math.max(1,...lines.map(l=>l.width));
    if(widest>W*config.max_width){scale*=W*config.max_width/widest;lines=arrange(scale)}
    const groupWidth=Math.max(0,...lines.map(l=>l.width)),left=(W-groupWidth)/2;
    const mainWidth=lines.find(l=>l.row.words.includes(plan.hero)).width;
    const mainLine=lines.find(l=>l.row.words.includes(plan.hero));
    let mainDescent=0;
    mainLine.runs.forEach(run=>{pen.font=run.css;mainDescent=Math.max(mainDescent,pen.measureText(run.text).actualBoundingBoxDescent)});
    const mainBottom=H/2+(plan.offset||0)*scale+mainDescent;
    let mainAscent=0;mainLine.runs.forEach(run=>{pen.font=run.css;mainAscent=Math.max(mainAscent,pen.measureText(run.text).actualBoundingBoxAscent)});
    const mainTop=H/2+(plan.offset||0)*scale-mainAscent,lineGap=(config.alignment.ink_gap??9)*scale;
    pen.textBaseline='alphabetic';
    for(const {row,runs,width,gap,inkLeft} of lines){
      let x=(plan.two_line?(W-width)/2:row.align==='right'?left+mainWidth-width:left)-inkLeft+(row.x||0)*80*scale;
      let baseline=H/2+row.baseline*80*scale+(plan.offset||0)*scale;
      if(row.align==='right'){
        let ascent=0;runs.forEach(run=>{pen.font=run.css;ascent=Math.max(ascent,pen.measureText(run.text).actualBoundingBoxAscent)});
        baseline=mainBottom+lineGap+ascent;
      }else if(!row.blue&&row.baseline<0){
        let descent=0;runs.forEach(run=>{pen.font=run.css;descent=Math.max(descent,pen.measureText(run.text).actualBoundingBoxDescent)});
        baseline=mainTop-lineGap-descent;
      }
      for(const run of runs){
        const {i,text,size,css}=run,w=q.words[i],baseMotion=motionFor(plan,row,i);
        const motion=baseMotion;
        const visible=w&&phase.indices.includes(i);
        if(visible){
          const onset=visibility==='styled_spoken'?w.start:q.words[motion.start_word].start;
          const [alpha,dx,dy]=motionState(now-onset,motion);
          pen.font=css;const metrics=pen.measureText(text),custom=colors[i];
          let glyphCanvas=wordAssets.get(i);
          if(!glyphCanvas){
          glyphCanvas=document.createElement('canvas');glyphCanvas.width=W;glyphCanvas.height=H;
          const glyphPen=glyphCanvas.getContext('2d');
          glyphPen.clearRect(0,0,W,H);glyphPen.font=css;glyphPen.textBaseline='alphabetic';glyphPen.fillStyle='#FFFFFF';
          [...text].forEach((char,j)=>glyphPen.fillText(char,x+glyphPen.measureText(text.slice(0,j)).width+j*size*run.tracking,baseline));
          glyphPen.globalCompositeOperation='source-in';
          if(row.blue&&!custom){
            const gradient=glyphPen.createLinearGradient(0,baseline-metrics.actualBoundingBoxAscent,0,baseline+metrics.actualBoundingBoxDescent);
            config.gradient.forEach(([stop,color])=>gradient.addColorStop(stop,color));glyphPen.fillStyle=gradient;
          }else glyphPen.fillStyle=custom||'#FFFFFF';
          glyphPen.fillRect(0,0,W,H);glyphPen.globalCompositeOperation='source-over';
          wordAssets.set(i,glyphCanvas);
          }
          pen.save();pen.globalAlpha=alpha;pen.shadowColor='#00000080';pen.shadowBlur=scale;pen.shadowOffsetY=2*scale;
          pen.drawImage(glyphCanvas,dx*scale,dy*scale);
          pen.restore();
        }
        x+=run.width+gap;
      }
    }
    canvas.dataset.style='caption_1';canvas.dataset.font=family;
    const label=phase.indices.map(i=>words[i]).join(' ');
    canvas.setAttribute('aria-label',label);canvas.textContent=label;
    canvas.dataset.phase=phase.kind;
  }
  draw=function(){
    baseDraw();if(currentStyle!=='caption_1'||visibility==='spoken')return;
    const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end);
    if(index<0){caption.replaceChildren();return}
    caption.replaceChildren(canvas);caption.className='caption-one-reference';
    Object.assign(caption.style,{left:'0',right:'0',top:(templates.caption_1.default_position*100)+'%',width:'100%',maxWidth:'none',transform:'translateY(-50%)',filter:'none',opacity:'1',background:'transparent',visibility:'visible',padding:'0',textShadow:'none'});
    paint(cues[index],index,now);updateSelection();
  };
  video.addEventListener('seeked',draw);video.addEventListener('pause',draw);window.addEventListener('resize',draw);
  Promise.all([document.fonts.load('700 80px "Inter Caption 1"'),document.fonts.load('500 46px "Inter Caption 1"')])
    .then(()=>{wordAssets.clear();assetKey='';draw()});draw();
  const previewTime=new URLSearchParams(location.search).get('preview_time');
  if(project.demo&&previewTime!==null&&Number.isFinite(Number(previewTime))){
    const seekPreview=()=>{video.pause();video.currentTime=Math.max(0,Math.min(studioDuration-.01,Number(previewTime)));draw()};
    if(video.readyState>=1)seekPreview();else video.addEventListener('loadedmetadata',seekPreview,{once:true});
  }
})();
