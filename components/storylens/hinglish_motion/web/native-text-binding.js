/* Timeline glue follows the recipes in the original registry fragments above. */
(() => {
  const classes={'bottom-up-letters':'hf-bottom-up-letters','text-stagger':'hf-transition-text-stagger','soft-blur-in':'hf-soft-blur-in','tracking-in':'hf-tracking-in'};
  const families={Bodoni:'NativeBodoni,serif',Georgia:'Georgia,serif',Inter:'MotionInter,Arial,sans-serif',Roboto:'MotionInter,Arial,sans-serif'};
  function enter(tl,host,name,time,size,color){
    const className=classes[name];if(!className)throw new Error('Motion reference text invalid: unsupported native component '+name);
    host.classList.add(className);
    window.hfNativeText.configure[name](host,{text:host.textContent,size,tone:color==='#ffffff'?'paper':'ink',unit:'letter',travel:'close',distance:'close',blur:'soft'});
    Object.assign(host.style,{fontSize:size+'px',fontFamily:host.dataset.family,fontWeight:host.dataset.weight,lineHeight:'1',letterSpacing:'0',maxWidth:'none',whiteSpace:'pre'});
    host.style.setProperty('--hf-stagger-ink',color);host.style.color=color;
    if(name==='bottom-up-letters')tl.to(host.querySelectorAll('.hf-bottom-up-letters-char'),{opacity:1,y:0,duration:.24,ease:'power2.out',stagger:.028},time);
    else if(name==='text-stagger'){
      const measure=document.createElement('canvas').getContext('2d');measure.font=host.dataset.weight+' '+size+'px '+host.dataset.family;
      Object.assign(host.style,{display:'inline-flex',flexWrap:'nowrap',gap:measure.measureText(' ').width+'px'});
      tl.fromTo(host.querySelectorAll('span'),{opacity:0,y:size*.28,filter:'blur(8px)'},{opacity:1,y:0,filter:'blur(0px)',duration:.36,stagger:.085,ease:'power3.out'},time);
    }else if(name==='soft-blur-in')tl.fromTo(host,{opacity:0,y:14,filter:'blur(8px)'},{opacity:1,y:0,filter:'blur(0px)',duration:.38,ease:'power3.out'},time);
    else tl.fromTo(host,{opacity:0,'--hf-tracking-value':'.12em',y:4},{opacity:1,'--hf-tracking-value':'.02em',y:0,duration:.65,ease:'power3.out'},time);
  }
  window.hfNativeText.groups=async(camera,groups,W,H,D,tl)=>{
    await Promise.all([document.fonts.load('400 100px NativeBodoni'),document.fonts.load('700 100px NativeBodoni'),document.fonts.load('700 100px NativeCondensed'),document.fonts.load('700 100px MotionInter')]);
    await document.fonts.ready;
    const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');ctx.fontKerning='none';
    for(const g of groups){
      const color=g.ink||'#111111';const rows=[];
      for(const [text,font,weight,size,effect,offset] of [[g.header,g.support_font,400,g.support_size,'soft-blur-in',0],[g.main,g.main_font,700,g.main_size,g.effect,.15],[g.footer,g.support_font,400,g.support_size,'text-stagger',.42]]){
        if(!text || (g.backdrop_led && text===g.main))continue;let px=size*W;const family=families[font]||families.Inter;
        ctx.font=weight+' '+px+'px '+family;let m=ctx.measureText(text);
        // Reserve the largest normal camera scale; transition-only punch zooms
        // may crop during the exit, but readable resting copy stays in-frame.
        const isMain=text===g.main;
        const available=W*Math.min(isMain?(g.main_width||.65):.76,2*Math.min(g.anchor_x-.08,.92-g.anchor_x));
        if(m.width>available){px*=available/m.width;ctx.font=weight+' '+px+'px '+family;m=ctx.measureText(text);}
        rows.push({text,family,weight,px,m,effect,offset,ink:(m.actualBoundingBoxAscent||px*.75)+(m.actualBoundingBoxDescent||px*.1)});
      }
      const gap=g.ink_gap/720*W,total=rows.reduce((s,r)=>s+r.ink,0)+gap*(rows.length-1);
      let y=g.anchor_y*H-total/2;
      const caption=document.createElement('div');caption.style.cssText='position:absolute;inset:0;pointer-events:none;';camera.append(caption);
      for(const r of rows){
        const box=document.createElement('div'),host=document.createElement('span');host.textContent=r.text;
        const base=(r.px+(r.m.fontBoundingBoxAscent||r.px*.8)-(r.m.fontBoundingBoxDescent||r.px*.2))/2;
        const top=y-base+(r.m.actualBoundingBoxAscent||r.px*.75);
        box.style.cssText=`position:absolute;left:${g.anchor_x*W-r.m.width/2}px;top:${top}px;width:${r.m.width+3}px;height:${r.px*1.4}px;overflow:visible;`;
        host.style.cssText=`font-family:${r.family};font-weight:${r.weight};font-size:${r.px}px;line-height:1;white-space:pre;font-kerning:none;display:inline-block;`;
        host.dataset.family=r.family;host.dataset.weight=String(r.weight);box.append(host);caption.append(box);
        enter(tl,host,r.effect,g.start+r.offset,r.px,color);y+=r.ink+gap;
      }
      if(!g.backdrop_led && rows.length){
        for(const photo of camera.querySelectorAll('.reference-photo-layout')){
          const shift=Math.max(0,y+H*.045-Number(photo.dataset.top));
          tl.to(photo,{y:shift,duration:g.start===0?0:.3,ease:'power2.inOut'},g.start);
        }
      }
      tl.set(caption,{opacity:1},g.start);tl.set(caption,{opacity:0},0);
      tl.to(caption,{opacity:1,duration:.02},g.start);
      tl.to(caption,{opacity:0,filter:'blur(6px)',y:-8,duration:.16,ease:'power2.in'},Math.max(g.start+.6,g.end-.16));
      const bg=document.createElement('div'),word=document.createElement('span');word.textContent=g.main.replace(/[.!?,]/g,'').toUpperCase();
      bg.style.cssText=`position:absolute;left:0;top:${(g.anchor_y-.12)*H}px;width:${W}px;height:${H*.42}px;display:flex;align-items:center;justify-content:center;opacity:0;overflow:visible;color:${color};`;
      word.style.cssText=`font-family:NativeCondensed,Impact,sans-serif;font-weight:700;font-size:${W*.72}px;line-height:1;white-space:nowrap;flex-shrink:0;transform-origin:center;`;
      bg.append(word);camera.insertBefore(bg,camera.firstChild);
      ctx.font='700 '+(W*.72)+'px NativeCondensed';const bw=ctx.measureText(word.textContent).width;
      word.style.transform=`scaleX(${Math.min(1,W*1.04/Math.max(1,bw))})`;
      tl.to(bg,{opacity:g.backdrop_opacity||.18,duration:.55},g.start);tl.to(bg,{opacity:0,duration:.15},Math.max(g.start+.6,g.end-.15));
    }
  };
})();
