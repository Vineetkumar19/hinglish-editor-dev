/* Deterministic documentary choreography. All entrances use source seconds,
   independently of speed; every frame can be sought without playback history. */
window.buildArchiveMotion = function(root, d, api) {
  const {el, place, tweens, speed, landscape:L} = api;
  const w=L?1920:1080, h=L?1080:1920, duration=d.duration;
  const style=d.archive_style||'slate', variant=Number(d.archive_variant)||0;
  const alt=variant%2===1, dir=alt?-1:1;
  const clamp=x=>Math.max(0,Math.min(1,x));
  const ease=x=>1-Math.pow(1-clamp(x),3);
  const mix=(a,b,p)=>a+(b-a)*p;
  const world=el('div','archive-world '+style,null,root);
  world.dataset.motion=style+'-'+(alt?'alternate':'primary');
  if(d.archive_grade==='monochrome')world.classList.add('monochrome');
  const grade=d.archive_grade==='monochrome'?'grayscale(1) contrast(1.08) ':'';
  const plane=el('div','archive-plane',null,world);
  const pictures=(d.assets||[]).slice(0,4);
  const entry=(a,i)=>Number.isFinite(a.enter_at)?Math.max(0,a.enter_at):i*1.35;
  const svgNS='http://www.w3.org/2000/svg';
  function svgNode(tag,attrs,parent){
    const node=document.createElementNS(svgNS,tag);
    Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,String(v)));
    if(parent)parent.appendChild(node);return node;
  }
  function mask(node, id, seeds) {
    const svg=svgNode('svg',{width:0,height:0,'aria-hidden':'true'},world);
    svg.style.position='absolute';
    const clip=svgNode('clipPath',{id,clipPathUnits:'objectBoundingBox'},svg);
    const paths=seeds.map(([cx,cy,r],j)=>{
      let points=[];
      for(let n=0;n<100;n++){
        const a=n/100*Math.PI*2;
        const rr=r*(1+.045*Math.sin(n*2.8+j)+.055*Math.sin(n*.71+j*3));
        points.push(`${cx+Math.cos(a)*rr},${cy+Math.sin(a)*rr}`);
      }
      const path=svgNode('path',{d:'M'+points.join('L')+'Z'},clip);
      return {path,cx,cy,j};
    });
    node.style.clipPath=`url(#${id})`;
    return p=>paths.forEach(({path,cx,cy,j})=>{
      const k=ease(clamp((p-j*.075)/(1-j*.075)));
      path.setAttribute('transform',`translate(${cx} ${cy}) scale(${Math.max(.001,k)}) translate(${-cx} ${-cy})`);
    });
  }
  const layouts={
    slate:alt?[[.02,.18,.37,.55,-5,40],[.40,.14,.38,.57,4,60],[.80,.20,.37,.55,-3,90],[.27,.52,.3,.34,5,-40]]:
      [[.06,.12,.47,.66,-5,30],[.55,.18,.38,.57,6,-50],[.36,.17,.43,.63,-2,140],[.12,.60,.25,.29,3,70]],
    map:[[.08,.12,.35,.49,-7,40],[.46,.13,.31,.48,6,10],[.29,.39,.37,.48,-3,100],[.72,.40,.23,.33,7,40]],
    ink:[[.06,.16,.35,.56,-4,30],[.43,.10,.41,.58,3,80],[.57,.37,.35,.46,-5,110],[.22,.56,.25,.29,4,60]],
    sepia:[[.29,.08,.42,.66,-3,60],[.05,.30,.34,.48,-8,120],[.64,.22,.31,.52,7,90],[.43,.60,.23,.3,3,150]],
    glass:[[.09,.12,.43,.65,0,80],[.55,.10,.35,.54,0,-40],[.39,.33,.43,.52,0,140],[.05,.55,.26,.31,0,90]],
    album:[[.12,.17,.32,.50,-5,0],[.53,.15,.32,.48,4,10],[.52,.21,.35,.49,-3,100],[.14,.52,.24,.3,5,30]],
    night:[[.10,.13,.40,.64,-3,50],[.54,.13,.34,.58,4,30],[.34,.19,.41,.62,-2,100],[.68,.56,.23,.3,6,140]]
  };
  const boxes=L?layouts[style]:[[.1,.08,.65,.34,-4,50],[.2,.38,.67,.33,4,100],[.1,.65,.65,.29,-3,140],[.66,.12,.28,.24,3,10]];
  if(style==='map'){
    const map=el('div','archive-map',null,world);world.insertBefore(map,plane);
    const svg=svgNode('svg',{viewBox:`0 0 ${w} ${h}`,class:'archive-route'},plane);
    const centres=boxes.slice(0,pictures.length).map(b=>[(b[0]+b[2]/2)*w,(b[1]+b[3]/2)*h]);
    const path=svgNode('path',{d:centres.map(([x,y],i)=>(i?'L':'M')+x+' '+y).join(' '),fill:'none',stroke:'#d6c694','stroke-width':3,'stroke-dasharray':'12 8'},svg);
    const length=path.getTotalLength();path.style.strokeDasharray=String(length);
    tweens.push(t=>{path.style.strokeDashoffset=String(length*(1-clamp(t/(entry(pictures.at(-1)||{},2)+.7))));});
    centres.forEach(([cx,cy],i)=>{
      const dot=svgNode('circle',{cx,cy,r:13,fill:'#d8c6a0'},svg);
      tweens.push(t=>{dot.style.opacity=String(clamp((t-entry(pictures[i],i)+.15)*4));});
    });
  }
  if(style==='slate'&&alt){
    const strip=el('div','archive-filmstrip',null,plane);place(strip,{left:-w*.12,top:h*.10,width:w*1.48,height:h*.68});
  }
  if(style==='sepia')el('div','archive-writing',Array(16).fill(d.label||'Archive').join('   '),world);
  if(style==='album'){
    const book=el('div','archive-book',null,world);world.insertBefore(book,plane);
    // The turn is timed with the third photograph, rather than an empty turn at frame zero.
    const page=el('div','archive-page',null,world);
    const turn=entry(pictures[2]||{},2)-.4;
    tweens.push(t=>{
      const p=ease((t-turn)/1.05);
      page.style.opacity=t<turn?'0':String(1-clamp((p-.85)/.15));
      page.style.transform=alt?`rotateX(${-178*p}deg)`:`rotateY(${-178*p}deg)`;
    });
  }
  if(style==='ink'&&pictures[0]?.src){
    const hero=el('img','archive-ink-hero',null,world);world.insertBefore(hero,plane);hero.src=pictures[0].src;hero.alt='';
    const reveal=mask(hero,'archive-hero-mask',[[.24,.35,.28],[.55,.57,.34],[.75,.25,.26],[.14,.74,.22],[.87,.70,.25],[.51,.17,.22]]);
    const at=entry(pictures[0],0);
    tweens.push(t=>{
      const age=(t-at)*speed,p=clamp(age/1.6);reveal(p);
      hero.style.opacity=t<=at?'0':String(.34*clamp(age*4));
      hero.style.filter=grade+'blur('+mix(3,0,p)+'px)';
      hero.style.transform=`scale(${1+.06*clamp(t/duration)})`;
      if(alt)hero.style.clipPath=`polygon(0 3%,${Math.min(100,p*145)}% 0,${Math.min(100,p*145)}% 97%,0 100%)`;
    });
  }
  if(style==='night'&&pictures[0]?.src){
    const hero=el('img','archive-night-hero',null,world);world.insertBefore(hero,plane);hero.src=pictures[0].src;hero.alt='';
    tweens.push(t=>{hero.style.opacity=t<=entry(pictures[0],0)?'0':'.16';hero.style.transform=`translateX(${-35*clamp(t/duration)}px) scale(${1+.08*clamp(t/duration)})`;});
  }
  pictures.forEach((a,i)=>{
    const [x,y,bw,bh,rotation,z]=boxes[i], at=entry(a,i), role=(i+(alt?1:0))%3;
    const card=el('div','archive-photo',null,plane);card.dataset.motion=style+'-'+role+'-'+variant;
    place(card,{left:x*w,top:y*h,width:bw*w,height:bh*h});
    const img=el('img','',null,card);img.src=a.src;img.alt='';
    let reveal=null, bands=[];
    if(style==='ink'&&role===1)reveal=mask(card,'archive-card-mask-'+i,[[.30,.28,.36],[.67,.53,.45],[.21,.80,.37],[.81,.15,.30],[.82,.86,.31]]);
    if(style==='glass'&&role===0){
      img.style.opacity='0';
      for(let j=0;j<5;j++){
        const band=el('div','archive-glass-band',null,card);
        const clone=el('img','',null,band);clone.src=a.src;clone.alt='';
        band.style.clipPath=alt?`inset(${j*20}% 0 ${80-j*20}% 0)`:`inset(0 ${80-j*20}% 0 ${j*20}%)`;
        bands.push(band);
      }
    }
    if(style==='sepia')el('div','archive-tape',null,card);
    if(style==='album')for(const corner of ['tl','tr','bl','br'])el('i','archive-photo-corner '+corner,null,card);
    if(style==='map'&&role===0)card.style.transformOrigin='25% 80%';
    if(style==='album')card.style.transformOrigin=role===1?'left center':'center top';
    tweens.push(t=>{
      const age=(t-at)*speed,p=ease(age/.92), hold=clamp((t-at)/Math.max(1,duration-at));
      // Each slot has a different entrance. A new variant changes both this order and camera path.
      let tx=0,ty=0,rz=rotation,rx=0,ry=0,tz=z,sc=1,blur=0,clip='none';
      if(style==='slate'){
        if(role===0){tz=mix(-900,z,p);ry=mix(alt?24:-32,0,p);sc=mix(.65,1,p);blur=10*(1-p);}
        if(role===1){tx=dir*mix(w*.75,0,p);rz=mix(rotation+18,rotation,p);blur=7*(1-p);}
        if(role===2){ty=mix(-h*.65,0,p);rx=mix(-48,0,p);sc=mix(1.35,1,p);}
        ty+=i%2?hold*18:-hold*14;
      } else if(style==='map'){
        if(role===0){sc=mix(1.7,1,p);rz=mix(rotation-19,rotation,p);blur=5*(1-p);}
        if(role===1){clip=`inset(0 ${100*(1-p)}% 0 0)`;tx=dir*45*(1-p);}
        if(role===2){ry=mix(82,0,p);tz=mix(350,z,p);}
      } else if(style==='ink'){
        if(role===0){clip=alt?`inset(${100*(1-p)}% 0 0 0)`:`polygon(0 0,${100*p}% 2%,${100*p}% 100%,0 97%)`;sc=1+.06*hold;}
        if(role===1)reveal(p);
        if(role===2){clip=`inset(${48*(1-p)}% ${8*(1-p)}% ${48*(1-p)}% 0)`;rz=mix(rotation+11,rotation,p);ty=30*(1-p);}
      } else if(style==='sepia'){
        if(role===0){sc=mix(.82,1,p);rz=mix(rotation-12,rotation,p);}
        if(role===1){tx=dir*mix(-w*.68,0,p);ry=mix(-12,0,p);}
        if(role===2){rx=mix(-86,0,p);ty=mix(h*.14,0,p);}
        tz+=Math.sin(hold*Math.PI)*22;
      } else if(style==='glass'){
        card.style.clipPath='none';
        if(role===0)bands.forEach((band,j)=>{
          const bp=ease((age-j*.065)/.6);
          band.style.transform=alt?`translateX(${(j%2?1:-1)*260*(1-bp)}px)`:`translateY(${(j%2?1:-1)*220*(1-bp)}px)`;
          band.style.opacity=String(clamp((age-j*.065)*8));
        });
        if(role===1){clip=alt?`inset(0 ${50*(1-p)}% 0 ${50*(1-p)}%)`:`inset(${50*(1-p)}% 0 ${50*(1-p)}% 0)`;ry=mix(-18,0,p);}
        if(role===2){blur=18*(1-p);tz=mix(-400,z,p);sc=mix(1.12,1,p);}
      } else if(style==='album'){
        if(role===0){ry=mix(-72,0,p);tz=mix(190,z,p);}
        if(role===1){tx=mix(-w*.25,0,p);rz=mix(22,rotation,p);sc=mix(.8,1,p);}
        if(role===2){alt?rx=mix(-94,0,p):ry=mix(-100,0,p);card.style.zIndex='5';}
      } else if(style==='night'){
        if(role===0){blur=22*(1-p);sc=mix(1.13,1,p);}
        if(role===1){clip=`inset(0 ${100*(1-p)}% 0 0)`;tx=dir*20*(1-p);}
        if(role===2){tz=mix(-700,z,p);ry=mix(alt?-22:22,0,p);}
        const dim=clamp((t-at-1.6)/1.6);
        img.style.filter=grade+`brightness(${1-.38*dim})`;
      }
      card.style.opacity=t<=at?'0':String(clamp(age*6));
      card.style.transform=`translate3d(${tx}px,${ty}px,${tz}px) rotateX(${rx}deg) rotateY(${ry}deg) rotate(${rz}deg) scale(${sc})`;
      card.style.filter=`blur(${blur}px)`;
      if(!reveal)card.style.clipPath=clip;
      if(style==='glass'&&role!==0)card.style.clipPath=clip;
      if(style!=='night')img.style.transform=`scale(${1+(.035+i*.012)*hold}) translate(${(i%2?1:-1)*hold*9}px,${-hold*4}px)`;
    });
  });
  // Distinct camera choreography: rail, overhead map, paper drift, orbit, glass
  // plane exchange, overhead album, and a slow dramatic push.
  tweens.push(t=>{
    const q=clamp(t/duration), e=ease(q), swing=Math.sin(q*Math.PI);
    let transform='';
    if(style==='slate')transform=alt?`translate3d(${mix(w*.12,-w*.30,ease((t-.8)/(duration-.8)))}px,0,${80*q}px) rotateY(${dir*4*swing}deg) scale(${1+.1*swing})`:
      `translate3d(${dir*mix(65,-75,e)}px,${-15*swing}px,${120*q}px) rotateY(${mix(-7,5,q)}deg) scale(${1+.05*q})`;
    if(style==='map')transform=`translate3d(${dir*30*swing}px,${mix(45,-20,e)}px,0) rotate(${dir*mix(-5,2,e)}deg) scale(${mix(1.19,.98,e)})`;
    if(style==='ink')transform=`translate3d(${dir*22*q}px,${-15*q}px,0) rotate(${dir*1.6*swing}deg) scale(${1+.04*q})`;
    if(style==='sepia')transform=`translate3d(${dir*70*Math.sin(q*2.2)}px,${-25*swing}px,${80*q}px) rotateY(${dir*mix(9,-7,e)}deg) rotateX(${3*swing}deg)`;
    if(style==='glass')transform=`translate3d(${dir*mix(-50,50,e)}px,0,${100*swing}px) rotateY(${dir*mix(-5,4,e)}deg) scale(${1+.035*q})`;
    if(style==='album')transform=`translate3d(${dir*20*q}px,${-25*q}px,0) rotateX(${mix(10,0,e)}deg) rotate(${mix(-5,-1,e)}deg) scale(${mix(1.08,1,e)})`;
    if(style==='night')transform=`translate3d(${dir*mix(30,-25,e)}px,${-10*q}px,${180*q}px) scale(${1+.06*q})`;
    const end=clamp((t-(duration-.5))/.5);
    if(style==='slate'&&end)transform+=` translateX(${-dir*170*end}px)`;
    if(style==='album'&&end)transform+=` rotateY(${-dir*20*end}deg)`;
    plane.style.transform=transform;
    world.style.opacity=String(1-end);
  });
  if(style==='night'){
    const beam=el('div','archive-spotlight',null,world);
    tweens.push(t=>{
      const q=clamp(t/duration);beam.style.transform=`translateX(${dir*mix(-w*.45,w*.4,ease(q))}px) rotate(${dir*mix(-12,10,q)}deg)`;
      beam.style.opacity=String(.35+.23*Math.sin(q*Math.PI));
    });
  } else if(style!=='ink'&&style!=='glass'){
    const light=el('div','archive-light',null,world);
    tweens.push(t=>{light.style.opacity=String(Math.max(0,.45*Math.sin((t-1)*Math.PI/1.8)));light.style.transform=`translateX(${dir*t*45}px)`;});
  }
  el('div','grain',null,world);el('div','vignette',null,world);
  const label=el('div','archive-caption fit',d.label||'',world);
  tweens.push(t=>{const p=ease((t-.3)/.6);label.style.opacity=String(p);label.style.clipPath=`inset(0 ${100*(1-p)}% 0 0)`;});
  return world;
};
