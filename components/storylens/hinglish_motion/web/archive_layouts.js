/* Independent narrative structures. Background styling is deliberately separate
   from picture layout, camera path, and the way one image succeeds another. */
window.buildArchiveLayout=function(style,pictures,plane,world,api){
  const {el,place,tweens,speed,w,h,duration,alt,mono,entry,svgNode}=api;
  const clamp=x=>Math.max(0,Math.min(1,x));
  const ease=x=>1-Math.pow(1-clamp(x),3),smooth=x=>{const p=clamp(x);return p*p*(3-2*p);};
  const mix=(a,b,p)=>a+(b-a)*p,dir=alt?-1:1;
  const cue=i=>entry(pictures[i],i),after=(t,i,span=1)=>i<pictures.length?smooth((t-cue(i))*speed/span):0;
  const defaults={night:'cinema',slate:alt?'horizontal-reel':'vertical-reel',map:alt?'orbit':'road-travel',ink:'print-sheet',sepia:'evidence-fan',glass:'hinged-triptych',album:'turning-album'};
  const allowed=['cinema','horizontal-reel','vertical-reel','road-travel','orbit','print-sheet','evidence-fan','hinged-triptych','turning-album'];
  const composition=allowed.includes(api.requested)?api.requested:defaults[style];
  world.dataset.composition=composition;
  world.dataset.layoutRevision='independent-stories';
  world.classList.add('layout-'+composition);
  function photo(i,parent=plane,cls='archive-photo'){
    const a=pictures[i],card=el('div',cls,null,parent),img=el('img','',null,card);
    card.dataset.asset=i;card.dataset.motion=composition;img.src=a.src;img.alt='';
    card.style.zIndex=String(i+2);
    img.style.filter=mono?'grayscale(1) contrast(1.08)':style==='sepia'?'sepia(.45) saturate(.8)':'none';
    return {card,img,i};
  }
  function fit(item,b){
    const {card,img}=item,[x,y,bw,bh]=b,ratio=img.naturalWidth&&img.naturalHeight?img.naturalWidth/img.naturalHeight:1;
    const cw=Math.min(bw*w,bh*h*ratio),ch=cw/ratio;
    const left=x*w+(bw*w-cw)/2,top=y*h+(bh*h-ch)/2;
    place(card,{left,top,width:cw,height:ch});return {cw,ch,left,top};
  }
  function enter(item,t,span=.9){
    const age=(t-cue(item.i))*speed,p=ease(age/span);
    item.card.style.opacity=t<=cue(item.i)?'0':'1';return {age,p};
  }
  function inkReveal(item){
    const svg=svgNode('svg',{width:0,height:0,'aria-hidden':true},world);
    const defs=svgNode('defs',{},svg),id='print-mask-'+item.i;
    const clip=svgNode('clipPath',{id,clipPathUnits:'objectBoundingBox'},defs);
    const seeds=[[.2,.3,.42],[.68,.2,.4],[.5,.76,.46],[.88,.77,.35],[.1,.84,.3]];
    const shapes=seeds.map(([cx,cy,r],j)=>{
      const points=Array.from({length:100},(_,n)=>{
        const a=n/100*Math.PI*2,rr=r*(1+.035*Math.sin(n*.91+j)+.02*Math.cos(n*3));
        return `${cx+Math.cos(a)*rr},${cy+Math.sin(a)*rr}`;
      });
      return {cx,cy,j,path:svgNode('path',{d:'M'+points.join('L')+'Z'},clip)};
    });
    item.card.style.clipPath=`url(#${id})`;
    return p=>shapes.forEach(({cx,cy,j,path})=>path.setAttribute('transform',`translate(${cx} ${cy}) scale(${Math.max(.001,ease((p-j*.09)/(1-j*.09)))}) translate(${-cx} ${-cy})`));
  }
  const builders={};
  builders.cinema=()=>{
    pictures.forEach((_,i)=>{
      const item=photo(i);item.card.classList.add('cinema-picture');
      tweens.push(t=>{
        const {p}=enter(item,t,1.25),q=clamp((t-cue(i))/Math.max(1,duration-cue(i)));
        fit(item,[.025,.035,.95,.83]);
        const replaced=after(t,i+1,1.25);
        item.card.style.opacity=t<=cue(i)?'0':String(1-replaced);
        item.card.style.clipPath=alt?`inset(${48*(1-p)}% 0 ${48*(1-p)}% 0)`:`circle(${150*p}% at 50% 48%)`;
        item.card.style.transform=`scale(${mix(1.06,1,p)+.022*q}) rotate(${dir*.35*q}deg)`;
        item.card.style.filter=`blur(${4*(1-p)+5*replaced}px)`;
      });
    });
    tweens.push(t=>{plane.style.transform=`translateY(${-8*clamp(t/duration)}px)`;});
  };
  builders['vertical-reel']=()=>{
    const reel=el('div','vertical-film',null,plane);
    for(const side of ['left','right'])el('div','film-perforations '+side,null,reel);
    pictures.forEach((_,i)=>{
      const item=photo(i);
      tweens.push(t=>{
        const {p}=enter(item,t,1.1);
        fit(item,[.22,.08+dir*i*.96,.56,.70]);
        item.card.style.transform=`scale(${mix(.96,1,p)})`;
        item.card.style.filter=`blur(${2*(1-p)}px)`;
      });
    });
    el('div','film-gate',null,world);
    const exposure=el('div','film-exposure',null,world);
    tweens.push(t=>{
      let index=0,flash=0;
      for(let i=1;i<pictures.length;i++){
        index+=after(t,i,1.25);
        const age=(t-cue(i))*speed;
        flash+=age>0&&age<1.25?.20*Math.sin(age/1.25*Math.PI):0;
      }
      plane.style.transform=`translateY(${-dir*index*h*.96}px)`;
      exposure.style.opacity=String(flash);
      reel.style.transform=`translateY(${dir*index*h*.96}px)`;
    });
  };
  builders['horizontal-reel']=()=>{
    const width=.47*w,height=.67*h,step=.53*w,y=.10*h,x=.27*w;
    const strip=el('div','horizontal-film',null,plane);
    place(strip,{left:x-.035*w,top:y-.035*h,width:Math.max(1,pictures.length)*step,height:height+.07*h});
    pictures.forEach((_,i)=>{
      const frame=el('div','film-window',null,plane);
      place(frame,{left:x+i*step,top:y,width,height});
      frame.dataset.asset=i;
      const item=photo(i);
      tweens.push(t=>{
        const {p}=enter(item,t,1.1);fit(item,[(x+i*step)/w,y/h,width/w,height/h]);
        frame.style.opacity=t<=cue(i)?'0':'1';
        item.card.style.transform='none';item.card.style.filter=`blur(${2*(1-p)}px)`;
      });
    });
    tweens.push(t=>{
      let index=0;for(let i=1;i<pictures.length;i++)index+=after(t,i,1.45);
      plane.style.transform=`translateX(${-index*step}px)`;
    });
  };
  builders['road-travel']=()=>{
    const start=.28*w,step=.63*w,roadY=.72*h;
    const road=svgNode('svg',{class:'road-travel-path',viewBox:`0 0 ${w*(pictures.length+1)} ${h}`},plane);
    road.style.width=w*(pictures.length+1)+'px';
    const points=pictures.map((_,i)=>[start+i*step,roadY+(i%2?-.05:.03)*h]);
    let shape=`M ${start-.16*w} ${roadY}`;
    points.forEach(([x,y])=>{shape+=` Q ${x-.10*w} ${y+.10*h} ${x} ${y}`;});
    const line=svgNode('path',{d:shape,fill:'none',stroke:'#dfbc74','stroke-width':3},road);
    const length=line.getTotalLength();line.style.strokeDasharray=String(length);
    points.forEach(([cx,cy],i)=>{
      const marker=svgNode('circle',{cx,cy,r:9,fill:'#e6c284'},road);
      tweens.push(t=>{marker.style.opacity=t<=cue(i)?'0':String(ease((t-cue(i))/.7));});
    });
    pictures.forEach((_,i)=>{
      const item=photo(i),z=[30,-90,80,-30][i];
      tweens.push(t=>{
        const {p}=enter(item,t,1.2),q=clamp((t-cue(i))/Math.max(1,duration-cue(i)));
        fit(item,[(start+i*step)/w-.215,.12,.43,.53]);
        item.card.style.transform=`translate3d(0,${mix(45,0,p)}px,${z}px) rotateY(${mix(-10,0,p)}deg) rotate(${i%2?3:-3}deg)`;
        item.img.style.transform=`scale(${1+.015*q})`;
      });
    });
    tweens.push(t=>{
      let index=0;for(let i=1;i<pictures.length;i++)index+=after(t,i,1.6);
      const travelled=index*step;
      plane.style.transform=`translate3d(${-travelled}px,0,${25*Math.sin(index*Math.PI)}px)`;
      line.style.strokeDashoffset=String(length*(1-clamp((index+ease((t-cue(0))/1.2)+.25)/Math.max(1,pictures.length))));
      world.style.setProperty('--road-camera-x',String(travelled));
    });
  };
  builders.orbit=()=>{
    const ring=svgNode('svg',{class:'orbit-ring',viewBox:`0 0 ${w} ${h}`},plane);
    const path=svgNode('ellipse',{cx:w*.5,cy:h*.44,rx:w*.32,ry:h*.31,fill:'none',stroke:'#dcb879','stroke-width':2},ring);
    const len=path.getTotalLength();path.style.strokeDasharray=String(len);
    tweens.push(t=>{path.style.strokeDashoffset=String(len*(1-smooth(t/Math.max(2,cue(pictures.length-1)+1))));});
    pictures.forEach((_,i)=>{
      const item=photo(i);
      tweens.push(t=>{
        const {p}=enter(item,t,1.15),q=clamp(t/duration);
        let phase=dir*(5*q+12*after(t,1,1.3)+15*after(t,2,1.3));
        const angle=(-90+360*i/Math.max(3,pictures.length)+phase)*Math.PI/180;
        const cx=.5+Math.cos(angle)*.24*p,cy=.44+Math.sin(angle)*.22*p;
        fit(item,[cx-.155,cy-.19,.31,.38]);
        item.card.style.transform=`scale(${mix(.6,1,p)}) rotate(${dir*(i%2?2:-2)}deg)`;
      });
    });
    tweens.push(t=>{plane.style.transform=`rotateY(${dir*2*Math.sin(clamp(t/duration)*Math.PI)}deg)`;});
  };
  builders['print-sheet']=()=>{
    const sheet=el('div','print-sheet',null,plane);
    for(const c of ['tl','tr','bl','br'])el('div','print-register '+c,null,sheet);
    const boxes=alt?[[.12,.10,.31,.29],[.55,.49,.31,.29],[.55,.10,.31,.29],[.12,.49,.31,.29]]:
                   [[.55,.10,.31,.29],[.12,.49,.31,.29],[.12,.10,.31,.29],[.55,.49,.31,.29]];
    pictures.forEach((_,i)=>{
      const item=photo(i);item.card.classList.add('printed-picture');
      const reveal=inkReveal(item);
      tweens.push(t=>{
        const {p}=enter(item,t,1.4);fit(item,boxes[i]);reveal(p);
        item.card.style.transform='none';
        item.img.style.filter=(mono?'grayscale(1) ':'')+`contrast(${mix(1.5,1.05,p)}) brightness(${mix(.62,1,p)})`;
      });
    });
    tweens.push(t=>{plane.style.transform=`rotate(${dir*mix(5,0,smooth(t/duration))}deg) scale(${mix(1.03,1,clamp(t/duration))})`;});
  };
  builders['evidence-fan']=()=>{
    const pivot=el('div','evidence-pivot',null,plane);
    pictures.forEach((_,i)=>{
      const item=photo(i);item.card.style.zIndex=String(10-i);
      el('div','archive-tape',null,item.card);
      tweens.push(t=>{
        const {p}=enter(item,t,1.1),open=after(t,1,1.4);
        const spread=i===0?0:(i%2?-1:1);
        const fan=p*Math.min(1,open+.15);
        fit(item,[.30+spread*.20*fan,.08+(i===0?-.035*open:.12*fan),.40,.60]);
        item.card.style.transform=`rotate(${spread*mix(0,17,fan)}deg) rotateX(${mix(18,0,p)}deg)`;
      });
    });
    tweens.push(t=>{
      plane.style.transform=`scale(${mix(1.20,1,after(t,1,1.8))}) rotate(${dir*mix(-3,1,smooth(t/duration))}deg)`;
      pivot.style.opacity=String(after(t,1));
    });
  };
  builders['hinged-triptych']=()=>{
    const count=pictures.length,gap=.024,bw=(.86-(count-1)*gap)/Math.max(1,count);
    pictures.forEach((_,i)=>{
      const x=.07+i*(bw+gap),group=el('div','glass-hinge-group',null,plane);
      group.style.transformOrigin=`${(x+(i%2?bw:0))*w}px ${h*.43}px`;
      const door=el('div','glass-door',null,group);place(door,{left:x*w,top:h*.07,width:bw*w,height:h*.72});
      const item=photo(i,group);
      tweens.push(t=>{
        const {p}=enter(item,t,1.3);fit(item,[x+.01,.09,bw-.02,.68]);
        group.style.opacity=t<=cue(i)?'0':'1';
        group.style.transform=`rotateY(${dir*(i%2?-1:1)*mix(82,0,p)}deg)`;
        item.card.style.transform='none';
        door.style.opacity=String(p);
      });
    });
    const scanner=el('div','glass-focus-line',null,plane);
    tweens.push(t=>{
      let index=0;for(let i=1;i<pictures.length;i++)index+=after(t,i,1.3);
      scanner.style.left=(.07+bw*.5+index*(bw+gap))*100+'%';
      plane.style.transform=`rotateY(${dir*mix(-4,4,smooth(t/duration))}deg)`;
    });
  };
  builders['turning-album']=()=>{
    const book=el('div','archive-book',null,plane);
    const items=pictures.map((_,i)=>{
      const leaf=el('div','album-leaf',null,plane);leaf.style.zIndex=String(100-i);
      el('div','album-leaf-paper',null,leaf);
      const item=photo(i,leaf);
      for(const c of ['tl','tr','bl','br'])el('i','archive-photo-corner '+c,null,item.card);
      tweens.push(t=>{
        const {p}=enter(item,t,.8);fit(item,[.54,.17,.33,.49]);
        const turn=after(t,i+1,1.4);
        leaf.style.opacity=t<=cue(i)||turn>=.5?'0':'1';
        leaf.style.transform=`rotateY(${-178*turn}deg)`;
        item.card.style.transform=`scale(${mix(.94,1,p)})`;
      });
      return item;
    });
    items.forEach((_,i)=>{
      if(i===pictures.length-1)return;
      const memory=photo(i,plane,'archive-album-memory');memory.card.style.zIndex='2';
      for(const c of ['tl','tr','bl','br'])el('i','archive-photo-corner '+c,null,memory.card);
      tweens.push(t=>{
        fit(memory,[.12,.17,.33,.49]);
        const turned=after(t,i+1,1.4),retired=after(t,i+2,1.4);
        memory.card.style.opacity=t<=cue(i)||turned<.45?'0':String(1-retired);
        memory.card.style.transform=`rotate(${dir*(i%2?1:-1)}deg)`;
      });
    });
    tweens.push(t=>{plane.style.transform=`rotate(${dir*mix(-3,0,smooth(t/duration))}deg) rotateX(${mix(7,1,smooth(t/duration))}deg)`;});
  };
  builders[composition]();
  return composition;
};
