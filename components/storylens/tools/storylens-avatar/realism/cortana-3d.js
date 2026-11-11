import * as T from './cortana-3d-vendor.js';

const TAU = Math.PI * 2;
const X = new T.Vector3(1, 0, 0);
const Y = new T.Vector3(0, 1, 0);
const Z = new T.Vector3(0, 0, 1);

const shaderParts = {
  'Cortana Suit': [
    '#12334e',
    String.raw`
      float across = abs(holoRest.x);
      float y = holoRest.y;
      float side = abs(holoRest.z);
      float upper = smoothstep(1.08,1.24,y);
      float seam = across - (.075 + .054*(1.0-smoothstep(1.099,1.223,y))
        - .022*smoothstep(1.274,1.326,y));
      float sleeve = smoothstep(1.087,1.118,y) * (1.0-smoothstep(.263,.284,across));
      float yoke = smoothstep(0.002,0.009,seam) * max(upper,sleeve*.76);
      float outerShoulder=(1.0-smoothstep(.002,.004,abs(across-.176+.042*(y-1.20))))
        * smoothstep(1.13,1.19,y);
      float cuff=(1.0-smoothstep(.0015,.004,abs(y-(1.109-.14*(across-.18)))))
        * smoothstep(.151,.179,across)*(1.0-smoothstep(.251,.282,across));
      float collarAngle=atan(across,-holoRest.z+.013);
      float neckLine=1.333-.022*max(0.0,-cos(collarAngle))+.005*abs(sin(collarAngle));
      float collar = (1.0 - smoothstep(.0015,.005,abs(y-neckLine+.004))) * (1.0-smoothstep(.067,.083,across));
      float piping = (1.0-smoothstep(.002,.0045,abs(seam))) * smoothstep(1.00,1.14,y);
      piping += (1.0-smoothstep(.0017,.0034,abs(seam-.009))) * smoothstep(1.00,1.14,y);
      piping += (1.0-smoothstep(.0013,.0027,abs(seam-.015))) * smoothstep(1.00,1.14,y);
      piping += (outerShoulder+cuff)*.52;
      float legSeam = 1.0-smoothstep(.001,.004,abs(across - (.113 - .057*(1.0-y))));
      legSeam *= smoothstep(.11,.23,y)*(1.0-smoothstep(.73,.84,y))*smoothstep(.035,.065,side);
      vec2 woven = vec2(170.0*y,153.0*(holoRest.x + .71*holoRest.z));
      vec2 weave=fract(woven+vec2(0.0,floor(woven.x)*.5))-.5;
      float stitch=length(weave*vec2(.86,1.15));
      float rib=1.0-smoothstep(.13,.39,stitch);
      float fine=.88+.12*sin(woven.x*12.566)*cos(woven.y*15.71);
      float band=smoothstep(.07,.095,across)*smoothstep(.72,.88,y)
        *(1.0-smoothstep(1.05,1.16,y))*(1.0-smoothstep(.19,.248,across));
      holoTint = mix(vec3(.007,.027,.055),vec3(.063,.187,.29)*(.71+rib*.84)*fine,max(yoke,band*.46));
      holoTint += vec3(.10,.35,.54)*clamp(piping*.15+collar*.16+legSeam*.48,0.0,1.0);
    `,
  ],
  'Cortana Face': [
    '#639ab9',
    String.raw`
      float ax=abs(holoRest.x);
      float y=holoRest.y+.016*smoothstep(1.302,1.405,holoRest.y);
      float front=smoothstep(.096,.117,holoRest.z);
      float lip=1.0-smoothstep(.16,1.0,length(vec2(holoRest.x/.027,(y-1.423)/.0074)));
      float browHeight=1.508+.006*sin(clamp((ax-.012)/.038,0.0,1.0)*3.14159);
      float brow=(1.0-smoothstep(.001,.0036,abs(y-browHeight)))
           *smoothstep(.010,.016,ax)*(1.0-smoothstep(.043,.051,ax));
      float underChin=.79+.21*smoothstep(1.346,1.407,y);
      holoTint=mix(vec3(.14,.34,.52)*underChin,vec3(.04,.093,.16),front*clamp(lip*.57+brow*.76,0.0,1.0));
    `,
  ],
  'Cortana Boots': ['#10324a', 'holoTint=vec3(.008,.036,.063)+vec3(.04,.13,.21)*(1.0-smoothstep(.002,.006,abs(holoRest.y-.100)));'],
  'Cortana Piping': ['#64c3dc',
    'holoTint=vec3(.075,.25,.36)+vec3(.023,.10,.16)*smoothstep(1.16,1.28,holoRest.y);'],
  'Cortana Eyes': [
    '#c4e9ef',
    String.raw`
      float radius=length(vec2(abs(holoRest.x)/1.068-.0285,holoRest.y-1.473));
      float glint=exp(-pow(length(vec2(abs(holoRest.x)-.0282,holoRest.y-1.475))/.0012,2.0));
      float iris=(1.0-smoothstep(.0048,.006,radius))*smoothstep(.108,.118,holoRest.z);
      float pupil=(1.0-smoothstep(.002,.0034,radius))*iris;
      holoTint=mix(vec3(.41,.68,.76),vec3(.055,.26,.42),iris);
      holoTint=mix(holoTint,vec3(.008,.036,.06),pupil)+vec3(.19,.29,.36)*glint;
    `,
  ],
  'Cortana Hair': [
    '#07182c',
    String.raw`
      float flow=holoUv.x+(.054*sin(holoUv.y*2.7))*(1.0-holoUv.y);
      float fiber=.58+.15*sin(flow*1053.0)+.13*sin(flow*1963.0)+.08*cos(flow*372.0);
      float waves=.8+.20*cos(flow*47.0+holoUv.y*7.0);
      holoTint=vec3(.005,.019,.038)*(0.61+fiber*waves);
    `,
  ],
};

