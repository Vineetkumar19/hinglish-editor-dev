/* Generic graphic objects, parent masks and independent model-authored tracks. */
(()=>{
 const stage=document.getElementById('stage');let timeline,errors=[],D;
 window.mgLoad=async payload=>{
  stage.replaceChildren();errors=[];const s=payload.data.scene,W=payload.width,H=payload.height;D=s.duration;
  stage.style.background=s.background;
  const region=document.createElement('div');region.style.cssText=`position:absolute;left:${W*.05}px;top:${H*.08}px;width:${W*.9}px;height:${H*.65}px;`;stage.append(region);
  const nodes=new Map(),specs=new Map(s.objects.map(o=>[o.id,o]));timeline=gsap.timeline({paused:true});window.__timelines={main:timeline};
  function build(id){
   if(nodes.has(id))return nodes.get(id);const o=specs.get(id),p=o.parent?build(o.parent):region;
   const pw=o.parent?Number(p.dataset.w):W*.9,ph=o.parent?Number(p.dataset.h):H*.65,w=o.w*pw,h=o.h*ph;
   const e=document.createElement('div');e.dataset.object=id;e.dataset.w=w;e.dataset.h=h;
   e.style.cssText=`position:absolute;left:0;top:0;width:${w}px;height:${h}px;background:${o.kind==='frame'?'transparent':o.fill};border:${o.stroke_width}px solid ${o.stroke};border-radius:${o.kind==='ellipse'?'50%':o.radius*pw+'px'};overflow:${o.clip?'hidden':'visible'};transform-origin:center;`;
   if(o.kind==='arrow')e.style.clipPath='polygon(0 30%,65% 30%,65% 0,100% 50%,65% 100%,65% 70%,0 70%)';
   if(o.kind==='star')e.style.clipPath='polygon(50% 0,62% 37%,100% 50%,62% 63%,50% 100%,38% 63%,0 50%,38% 37%)';
   p.append(e);nodes.set(id,e);
   if(o.label){const label=document.createElement('span');label.textContent=o.label;label.style.cssText=`position:absolute;inset:7%;display:flex;align-items:center;justify-content:center;color:${o.stroke};font:700 ${Math.max(14,Math.min(W*.04,w*.16,h*.27))}px MotionInter,Arial,sans-serif;text-align:center;overflow:hidden;`;e.append(label);}
   const pose=k=>({x:k.x*pw,y:k.y*ph,scale:k.scale,rotation:k.rotation,opacity:k.opacity});
   timeline.set(e,pose(o.keys[0]),0);
   for(let i=1;i<o.keys.length;i++){const a=o.keys[i-1],b=o.keys[i];timeline.to(e,{...pose(b),duration:(b.t-a.t)*D,ease:'power2.inOut'},a.t*D);}
   return e;
  }
  for(const o of s.objects)build(o.id);
  const rgb=s.background.slice(1).match(/../g).map(v=>parseInt(v,16)),ink=rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722>155?'#111111':'#ffffff';
  const cap=document.createElement('div');cap.textContent=s.caption;cap.style.cssText=`position:absolute;left:8%;right:8%;top:80%;height:15%;font:700 ${W*.045}px/1.2 MotionInter,Arial,sans-serif;color:${ink};text-align:center;display:flex;align-items:center;justify-content:center;`;stage.append(cap);
  await document.fonts.ready;let size=W*.045;while((cap.scrollHeight>cap.clientHeight+1||cap.scrollWidth>cap.clientWidth+1)&&size>W*.025){size-=1;cap.style.fontSize=size+'px';}
  if(cap.scrollHeight>cap.clientHeight+2||cap.scrollWidth>cap.clientWidth+2)errors.push('Caption does not fit');
  timeline.fromTo(cap,{opacity:0},{opacity:1,duration:.15},0);timeline.to(region,{opacity:0,duration:.12},D-.12);timeline.to(cap,{opacity:0,duration:.12},D-.12);timeline.set(stage,{opacity:1},D);
  timeline.time(0,false);if(errors.length)throw new Error('Element motion layout invalid: '+errors.join('; '));return true;
 };
 window.mgSeek=t=>timeline?.time(Math.max(0,Math.min(D,t)),false).pause();window.mgCheck=()=>errors;
 window.mgObjects=()=>[...stage.querySelectorAll('[data-object]')].map(e=>({id:e.dataset.object,transform:getComputedStyle(e).transform,opacity:getComputedStyle(e).opacity,rect:(()=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()}));
 window.addEventListener('hf-seek',e=>e.detail.waitUntil(Promise.resolve(window.__creativeReady).then(()=>window.mgSeek(e.detail.time))));
})();
