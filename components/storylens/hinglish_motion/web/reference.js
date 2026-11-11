/* Typed local-model layers; no model JavaScript, HTML, external URLs or event code. */
(() => {
  const stage=document.getElementById('stage');let timeline=null,scene=null,errors=[];
  const fonts={sans:'MotionInter,Arial,sans-serif',serif:'Georgia,serif',italic:'Georgia,serif',condensed:'Impact,Arial Narrow,sans-serif'};
  window.mgLoad=async payload=>{
    timeline?.kill();stage.replaceChildren();errors=[];scene=payload.data.reference_scene;
    const W=payload.width,H=payload.height,D=scene.duration;
    stage.style.background=scene.background;stage.style.color='#111';
    const camera=document.createElement('div');camera.style.cssText='position:absolute;inset:0;transform-origin:center;';stage.append(camera);
    timeline=gsap.timeline({paused:true});window.__timelines={main:timeline};
    const assets=Object.fromEntries(payload.data.assets.map(a=>[a.id,a.src]));
    const loaded=[];
    for(const layer of scene.layers){
      const element=document.createElement(layer.kind==='image'?'img':'div');
      element.style.cssText=`position:absolute;left:${layer.x*W}px;top:${layer.y*H}px;width:${layer.w*W}px;height:${layer.h*H}px;transform-origin:center;`;
      if(layer.kind==='image'){
        if(!assets[layer.asset])throw new Error('Motion reference asset missing: '+layer.asset);
        element.src=assets[layer.asset];element.style.objectFit='contain';
        loaded.push(element.decode());element.style.filter=`drop-shadow(${W*.012}px ${H*.012}px ${W*.018}px rgba(0,0,0,${layer.shadow}))`;
      }else if(layer.kind==='text'){
        element.textContent=layer.text;
        Object.assign(element.style,{fontFamily:fonts[layer.font],fontWeight:String(layer.weight),fontStyle:layer.font==='italic'?'italic':'normal',
          fontSize:layer.size*W+'px',color:layer.color,textAlign:layer.align,lineHeight:'1.04',whiteSpace:'pre-wrap',overflowWrap:'normal',
          display:'flex',alignItems:'center',justifyContent:layer.align==='center'?'center':layer.align==='right'?'flex-end':'flex-start'});
      }else{
        element.style.background=layer.color;
        if(layer.kind==='ellipse')element.style.borderRadius='50%';
        if(layer.kind==='star')element.style.clipPath='polygon(50% 0,58% 40%,100% 50%,58% 58%,50% 100%,42% 58%,0 50%,42% 40%)';
        if(layer.shadow)element.style.boxShadow=`${W*.02}px ${H*.02}px ${W*.03}px rgba(0,0,0,${layer.shadow})`;
      }
      if(layer.kind==='image' && scene.motion_tracks){
        const layout=document.createElement('div');layout.className='reference-photo-layout';layout.dataset.top=String(layer.y*H);layout.style.cssText='position:absolute;inset:0;';camera.append(layout);
        const carrier=document.createElement('div');carrier.style.cssText='position:absolute;inset:0;transform-origin:50% 65%;';carrier.append(element);layout.append(carrier);
        const m=scene.motion_tracks.image;
        timeline.fromTo(carrier,{x:-m.x*W*.25,y:-m.y*H*.25,scale:1,rotation:0},{x:m.x*W,y:m.y*H,scale:m.scale,rotation:m.rotation,duration:D,ease:'none'},0);
      }else camera.append(element);
      if(layer.kind==='text'){
        await document.fonts.ready;let size=layer.size*W;const minimum=Math.max(12,size*.52);
        while((element.scrollWidth>element.clientWidth+2||element.scrollHeight>element.clientHeight+2)&&size>minimum){size-=1;element.style.fontSize=size+'px';}
        if(element.scrollWidth>element.clientWidth+2||element.scrollHeight>element.clientHeight+2)errors.push('Text does not fit: '+layer.text);
      }
      timeline.set(element,{opacity:0,x:layer.travel_x*W,y:layer.travel_y*H,scale:layer.scale_from,rotation:layer.rotation},0);
      timeline.to(element,{opacity:layer.opacity,x:0,y:0,scale:1,duration:layer.enter,ease:'power3.out'},layer.delay);
      const settled=layer.delay+layer.enter;
      timeline.to(element,{x:layer.drift_x*W,y:layer.drift_y*H,duration:Math.max(.1,D-settled),ease:'none'},settled);
      if(layer.end && layer.end<D-.1)timeline.to(element,{opacity:0,duration:.12},layer.end-.12);
    }
    await Promise.all(loaded);
    if(scene.text_groups)await window.hfNativeText.groups(camera,scene.text_groups,W,H,D,timeline);
    if(scene.motion_tracks){
      const motion=scene.motion_tracks,keys=motion.camera;
      timeline.set(camera,{scale:keys[0].scale,x:keys[0].x*W,y:keys[0].y*H},0);
      for(let i=1;i<keys.length;i++){const a=keys[i-1],b=keys[i];timeline.to(camera,{scale:b.scale,x:b.x*W,y:b.y*H,duration:b.time-a.time,ease:i===keys.length-1&&keys.length>2?'power3.in':'none'},a.time);}
      if(motion.light_sweep){
        const light=document.createElement('div');light.style.cssText=`position:absolute;inset:-50%;pointer-events:none;background:linear-gradient(125deg,transparent 25%,rgba(0,0,0,.18) 38%,rgba(255,255,255,.24) 48%,transparent 57%,rgba(0,0,0,.10) 65%,transparent 77%);filter:blur(${W*.025}px);mix-blend-mode:soft-light;`;stage.append(light);
        timeline.fromTo(light,{x:-W*.3,y:-H*.08},{x:W*.3,y:H*.08,duration:D,ease:'sine.inOut'},0);
      }
      for(let i=0;i<motion.particles;i++){
        const dust=document.createElement('i'),x=((i*173+29)%997)/997,y=((i*281+71)%991)/991;
        dust.style.cssText=`position:absolute;left:${x*W}px;top:${y*H}px;width:${W*.003}px;height:${W*.006}px;background:#fff;border-radius:50%;pointer-events:none;filter:blur(.7px);`;
        stage.append(dust);timeline.fromTo(dust,{x:0,y:0,opacity:.08},{x:W*(.06+(i%3)*.025),y:-H*(.08+(i%4)*.02),opacity:.42,duration:D,ease:'none'},0);
      }
      if(motion.transition==='zoom-blur')timeline.to(camera,{filter:'blur(9px)',duration:.23,ease:'power2.in'},D-.23);
      else if(motion.transition==='slide-blur')timeline.to(camera,{x:-W*.18,filter:'blur(7px)',duration:.25,ease:'power3.in'},D-.25);
    }else timeline.fromTo(camera,{scale:scene.camera_start},{scale:scene.camera_end,duration:D,ease:'none'},0);
    timeline.to(camera,{opacity:0,duration:.12,ease:'power1.in'},D-.12);
    if(errors.length)throw new Error('Motion reference layout invalid: '+errors.join('; '));
    timeline.totalTime(0,false);return true;
  };
  window.mgSeek=t=>timeline?.totalTime(Math.max(0,Math.min(scene.duration,t)),false);
  window.mgCheck=()=>errors;
  window.addEventListener('hf-seek',e=>e.detail.waitUntil(Promise.resolve(window.__creativeReady).then(()=>window.mgSeek(e.detail.time))));
})();