function hologramMaterial(name, signal) {
  const body = name === 'Cortana Suit' || name === 'Cortana Face';
  const [base, treatment] = shaderParts[name] || shaderParts['Cortana Suit'];
  const color = body ? `
    { ${shaderParts['Cortana Suit'][1]} }
    vec3 uniformTint = holoTint;
    { ${shaderParts['Cortana Face'][1]} }
    float collarAzimuth = atan(holoRest.x,holoRest.z-.013);
    float collar = 1.333-.022*max(0.0,cos(collarAzimuth))+.005*abs(sin(collarAzimuth));
    float faceWeight = smoothstep(collar-.003,collar+.005,holoRest.y);
    holoTint = mix(uniformTint, holoTint*.68, faceWeight);
  ` : treatment;
  const portrait = name === 'Cortana Eyes' || body;
  const badge = body ? `
    vec2 badgeUv=vec2((holoRest.x+.073)/.055,(holoRest.y-1.124)/.015);
    if (badgeUv.x>0.0 && badgeUv.x<1.0 && badgeUv.y>0.0 && badgeUv.y<1.0 && holoRest.z>.056)
      holoTint += texture2D(holoBadge,badgeUv).a*vec3(.11,.40,.58);
  ` : '';
  const roughness = {'Cortana Hair':.53,'Cortana Face':.54,'Cortana Eyes':.31,'Cortana Piping':.42};
  const material = new T.MeshStandardMaterial({
    color: base, roughness: roughness[name] || .76, metalness: name === 'Cortana Piping' ? .14 : .025,
    side: name === 'Cortana Hair' ? T.DoubleSide : T.FrontSide,
    skinning: true,
  });
  material.customProgramCacheKey = () => 'cortana-hologram/' + name;
  material.onBeforeCompile = shader => {
    shader.uniforms.holoClock = signal.clock;
    shader.uniforms.holoBoot = signal.boot;
    shader.uniforms.holoEnergy = signal.energy;
    shader.uniforms.holoFace = {value:signal.face};
    shader.uniforms.holoHair = {value:signal.hair};
    shader.uniforms.holoBadge = {value:signal.badge};
    const varying = 'varying vec3 holoRest; varying vec2 holoUv;\n';
    shader.vertexShader = varying + shader.vertexShader.replace('#include <begin_vertex>', 
      '#include <begin_vertex>\nholoRest=position; holoUv=uv;');
    shader.fragmentShader = varying + 'uniform float holoClock, holoBoot, holoEnergy; uniform sampler2D holoFace, holoHair, holoBadge;\n' + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', String.raw`
      #include <color_fragment>
      vec3 holoTint = diffuseColor.rgb;
      ${color}
      ${badge}
      vec2 fitted=vec2(holoRest.x/(1.0+.068*smoothstep(1.333,1.404,holoRest.y)),
                       holoRest.y+.016*smoothstep(1.302,1.405,holoRest.y));
      ${portrait ? `
        vec2 faceUV=vec2((610.5+fitted.x*1807.0-487.0)/267.0,
          (567.0-(266.0-(fitted.y-1.490)*1750.0))/433.0);
        vec4 details=texture2D(holoFace,faceUV);
        float portraitFront=smoothstep(.045,.122,holoRest.z);
        if (faceUV.x>=0.0 && faceUV.x<=1.0 && faceUV.y>=0.0 && faceUV.y<=1.0 && holoRest.y>1.301)
          holoTint=mix(holoTint,pow(details.rgb,vec3(2.15)),details.a*portraitFront*.97);
      ` : ''}
      ${name === 'Cortana Hair' ? `
        vec2 hairUV=vec2((610.5+fitted.x*1807.0-419.0)/412.0,
          (433.0-(266.0-(fitted.y-1.490)*1750.0))/415.0);
        vec4 strands=texture2D(holoHair,hairUV);
        float onFront=smoothstep(.035,.108,holoRest.z);
        if (hairUV.x>=0.0 && hairUV.x<=1.0 && hairUV.y>=0.0 && hairUV.y<=1.0)
          holoTint=mix(holoTint,pow(strands.rgb,vec3(2.2))*.85,strands.a*onFront*.76);
      ` : ''}
      diffuseColor.rgb = holoTint;
    `);
    shader.fragmentShader = shader.fragmentShader.replace('#include <tonemapping_fragment>', String.raw`
      float scanDepth = mix(.069,.016,smoothstep(1.30,1.43,holoRest.y));
      float scan = (1.0-scanDepth) + scanDepth*sin(holoRest.y*1090.0-holoClock*10.0);
      float sweep = exp(-pow((holoRest.y-mod(holoClock*.22,1.88))/.027,2.0));
      float rim = pow(1.0-clamp(abs(dot(normalize(vViewPosition),normal)),0.0,1.0),2.25);
      float bootLine = holoBoot*1.82;
      if (holoRest.y > bootLine && holoBoot < .995) discard;
      float bootEdge = exp(-abs(holoRest.y-bootLine)*110.0)*(1.0-holoBoot)*2.5;
      float skinRegion=${portrait ? 'smoothstep(1.302,1.410,holoRest.y)' : '0.0'};
      gl_FragColor.rgb = gl_FragColor.rgb * scan * mix(.76,.90,skinRegion)
        + holoTint*mix(.40,.22,skinRegion)
        + vec3(.010,.083,.175)*(rim*.85+sweep*.18+bootEdge+holoEnergy*.073);
      #include <tonemapping_fragment>
    `);
  };
  return material;
}

function steer(bone, tip, direction) {
  if (!bone || !tip) return;
  const q = bone.getWorldQuaternion(new T.Quaternion());
  const current = tip.getWorldPosition(new T.Vector3()).sub(bone.getWorldPosition(new T.Vector3())).normalize();
  const turn = new T.Quaternion().setFromUnitVectors(current, direction.normalize());
  bone.quaternion.copy(bone.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(turn).multiply(q));
  bone.updateWorldMatrix(false, true);
}

function motionJoint(bone) {
  if (!bone) return () => {};
  const rest = bone.quaternion.clone();
  const worldInverse = bone.getWorldQuaternion(new T.Quaternion()).invert();
  const axisX = X.clone().applyQuaternion(worldInverse);
  const axisY = Y.clone().applyQuaternion(worldInverse);
  const axisZ = Z.clone().applyQuaternion(worldInverse);
  const rotation = new T.Quaternion();
  return (pitch, yaw = 0, roll = 0) => {
    bone.quaternion.copy(rest).multiply(rotation.setFromAxisAngle(axisY, yaw))
      .multiply(rotation.setFromAxisAngle(axisX, pitch)).multiply(rotation.setFromAxisAngle(axisZ, roll));
  };
}

function mouthJoint(bone, sign) {
  if (!bone) return () => {};
  const rest = bone.position.clone();
  const inverse = bone.parent.getWorldQuaternion(new T.Quaternion()).invert();
  const outward = X.clone().applyQuaternion(inverse);
  const forward = Z.clone().applyQuaternion(inverse);
  return (width, round) => {
    bone.position.copy(rest).addScaledVector(outward,sign*(width-round))
      .addScaledVector(forward,round*.62);
  };
}

function lipShape(samples, rate, seconds) {
  if (!samples || seconds < 0 || seconds * rate >= samples.length) return [0, 0];
  const center = Math.floor(seconds * rate);
  const begin = Math.max(1, center - Math.round(rate * .012));
  const end = Math.min(samples.length, center + Math.round(rate * .012));
  let power = 0;
  let detail = 0;
  for (let i = begin; i < end; i += 2) {
    const sample = samples[i];
    power += sample * sample;
    detail += Math.abs(sample - samples[i-1]);
  }
  const length = Math.max(1, (end-begin)/2);
  const level = Math.sqrt(power/length);
  return [T.MathUtils.clamp((level-.012)*6.4,0,1),
    T.MathUtils.clamp(detail/length/(.009+level)*5,0,1)];
}

export function mountCortana(stage, phase) {
  const renderer = new T.WebGLRenderer({alpha:true, antialias:true, powerPreference:'low-power'});
  const canvas = renderer.domElement;
  canvas.setAttribute('aria-hidden', 'true');
  renderer.setClearColor(0x000000, 0);
  renderer.outputEncoding = T.sRGBEncoding;
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.7));
  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(33, 1, .04, 24);
  const subject = new T.Group();
  scene.add(subject, new T.HemisphereLight(0xb9dcec,0x111b2b,.70));
  const key = new T.DirectionalLight(0xc3def2,.96);
  key.position.set(-2.1,3.2,3.3);
  const backlight = new T.DirectionalLight(0x499eff,.65);
  backlight.position.set(1,2,-2);
  const fill = new T.DirectionalLight(0x73b1d1,.26);
  fill.position.set(2.7,1.45,3.3);
  scene.add(key,fill,backlight);
  const platform = new T.Group();
  scene.add(platform);
  for (const [radius, opacity, extent] of [[.27,.42,TAU],[.35,.22,TAU],[.52,.16,4.9],[.68,.08,TAU]]) {
    const points = Array.from({length:97}, (_, i) => {
      const a = extent*i/96;
      return new T.Vector3(radius*Math.cos(a),.008,radius*Math.sin(a));
    });
    platform.add(new T.Line(new T.BufferGeometry().setFromPoints(points),
      new T.LineBasicMaterial({color:0x4bb9ed,transparent:true,opacity})));
  }
  const pool = new T.Mesh(new T.PlaneGeometry(3.6, 3.6), new T.ShaderMaterial({
    transparent:true, depthWrite:false,
    vertexShader:'varying vec2 poolUV; void main(){poolUV=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
    fragmentShader:'varying vec2 poolUV; void main(){float radius=length(poolUV-.5)*2.0; gl_FragColor=vec4(.06,.44,.76,exp(-radius*radius*9.0)*.29);}'
  }));
  pool.rotation.x=-Math.PI/2;
  pool.position.y=-.006;
  scene.add(pool);
  const positions=[];
  for(let i=0;i<74;i++){
    const angle=i*2.39996;
    const radius=.35+.90*((i*31)%74)/74;
    positions.push(radius*Math.cos(angle),((i*53)%74)/44,radius*Math.sin(angle));
  }
  const sparks = new T.Points(new T.BufferGeometry().setAttribute('position',new T.Float32BufferAttribute(positions,3)),
    new T.PointsMaterial({color:0x54b6e8,size:.009,transparent:true,opacity:.43,depthWrite:false}));
  scene.add(sparks);
  const textureLoader = new T.TextureLoader();
  const badgeCanvas = document.createElement('canvas');
  badgeCanvas.width=256;
  badgeCanvas.height=64;
  const ink=badgeCanvas.getContext('2d');
  ink.font='bold 48px Segoe UI';
  ink.textAlign='center';
  ink.textBaseline='middle';
  ink.fillStyle='#fff';
  ink.fillText('UNSC',128,32);
  const signal = {clock:{value:0},boot:{value:0},energy:{value:0},
    face:textureLoader.load('/cortana-face-atlas.png?v=2'),
    hair:textureLoader.load('/cortana-hair-atlas.png?v=1'),badge:new T.CanvasTexture(badgeCanvas)};
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const materials = new Map();
  let host=stage, raf=0, yaw=0, wantedYaw=0, pitch=.047, wantedPitch=.047, zoom=1, dragging;
  let activeVoice, model, openedAt, lastDraw, energy=0;
  let jaw=()=>{}, head=()=>{}, chest=()=>{}, forearm=()=>{};
  let gesture=0, mouthWidth=0, mouthRound=0, lipCorners=[], eyelids=[], gaze=[];
  let width=0,height=0;
  const origin=new T.Vector3(0,.74,0);

  function resize() {
    width=host.clientWidth;
    height=host.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width,height,false);
    camera.aspect=width/height;
    camera.updateProjectionMatrix();
    if (!raf) raf=requestAnimationFrame(draw);
  }
  const sizes = new ResizeObserver(resize);
  function move(next) {
    sizes.disconnect();
    host=next;
    host.append(canvas);
    sizes.observe(host);
    resize();
  }
  function draw(now) {
    raf=0;
    if (!host.isConnected || !host.getClientRects().length || !width || !height) return;
    const small = host !== stage;
    const dt=Math.min(.055,Math.max(.008,(now-(lastDraw||now-16))/1000));
    lastDraw=now;
    const t=now/1000;
    const state=phase();
    const elapsed=activeVoice ? activeVoice.context.currentTime - activeVoice.start : 0;
    const [shape, bright] = activeVoice ? lipShape(activeVoice.samples,activeVoice.rate,elapsed) : [0,0];
    energy=T.MathUtils.damp(energy,shape,shape>energy?33:17,dt);
    signal.energy.value=energy;
    signal.clock.value=reduceMotion.matches?0:t;
    signal.boot.value=reduceMotion.matches?1:T.MathUtils.clamp((now-(openedAt||now))/720,0,1);
    const motion=reduceMotion.matches?0:1;
    const blinkPhase=(t+1.5)%9.7;
    const closure=Math.max(0,1-Math.abs(blinkPhase-.43)/.102,
                            1-Math.abs(blinkPhase-5.82)/.110)*motion;
    for(const [upper,lower] of eyelids) {
      upper(.39*closure);
      lower(-.138*closure);
    }
    const glance=.032*Math.tanh(4*Math.sin(t*.81))*motion;
    for(const look of gaze) look(.014*Math.sin(t*.72)*motion,glance);
    jaw((.11 + .22*(1-bright))*energy);
    mouthWidth=T.MathUtils.damp(mouthWidth,energy*bright*.0048,24,dt);
    mouthRound=T.MathUtils.damp(mouthRound,energy*(1-bright)*.0044,20,dt);
    for(const shapeLip of lipCorners) shapeLip(mouthWidth,mouthRound);
    gesture=T.MathUtils.damp(gesture,state==='speaking'?1:0,2.7,dt);
    forearm(-.11 * gesture * motion * (.55+.45*Math.sin(t*2.4)),
      .044 * gesture * motion * Math.sin(t*2.0));
    head((.018*Math.sin(t*1.1)+(state==='speaking'?.037*energy*Math.sin(elapsed*6.0):0))*motion,
      .085*Math.sin(t*.61)*motion,.024*Math.sin(t*.78)*motion);
    chest(.013*Math.sin(t*1.5)*motion,.022*Math.sin(t*.83)*motion);
    subject.position.y=(.011+.006*Math.sin(t*1.52))*motion;
    platform.rotation.y=t*.11*motion;
    sparks.rotation.y=t*.045*motion;
    yaw=T.MathUtils.damp(yaw,wantedYaw,14,dt);
    pitch=T.MathUtils.damp(pitch,wantedPitch,14,dt);
    const occupied = small ? .84 : Math.max(.36,Math.min(.75,1-(width<810?252:197)/height));
    const fitted = Math.max(1.64 / occupied, .78 / camera.aspect);
    const distance = fitted / (2*Math.tan(T.MathUtils.degToRad(camera.fov/2))) / (small?1:zoom);
    const angle = small ? .25 : yaw;
    const viewPitch = small ? .06 : pitch;
    const targetHeight = small ? .81 : origin.y - (width<810 && zoom===1 ? .043 : 0);
    camera.position.set(Math.sin(angle)*distance*Math.cos(viewPitch),targetHeight+Math.sin(viewPitch)*distance,
      Math.cos(angle)*distance*Math.cos(viewPitch));
    camera.lookAt(0,targetHeight,0);
    renderer.render(scene,camera);
    raf=requestAnimationFrame(draw);
  }

  function orbit(delta) { wantedYaw+=delta; }
  function view(angle) { wantedYaw += Math.atan2(Math.sin(angle-wantedYaw),Math.cos(angle-wantedYaw)); }
  stage.addEventListener('pointerdown', event=>{
    if (event.button!==0) return;
    stage.setPointerCapture(event.pointerId);
    dragging={id:event.pointerId,x:event.clientX,y:event.clientY};
    stage.dataset.dragging='true';
  });
  stage.addEventListener('pointermove', event=>{
    if(dragging?.id!==event.pointerId) return;
    orbit((dragging.x-event.clientX)*.010);
    wantedPitch=T.MathUtils.clamp(wantedPitch+(event.clientY-dragging.y)*.007,-.45,.48);
    dragging={id:event.pointerId,x:event.clientX,y:event.clientY};
  });
  stage.addEventListener('lostpointercapture', ()=>{
    dragging=null;
    delete stage.dataset.dragging;
  });
  stage.addEventListener('keydown', event=>{
    if(event.key==='ArrowLeft') orbit(-Math.PI/8);
    else if(event.key==='ArrowRight') orbit(Math.PI/8);
    else if(event.key==='ArrowUp') wantedPitch=Math.min(.48,wantedPitch+.12);
    else if(event.key==='ArrowDown') wantedPitch=Math.max(-.45,wantedPitch-.12);
    else if(event.key==='Home') {view(0); wantedPitch=.047;}
    else return;
    event.preventDefault();
  });
  move(stage);
  const ready = new T.GLTFLoader().loadAsync('/cortana-hologram.glb?v=realism').then(gltf=>{
    model=gltf.scene;
    model.traverse(mesh=>{
      if(!mesh.isMesh) return;
      const name=mesh.material.name;
      if(!materials.has(name)) materials.set(name,hologramMaterial(name,signal));
      mesh.material=materials.get(name);
      mesh.frustumCulled=false;
    });
    subject.add(model);
    model.updateMatrixWorld(true);
    for(const [side,sign] of [['L',1],['R',-1]]) {
      const bone=name=>model.getObjectByName(name+side);
      steer(bone('upperarm01'),bone('lowerarm01'),new T.Vector3(sign*.23,-.97,-.08));
      steer(bone('lowerarm01'),bone('wrist'),new T.Vector3(sign*-.42,-.87,-.25));
      steer(bone('wrist'),bone('finger3-1'),new T.Vector3(sign*-.30,-.91,-.07));
      lipCorners.push(mouthJoint(bone('oris03'),sign),mouthJoint(bone('oris07'),sign));
      eyelids.push([motionJoint(bone('orbicularis03')),motionJoint(bone('orbicularis04'))]);
      gaze.push(motionJoint(bone('eye')));
    }
    jaw=motionJoint(model.getObjectByName('jaw'));
    head=motionJoint(model.getObjectByName('head'));
    chest=motionJoint(model.getObjectByName('spine01'));
    forearm=motionJoint(model.getObjectByName('lowerarm01R'));
    openedAt=performance.now();
  });
  return {
    ready, move, view,
    closer(value) { zoom=value?2.62:1; origin.y=value?1.335:.74; },
    voice(context,buffer,start) { activeVoice={context,samples:buffer.getChannelData(0),rate:buffer.sampleRate,start}; },
    quiet() { activeVoice=null; },
  };
}
