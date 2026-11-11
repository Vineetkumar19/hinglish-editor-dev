/* Teacher-authored editable layers and explicit tracks, not model preset IDs. */
(()=>{
 const stage=document.getElementById('stage');let tl,plan,design,world,errors=[];
 const ink='#080b0e',teal='#009f9d';
 function node(tag,parent,css=''){const e=document.createElement(tag);e.style.cssText=css;parent.append(e);return e;}
 function threeWorld(parent,W,H,images){
  const renderer=new THREE.WebGLRenderer({alpha:false,antialias:true,preserveDrawingBuffer:true});renderer.setSize(W,H);renderer.setPixelRatio(1);
  renderer.domElement.style.cssText='position:absolute;inset:0;width:100%;height:100%;';parent.append(renderer.domElement);
  const scene=new THREE.Scene();scene.background=new THREE.Color('#03050a');const camera=new THREE.PerspectiveCamera(42,W/H,.1,100);camera.position.set(0,0,9);
  const light=new THREE.PointLight(0xffb24a,5,40);light.position.set(-3,4,5);scene.add(light);scene.add(new THREE.AmbientLight(0x8097bb,.65));
  const stars=new THREE.BufferGeometry(),positions=[];for(let i=0;i<1300;i++){const n=i*2.39996,r=1+(i%170)/12;positions.push(Math.cos(n)*r,Math.sin(n)*r,(i%61)/6-16);}stars.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  const starfield=new THREE.Points(stars,new THREE.PointsMaterial({color:0xcde0ef,size:.021,transparent:true,opacity:.8}));scene.add(starfield);
  const hole=new THREE.Group();scene.add(hole);const black=new THREE.Mesh(new THREE.SphereGeometry(.83,32,24),new THREE.MeshBasicMaterial({color:0x000000}));hole.add(black);
  for(let i=0;i<9;i++){const ring=new THREE.Mesh(new THREE.TorusGeometry(1.0+i*.07,.018+(9-i)*.006,8,90),new THREE.MeshBasicMaterial({color:new THREE.Color().setHSL(.07+i*.006,1,.48),transparent:true,opacity:1-i*.08}));ring.rotation.x=1.18;ring.rotation.z=.3;hole.add(ring);}
  const galaxy=new THREE.Group();scene.add(galaxy);for(let i=0;i<6;i++){const r=new THREE.Mesh(new THREE.TorusGeometry(.5+i*.18,.012,5,100),new THREE.MeshBasicMaterial({color:i%2?0xff6010:0xffca60,transparent:true,opacity:.45}));r.rotation.x=.2+i*.12;galaxy.add(r);}
  const core=new THREE.Mesh(new THREE.SphereGeometry(.22,20,14),new THREE.MeshBasicMaterial({color:0xfff4b7}));galaxy.add(core);
  const planet=new THREE.Group();scene.add(planet);
  const vertex='varying vec3 v;varying vec3 n;void main(){v=position;n=normal;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}';
  const fragment='varying vec3 v;varying vec3 n;uniform float phase;void main(){float land=sin(v.x*9.+sin(v.y*12.))*sin(v.z*8.+v.y*3.);vec3 ocean=vec3(.025,.12,.23),rock=vec3(.26,.28,.23);vec3 c=mix(ocean,rock,smoothstep(-.15,.25,land));float lit=.25+.75*max(0.,dot(normalize(n),normalize(vec3(-.5,.8,1.))));float cracks=pow(1.-abs(sin(v.x*18.+v.z*13.)*sin(v.y*17.)),20.);c=c*lit+vec3(1.,.12,.005)*cracks*phase;gl_FragColor=vec4(c,1.);}';
  const pm=new THREE.ShaderMaterial({vertexShader:vertex,fragmentShader:fragment,uniforms:{phase:{value:0}}});
  const half1=new THREE.Mesh(new THREE.SphereGeometry(1.55,48,32,0,Math.PI),pm),half2=new THREE.Mesh(new THREE.SphereGeometry(1.55,48,32,Math.PI,Math.PI),pm);planet.add(half1,half2);
  const molten=new THREE.Mesh(new THREE.SphereGeometry(1.22,32,24),new THREE.MeshBasicMaterial({color:0xff630b}));planet.add(molten);
  const debris=[];for(let i=0;i<55;i++){const m=new THREE.Mesh(new THREE.TetrahedronGeometry(.035+(i%5)*.022),new THREE.MeshStandardMaterial({color:i%3?0x716252:0xff7b10,roughness:.8,emissive:i%3?0x000000:0x7f1900}));planet.add(m);debris.push(m);}
  const actor=new THREE.Group();scene.add(actor);const white=new THREE.MeshBasicMaterial({color:0xd8ffff});
  function limb(parent,x,y,z,r,len){const pivot=new THREE.Group();pivot.position.set(x,y,z);parent.add(pivot);const mesh=new THREE.Mesh(new THREE.CylinderGeometry(r*.85,r,len,12),white);mesh.position.y=-len/2;pivot.add(mesh);return pivot;}
  const torso=new THREE.Mesh(new THREE.CylinderGeometry(.28,.22,.9,16),white);torso.position.y=.65;actor.add(torso);
  const head=new THREE.Mesh(new THREE.SphereGeometry(.22,20,16),white);head.position.y=1.36;actor.add(head);
  const la=limb(actor,-.28,1.02,0,.075,.73),ra=limb(actor,.28,1.02,0,.075,.73),ll=limb(actor,-.14,.23,0,.10,.98),rl=limb(actor,.14,.23,0,.10,.98);
  const fireMat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{time:{value:0},strength:{value:0}},vertexShader:'varying vec2 uv0;void main(){uv0=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',fragmentShader:'varying vec2 uv0;uniform float time;uniform float strength;float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1)),f.x),f.y);}void main(){vec2 p=uv0*vec2(6.,5.);float a=noise(p+vec2(0,-time*1.7));a+=noise(p*2.+vec2(time*.2,-time*2.7))*.5;float flame=smoothstep(.65,1.25,a+(1.-uv0.y)*.55);vec3 col=mix(vec3(.5,.035,.002),vec3(1.,.62,.08),pow(flame,2.));gl_FragColor=vec4(col,flame*strength*.9);}'});
  const fire=new THREE.Mesh(new THREE.PlaneGeometry(8,14),fireMat);fire.position.z=-2;scene.add(fire);
  const plateCanvas=document.createElement('canvas');plateCanvas.width=720;plateCanvas.height=1280;const plateContext=plateCanvas.getContext('2d');
  const plateTexture=new THREE.CanvasTexture(plateCanvas);const plate=new THREE.Mesh(new THREE.PlaneGeometry(4.25,7.56),new THREE.MeshBasicMaterial({map:plateTexture}));scene.add(plate);
  const poseCanvas=document.createElement('canvas');poseCanvas.width=360;poseCanvas.height=640;const poseContext=poseCanvas.getContext('2d');const poseTexture=new THREE.CanvasTexture(poseCanvas);
  const pose=new THREE.Mesh(new THREE.PlaneGeometry(3.98,7.08),new THREE.MeshBasicMaterial({map:poseTexture,transparent:true,depthWrite:false}));pose.position.z=.15;scene.add(pose);
  function render(t,mode,settings={},start=0,end=1){
   renderer.domElement.style.display=mode?'block':'none';if(!mode)return;
   hole.visible=mode==='blackhole';galaxy.visible=mode==='galaxy';planet.visible=mode==='planet';actor.visible=mode==='walker'||mode==='fire';fire.visible=mode==='fire';
   const plateName={blackhole:'cosmos',galaxy:'galaxy',planet:'planet',fire:'fire'}[mode];
   plate.visible=!!plateName;if(plateName&&images['plate-'+plateName]){
    const elapsed=t-({blackhole:9.11,galaxy:10.24,planet:10.94,fire:13.73}[mode]||0);
    plateContext.save();plateContext.translate(360,640);if(mode==='fire'){plateContext.rotate(Math.sin(elapsed*.9)*.025);plateContext.scale(1.10+elapsed*.025,1.10+elapsed*.02);}
    plateContext.drawImage(images['plate-'+plateName],-360,-640,720,1280);plateContext.restore();plateTexture.needsUpdate=true;
    const phase=Math.max(0,Math.min(1,(t-start)/Math.max(.01,end-start)));
    plate.scale.setScalar(settings.plate_scale_from!=null?settings.plate_scale_from+(settings.plate_scale_to-settings.plate_scale_from)*phase:1+Math.max(0,elapsed)*.025);
   }
   hole.visible=false;galaxy.visible=false;fire.visible=false;
   half1.visible=false;half2.visible=false;molten.visible=false;
   pose.visible=mode==='walker'||mode==='fire';actor.visible=false;
   if(pose.visible){const i=Math.max(0,Math.min(86,Math.floor((t-12.5)*30))),key='actor-'+String(i).padStart(3,'0');poseContext.clearRect(0,0,360,640);if(images[key])poseContext.drawImage(images[key],0,0,360,640);poseTexture.needsUpdate=true;pose.position.x=Math.sin((t-12.5)*.6)*.025;}
   starfield.rotation.z=t*.018;camera.position.set(Math.sin(t*.22)*.15,0,9);camera.lookAt(0,0,0);
   if(settings.camera_z_from!=null){const phase=Math.max(0,Math.min(1,(t-start)/Math.max(.01,end-start)));camera.position.set(settings.camera_x_from+(settings.camera_x_to-settings.camera_x_from)*phase,0,settings.camera_z_from+(settings.camera_z_to-settings.camera_z_from)*phase);camera.lookAt(0,0,0);pose.scale.setScalar(settings.pose_scale);}
   if(hole.visible){hole.rotation.z=t*.17;hole.rotation.y=.2;hole.scale.setScalar(1.9+(t-9.1)*.2);camera.position.y=.2;}
   if(galaxy.visible){galaxy.rotation.z=t*.4;galaxy.rotation.y=.4;galaxy.scale.setScalar(1.1+(t-10.23)*.6);}
   if(planet.visible){const e=Math.max(0,t-10.85)*(settings.debris_speed||1);planet.rotation.y=.3+e*.19;planet.position.set(.22,-.3,0);pm.uniforms.phase.value=e;half1.position.x=-e*.16;half2.position.x=e*.16;half1.rotation.z=e*.08;half2.rotation.z=-e*.1;for(let i=0;i<debris.length;i++){const a=i*2.4,r=1.2+e*(.4+(i%9)*.12);debris[i].position.set(Math.sin(a)*r,Math.cos(a)*r+e*.25,Math.sin(i*7)*1.5);debris[i].rotation.set(e+i,e*.7,e*.4);}}
   if(actor.visible){const step=t*7;actor.position.set((t-13.4)*.13,-.42,0);actor.rotation.y=-.7;ll.rotation.x=Math.sin(step)*.55;rl.rotation.x=-Math.sin(step)*.55;la.rotation.x=-Math.sin(step)*.45;ra.rotation.x=Math.sin(step)*.45;actor.position.y+=Math.abs(Math.sin(step))*.045;}
   fireMat.uniforms.time.value=t;fireMat.uniforms.strength.value=Math.min(1,Math.max(0,(t-13.65)*2));renderer.render(scene,camera);
  }
  return {render,matrices:()=>({projection:camera.projectionMatrix.toArray(),world:camera.matrixWorld.toArray(),view:camera.matrixWorldInverse.toArray(),planet:planet.matrixWorld.toArray(),actor:actor.matrixWorld.toArray(),posePlane:pose.matrixWorld.toArray(),plate:plate.matrixWorld.toArray()})};
 }
 window.mgLoad=async payload=>{
  stage.replaceChildren();errors=[];plan=payload.data.teacher_plan;design=node('div',stage,`width:720px;height:1280px;transform:scale(${payload.width/720});`);design.className='teacher-design';
  const assets=Object.fromEntries(payload.data.assets.map(a=>[a.id,a.src])),images={};
  await Promise.all(Object.entries(assets).map(async([id,src])=>{const im=new Image();im.src=src;await im.decode();images[id]=im;}));
  world=threeWorld(design,720,1280,images);tl=gsap.timeline({paused:true});window.__timelines={main:tl};
  await document.fonts.load('700 100px MotionInter');await document.fonts.ready;const promises=[];
  for(const shot of plan.scenes){
   const wrap=node('div',design,`background:${shot.mode3d?'transparent':shot.background};`);wrap.className='shot';wrap.dataset.shot=shot.id;
   if(shot.background_style==='radial')wrap.style.background=`radial-gradient(ellipse at 50% 45%,${shot.background} 10%,${shot.background_edge} 100%)`;
   if(shot.grid){const g=node('div',wrap,'position:absolute;inset:0;opacity:.09;background-image:linear-gradient(#777 1px,transparent 1px),linear-gradient(90deg,#777 1px,transparent 1px);background-size:44px 44px;pointer-events:none;');}
   const camera=node('div',wrap);camera.className='camera';camera.dataset.track=shot.id+'.camera';
   tl.set(wrap,{visibility:'hidden'},0);tl.set(wrap,{visibility:'visible'},shot.start);tl.set(wrap,{visibility:'hidden'},shot.end);
   if(shot.entrance==='right')tl.fromTo(wrap,{x:760,filter:'blur(16px)'},{x:0,filter:'blur(0px)',duration:.22,ease:'power3.out'},shot.start);
   else if(shot.entrance==='up')tl.fromTo(wrap,{y:1250,filter:'blur(18px)'},{y:0,filter:'blur(0px)',duration:.22,ease:'power3.out'},shot.start);
   const keys=shot.camera;tl.set(camera,{scale:keys[0].scale,x:keys[0].x,y:keys[0].y,rotation:keys[0].rotation||0},shot.start);
   for(let k=1;k<keys.length;k++){const a=keys[k-1],b=keys[k];tl.to(camera,{scale:b.scale,x:b.x,y:b.y,rotation:b.rotation||0,duration:b.time-a.time,ease:b.ease||'none'},shot.start+a.time);}
   for(const l of shot.layers){
    let parent=camera,left=l.x,top=l.y;
    if(l.orbit){parent=node('div',camera,`position:absolute;left:${l.orbit.center_x}px;top:${l.orbit.center_y}px;width:0;height:0;`);left-=l.orbit.center_x;top-=l.orbit.center_y;tl.fromTo(parent,{rotation:0},{rotation:l.orbit.rotation_delta,duration:shot.end-shot.start,ease:'none'},shot.start);}
    const e=node('div',parent,`left:${left}px;top:${top}px;width:${l.w}px;${l.h?'height:'+l.h+'px;':''}color:${l.color||ink};font-size:${l.size||32}px;font-weight:${l.weight||700};text-align:${l.align||'center'};opacity:${l.opacity??1};`);e.className='layer';e.dataset.track=shot.id+'.'+l.id;
    if(l.kind==='image'){const img=node('img',e);img.src=assets[l.asset];promises.push(img.decode());}
    else if(l.kind==='shape'){Object.assign(e.style,{background:l.color||teal,borderRadius:(l.radius||0)+'px',border:l.border||'none'});}
    else {
     if(l.font==='script')e.style.fontFamily='TeacherScript,cursive';
     if(l.font==='serif'||l.font==='serif-italic')e.style.fontFamily='Georgia,serif';if(l.font==='serif-italic')e.style.fontStyle='italic';
     if(l.font==='condensed')e.style.fontFamily='Impact,Arial Narrow,sans-serif';if(l.size<35)e.classList.add('tiny');
     if(l.label)Object.assign(e.style,{background:l.label,padding:'7px 15px',borderRadius:'12px',border:l.outline?'2px solid #111':'none'});
     if(l.underline)e.style.textDecoration='underline';
     const text=String(l.text||'');for(const char of Array.from(text)){if(char==='\n'){node('br',e);continue;}const s=node('span',e);s.className='type-char';s.textContent=char===' '?'\u00a0':char;}
     // Fit the complete row once before revealing any character.
     let size=l.size;while(e.scrollWidth>l.w+1&&size>14){size-=1;e.style.fontSize=size+'px';}
     if(e.scrollWidth>l.w+2)errors.push('Text overflow '+l.id);
    }
    const delay=shot.start+(l.delay||0);if(l.rotation)tl.set(e,{rotation:l.rotation},0);
    if(l.reveal==='characters')tl.fromTo(e.children,{opacity:0,y:16,scale:1.12,filter:'blur(4px)'},{opacity:1,y:0,scale:1,filter:'blur(0px)',duration:.16,stagger:l.stagger??.027,ease:'power2.out'},delay);
    else if(l.kind==='text')tl.fromTo(e,{opacity:0,y:l.rise||20,filter:'blur(8px)'},{opacity:l.opacity??1,y:0,filter:'blur(0px)',duration:.20,ease:'power3.out'},delay);
    if(l.drift){const t=Math.max(.25,shot.end-delay);tl.fromTo(e,{x:0,y:0,z:l.z||0},{x:l.drift[0],y:l.drift[1],z:(l.z||0)+(l.drift[2]||0),duration:t,ease:'none'},delay);}
   }
   if(shot.exit==='left')tl.to(wrap,{x:-850,filter:'blur(20px)',duration:.18,ease:'power3.in'},shot.end-.18);
   if(shot.exit==='up')tl.to(wrap,{y:-1280,filter:'blur(20px)',duration:.18,ease:'power3.in'},shot.end-.18);
  }
  node('div',design).className='grain';await Promise.all(promises);tl.set(design,{opacity:0},plan.duration);tl.time(0,false);world.render(0,null);if(errors.length)throw new Error(errors.join('; '));return true;
 };
 window.mgSeek=t=>{if(!tl)return;tl.time(t,false);const s=plan.scenes.find(s=>s.start<=t&&s.end>t);
  // Explicit absolute visibility also covers a renderer's repeated seeks to zero;
  // two zero-time GSAP sets must not make the opening scene remain hidden.
  for(const shot of design.querySelectorAll('.shot'))shot.style.visibility=shot.dataset.shot===s?.id?'visible':'hidden';
  world.render(t,s?.mode3d,s?.world,s?.start,s?.end);
 };
 window.mgCheck=()=>errors;
 window.teacherMatrices=()=>({time:tl.time(),layers:[...design.querySelectorAll('[data-track]')].filter(e=>getComputedStyle(e.closest('.shot')).visibility==='visible').map(e=>({id:e.dataset.track,matrix:getComputedStyle(e).transform,rect:(()=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};})()})),three:world.matrices()});
 window.addEventListener('hf-seek',e=>e.detail.waitUntil(Promise.resolve(window.__creativeReady).then(()=>window.mgSeek(e.detail.time))));
})();
