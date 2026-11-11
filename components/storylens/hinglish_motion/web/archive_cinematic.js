/* Seekable, image-led stages. Every asset (including its background copies)
   remains gated by its own source-time entry. No player cutout is fabricated. */
window.buildArchiveMotion = function(root,d,api) {
  const {el,place,tweens,speed,landscape:L}=api;
  const w=L?1920:1080,h=L?1080:1920,duration=d.duration;
  const styles=['slate','map','ink','sepia','glass','album','night'];
  const style=styles.includes(d.archive_style)?d.archive_style:'slate';
  const variant=Number(d.archive_variant)||0,alt=variant%2===1,dir=alt?-1:1;
  const clamp=x=>Math.max(0,Math.min(1,x));
  const ease=x=>1-Math.pow(1-clamp(x),3);
  const smooth=x=>{const p=clamp(x);return p*p*(3-2*p);};
  const mix=(a,b,p)=>a+(b-a)*p;
  const pictures=(d.assets||[]).slice(0,4);
  const entry=(a,i)=>Number.isFinite(a?.enter_at)?Math.max(0,a.enter_at):i*1.6;
  const mono=d.archive_grade==='monochrome';
  const world=el('div','archive-world '+style+(alt?' alt':''),null,root);
  world.dataset.motion=style+'-'+(alt?'alternate':'primary');
  world.dataset.background={slate:'photo-projection',map:'tactical-field',ink:'halftone-paper',sepia:'archive-desk',glass:'prismatic-photo',album:'walnut-and-paper',night:'floodlit-portrait'}[style];
  if(mono)world.classList.add('monochrome');
  const bg=el('div','archive-background',null,world);
  const plane=el('div','archive-plane',null,world);
  const ns='http://www.w3.org/2000/svg';
  function svgNode(tag,attrs,parent){const n=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));parent.appendChild(n);return n;}
  // Background photographs carry the story, with opposing camera movement.
  // Later players never leak through a decorative duplicate before their cue.
  if(style==='album')el('div','archive-wood',null,bg);
  pictures.forEach((a,i)=>{
    if(!a.src)return;
    const photo=el('img','archive-bg-photo'+(style==='ink'&&i===0?' archive-ink-hero':''),null,bg);
    photo.src=a.src;photo.alt='';photo.dataset.asset=i;photo.dataset.background='photo';
    const echo=i===0&&['night','slate','sepia'].includes(style)?el('img','archive-bg-echo',null,bg):null;
    if(echo){echo.src=a.src;echo.alt='';echo.dataset.asset=i;echo.dataset.background='echo';}
    const at=entry(a,i),next=entry(pictures[i+1],i+1);
    tweens.push(t=>{
      const age=t-at,p=ease(age/.8),q=clamp(t/duration);
      const replaced=i<pictures.length-1?smooth((t-next)/.9):0;
      const opacity={slate:.27,map:.12,ink:.19,sepia:.18,glass:.46,album:.07,night:.21}[style];
      photo.style.opacity=t<=at?'0':String(opacity*p*(1-.90*replaced));
      const filter=style==='glass'?'blur(18px) saturate(.85) brightness(.62)':
        style==='ink'?'grayscale(1) contrast(.85) sepia(.25)':
        style==='sepia'?'sepia(.85) saturate(.65) blur(2px) contrast(1.1)':
        'grayscale(1) contrast(1.2) blur(1px)';
      photo.style.filter=filter;
      let camera=0;
      if(style==='map'&&!alt)for(let j=1;j<pictures.length;j++)camera+=smooth((t-entry(pictures[j],j))*speed/1.6)*w*.63;
      photo.style.transform=`translate3d(${dir*mix(25,-65,q)-camera*.10}px,${mix(25,-20,q)}px,0) scale(${mix(1.12,1.02,q)})`;
      if(echo){
        echo.style.opacity=t<=at?'0':String((style==='night'?.14:.10)*p);
        echo.style.filter='grayscale(1) contrast(1.15)';
        echo.style.transform=`translateX(${dir*36*q}px) scale(${1+.045*q})`;
      }
    });
  });
  const atmosphere=el('div','archive-atmosphere',null,bg);
  const grid=el('div','archive-grid',null,bg);
  el('div','archive-paper-fibre',null,bg);
  el('div','archive-scratches',null,bg);
  if(style==='ink'){el('div','archive-halftone',null,bg);el('div','archive-paper-edge',null,bg);}
  if(style==='sepia'){
    for(const box of [[.65,.0,.30,.7,14],[.0,.40,.35,.55,-14]]){
      const paper=el('div','archive-paper-prop',null,bg);
      place(paper,{left:box[0]*w,top:box[1]*h,width:box[2]*w,height:box[3]*h});paper.style.transform=`rotate(${box[4]}deg)`;
    }
  }
  if(style==='map')el('div','archive-field',null,bg);
  if(style==='glass'){
    const prism=el('div','archive-prism',null,bg);el('div','archive-glass-outline',null,bg);
    tweens.push(t=>{prism.style.transform=`translateX(${dir*mix(-90,90,clamp(t/duration))}px) rotate(-10deg)`;});
  }
  const line=svgNode('svg',{class:'archive-linework',viewBox:`0 0 ${w} ${h}`},bg);
  // Abstract editorial framing, not a map of real places or a fake scorecard.
  const accentPath=svgNode('path',{d:`M ${w*.05} ${h*.12} L ${w*.05} ${h*.05} L ${w*.18} ${h*.05} M ${w*.80} ${h*.86} L ${w*.95} ${h*.86} L ${w*.95} ${h*.73}`},line);
  const lineLength=accentPath.getTotalLength();accentPath.style.strokeDasharray=String(lineLength);
  tweens.push(t=>{accentPath.style.strokeDashoffset=String(lineLength*(1-ease(t/1.5)));grid.style.transform=`translateX(${dir*20*clamp(t/duration)}px) rotate(-8deg)`;});
  window.buildArchiveLayout(style,pictures,plane,world,
    {el,place,tweens,speed,w,h,duration,alt,mono,entry,svgNode,requested:d.archive_composition});
  tweens.push(t=>{
    const q=clamp(t/duration);
    world.style.opacity=String(1-clamp((t-(duration-.12))/.12));
    atmosphere.style.transform=`scale(${1+.03*q}) translateX(${dir*8*q}px)`;
  });
  if(style==='night'){
    const beam=el('div','archive-spotlight',null,world),bloom=el('div','archive-bloom',null,bg);
    tweens.push(t=>{
      const q=clamp(t/duration);beam.style.transform=`translateX(${dir*mix(-w*.30,w*.22,smooth(q))}px) rotate(${dir*mix(-10,7,q)}deg)`;
      beam.style.opacity=String(.4+.25*Math.sin(q*Math.PI));bloom.style.opacity=String(.55+.25*Math.sin(q*Math.PI));
    });
  } else if(style==='slate'||style==='sepia'){
    const light=el('div','archive-light',null,world);
    tweens.push(t=>{light.style.opacity=String(.25+.20*Math.sin(clamp(t/duration)*Math.PI));light.style.transform=`translateX(${dir*t*28}px)`;});
  }
  el('div','grain',null,world);el('div','vignette',null,world);
  const label=el('div','archive-caption fit',d.label||'',world);
  tweens.push(t=>{const p=ease((t-.2)/.7);label.style.opacity=String(p);label.style.clipPath=`inset(0 ${100*(1-p)}% 0 0)`;});
  return world;
};
