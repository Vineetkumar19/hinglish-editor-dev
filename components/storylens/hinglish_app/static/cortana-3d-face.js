import * as T from './cortana-3d-performance-vendor.js';

const X = new T.Vector3(1, 0, 0);
const Y = new T.Vector3(0, 1, 0);
const Z = new T.Vector3(0, 0, 1);

const shaderParts = {
  'Cortana Suit': [
    '#12334e',
    String.raw`
      float x = abs(holoRest.x);
      float y = holoRest.y;
      float depth = holoRest.z;
      float torso = 1.0-smoothstep(.173,.206,x);
      float neckline = 1.333-.022*max(0.0,cos(atan(holoRest.x,depth-.013)))+.005*abs(sin(atan(holoRest.x,depth-.013)));
      float silverEdge = .075+.054*(1.0-smoothstep(1.099,1.223,y))-.022*smoothstep(1.274,1.326,y);
      float sleeveAxis = x+.78*(1.16-y);
      float arm = smoothstep(.156,.213,x)*smoothstep(.81,.96,y);
      float cap = smoothstep(.001,.005,x-silverEdge)*smoothstep(1.035,1.153,y);
      float shoulder = cap*(1.0-arm*smoothstep(.261,.267,sleeveAxis));
      float slashX = (x-.078)/.092;
      float slashMid = 1.305-.048*slashX;
      float slash = step(0.0,slashX)*step(slashX,1.0)
        *(1.0-smoothstep(.001,.004,abs(y-slashMid)-.012*(1.0-slashX)));
      float rear = 1.0-smoothstep(-.029,.006,depth);
      float rearX = x-(1.265-y)*.31;
      float rearPatch = smoothstep(.094,.100,rearX)*(1.0-smoothstep(.152,.158,rearX))
        *smoothstep(1.165,1.177,y)*(1.0-smoothstep(1.270,1.281,y));
      shoulder *= 1.0-mix(slash,rearPatch,rear)*.98;
      float sideStart = .110+.045*(1.0-smoothstep(.42,.914,y));
      float sidePanel = smoothstep(sideStart-.002,sideStart+.002,x)
        * smoothstep(.405,.455,y)*(1.0-smoothstep(.920,.952,y))*(1.0-arm);
      float waistHeight = .913+.039*smoothstep(.074,.145,x);
      float waist = (1.0-smoothstep(.0055,.0095,abs(y-waistHeight)))*torso*(1.0-arm);
      float seamX = .083-.022*clamp((.697-y)/.055,0.0,1.0)+.001*smoothstep(.697,.91,y);
      float legWindow = smoothstep(.553,.568,y)*(1.0-smoothstep(.909,.920,y))
        *smoothstep(.027,.053,depth)*torso*(1.0-arm);
      float piping = (1.0-smoothstep(.0010,.00225,abs(x-seamX)))
        +(1.0-smoothstep(.0007,.00175,abs(x-seamX-.0048)));
      float kneeHeight = .411+.048*pow(clamp(abs(x-.140)/.045,0.0,1.0),2.3);
      float knee = (1.0-smoothstep(.004,.0065,abs(y-kneeHeight)))*smoothstep(.075,.103,x)
        *smoothstep(.006,.040,abs(depth));
      float cuff = ((1.0-smoothstep(.0013,.0035,abs(sleeveAxis-.267)))
        + (1.0-smoothstep(.001,.0031,abs(sleeveAxis-.274))))*arm*smoothstep(1.05,1.10,y);
      float wrist = (1.0-smoothstep(.0013,.004,abs(x-.418)))*smoothstep(.82,.88,y);
      float collar = (1.0-smoothstep(.002,.0044,abs(y-neckline+.0035)))*(1.0-smoothstep(.068,.082,x));
      vec2 weave = vec2((holoRest.x+.57*depth)*269.0,y*296.0);
      vec2 tile = abs(fract(weave+vec2(.5*floor(weave.y),0.0))-.5);
      float fibre = 1.0-smoothstep(.34,.47,max(tile.x*.96,tile.y*.59+tile.x*.49));
      vec2 pitch = vec2(holoRest.x*223.0+depth*107.0,y*272.0);
      vec2 mark = fract(pitch+vec2(.5*mod(floor(pitch.y),2.0)*rear,0.0))-.5;
      float pixel = 1.0-smoothstep(.044,.145,length(mark*vec2(mix(1.0,.48,rear),1.0)));
      vec3 navy = vec3(.007,.033,.059)+pixel*vec3(.006,.020,.030);
      vec3 silver = vec3(.099,.186,.236)+fibre*vec3(.115,.171,.189);
      holoTint = mix(navy,silver,max(shoulder,sidePanel*.88));
      float detail = clamp(max(max(waist,knee),max(piping*legWindow*.85,max(cuff,wrist)))+collar*.49,0.0,1.0);
      holoTint = mix(holoTint,vec3(.151,.268,.334),detail*.94);
      float hands = smoothstep(.421,.431,x)*smoothstep(.80,.84,y);
      holoTint = mix(holoTint,vec3(.154,.211,.266),hands);
    `,
  ],
  'Cortana Face': [
    '#639ab9',
    String.raw`
      float underChin=.79+.21*smoothstep(1.347,1.409,holoRest.y);
      holoTint=vec3(.152,.282,.424)*underChin;
    `,
  ],
  'Cortana Boots': ['#172b38', [
    'float toe=(1.0-smoothstep(.058,.077,holoRest.y))*smoothstep(.048,.089,holoRest.z);',
    'float sole=smoothstep(.011,.017,holoRest.y);',
    'holoTint=mix(vec3(.007,.029,.049),vec3(.154,.236,.278),toe)*sole+vec3(.004,.008,.010)*(1.0-sole);'
  ].join('\n')],
  'Cortana Piping': ['#9fc6d9',
    'holoTint=vec3(.139,.239,.292)+vec3(.012,.028,.035)*smoothstep(1.16,1.28,holoRest.y);'],
  'Cortana Eyes': [
    '#c4e9ef',
    String.raw`
      vec2 eye=vec2(abs(holoRest.x)-.0295,holoRest.y-1.4742);
      float radius=length(eye);
      float angle=atan(eye.y,eye.x);
      float fibers=.82+.10*sin(angle*38.0+radius*510.0)+.08*sin(angle*61.0);
      float iris=(1.0-smoothstep(.0056,.0064,radius))*smoothstep(.108,.118,holoRest.z);
      float limbal=smoothstep(.0046,.0063,radius);
      float pupil=(1.0-smoothstep(.0021,.0027,radius))*iris;
      vec2 shine=vec2(holoRest.x+.0015-sign(holoRest.x)*.0295,holoRest.y-1.476);
      float glint=exp(-pow(length(shine)/.00075,2.0));
      vec3 irisBlue=mix(vec3(.040,.195,.32)*fibers,vec3(.013,.049,.082),limbal*.76);
      holoTint=mix(vec3(.197,.286,.365),irisBlue,iris);
      holoTint=mix(holoTint,vec3(.005,.013,.026),pupil)+vec3(.16,.23,.32)*glint;
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
    holoTint = mix(uniformTint, holoTint*.92, faceWeight);
  ` : treatment;
  const portrait = body;
  const badge = body ? `
    vec2 badgeUv=vec2((holoRest.x+.073)/.055,(holoRest.y-1.124)/.015);
    if (badgeUv.x>0.0 && badgeUv.x<1.0 && badgeUv.y>0.0 && badgeUv.y<1.0 && holoRest.z>.056)
      holoTint += texture2D(holoBadge,badgeUv).a*vec3(.11,.40,.58);
  ` : '';
  const roughness = {'Cortana Hair':.63,'Cortana Face':.69,'Cortana Eyes':.39,'Cortana Piping':.42};
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
        vec2 faceUV=vec2((610.5+holoRest.x*1807.0/1.068-487.0)/267.0,
          (567.0-(266.0-(holoRest.y-1.474)*1750.0))/433.0);
        vec4 details=texture2D(holoFace,faceUV);
        float portraitFront=smoothstep(.047,.122,holoRest.z);
        if (faceUV.x>=0.0 && faceUV.x<=1.0 && faceUV.y>=0.0 && faceUV.y<=1.0 && holoRest.y>1.326) {
          vec3 albedo=pow(details.rgb,vec3(2.15));
          holoTint=mix(holoTint,albedo*vec3(.81,1.07,1.24),details.a*portraitFront*.66);
        }
        float ax=abs(holoRest.x);
        float browAlong=clamp((ax-.012)/.041,0.0,1.0);
        float browHeight=1.4905+.0061*sin(browAlong*2.82)-.0022*browAlong;
        float browThickness=mix(.00185,.00070,browAlong);
        float brow=(1.0-smoothstep(browThickness*.42,browThickness*1.45,abs(holoRest.y-browHeight)))
           *smoothstep(.010,.015,ax)*(1.0-smoothstep(.050,.057,ax));
        float mouth=(1.0-smoothstep(.24,1.0,length(vec2(holoRest.x/.029,(holoRest.y-1.4159)/.0132))));
        float faceFront=smoothstep(.092,.116,holoRest.z);
        holoTint=mix(holoTint,vec3(.038,.074,.112),faceFront*brow*.72);
        holoTint=mix(holoTint,vec3(.061,.112,.173),faceFront*mouth*.76);
      ` : ''}
      ${name === 'Cortana Hair' ? `
        vec2 hairUV=vec2((610.5+fitted.x*1807.0-419.0)/412.0,
          (433.0-(266.0-(fitted.y-1.490)*1750.0))/415.0);
        vec4 strands=texture2D(holoHair,hairUV);
        float onFront=smoothstep(.035,.108,holoRest.z);
        if (hairUV.x>=0.0 && hairUV.x<=1.0 && hairUV.y>=0.0 && hairUV.y<=1.0)
          holoTint=mix(holoTint,pow(strands.rgb,vec3(2.2))*.85,strands.a*onFront*.32);
      ` : ''}
      diffuseColor.rgb = holoTint;
    `);
    shader.fragmentShader = shader.fragmentShader.replace('#include <tonemapping_fragment>', String.raw`
      float scanDepth = mix(.069,.016,smoothstep(1.30,1.43,holoRest.y));
      float scan = (1.0-scanDepth) + scanDepth*sin(holoRest.y*1090.0-holoClock*10.0);
      float sweep = exp(-pow((holoRest.y-mod(holoClock*.22,1.88))/.027,2.0));
      float viewEdge=1.0-clamp(abs(dot(normalize(vViewPosition),normal)),0.0,1.0);
      float rim=pow(viewEdge,3.0);
      float halo=pow(viewEdge,1.7);
      float bootLine = holoBoot*1.82;
      if (holoRest.y > bootLine && holoBoot < .995) discard;
      float bootEdge = exp(-abs(holoRest.y-bootLine)*110.0)*(1.0-holoBoot)*2.5;
      float skinRegion=${body || name === 'Cortana Eyes' ? 'smoothstep(1.302,1.410,holoRest.y)' : '0.0'};
      gl_FragColor.rgb = gl_FragColor.rgb * scan * mix(.76,.86,skinRegion)
        + holoTint*mix(.40,.31,skinRegion)
        + vec3(.012,.155,.37)*(rim*mix(.75,.28,skinRegion)+bootEdge+sweep*.07)
        + vec3(.005,.042,.103)*(halo*.42+holoEnergy*.037);
      #include <tonemapping_fragment>
    `);
  };
  return material;
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
  scene.add(subject, new T.HemisphereLight(0xb4c6db,0x102238,.68));
  const key = new T.DirectionalLight(0xc5dbf0,.82);
  key.position.set(-2.1,3.2,3.3);
  const backlight = new T.DirectionalLight(0x3f9bdb,1.18);
  backlight.position.set(1,2,-2);
  const fill = new T.DirectionalLight(0x8bb2d1,.31);
  fill.position.set(2.7,1.45,3.3);
  const rim = new T.DirectionalLight(0x2b8dc6,.72);
  rim.position.set(-1.6,1.4,-2.0);
  scene.add(key,fill,backlight,rim);
  const pool = new T.Mesh(new T.PlaneGeometry(3.6, 3.6), new T.ShaderMaterial({
    transparent:true, depthWrite:false,
    vertexShader:'varying vec2 poolUV; void main(){poolUV=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
    fragmentShader:'varying vec2 poolUV; void main(){float radius=length(poolUV-.5)*2.0; gl_FragColor=vec4(.06,.44,.76,exp(-radius*radius*9.0)*.29);}'
  }));
  pool.rotation.x=-Math.PI/2;
  pool.position.y=-.006;
  scene.add(pool);
  const reflection = new T.Reflector(new T.PlaneGeometry(3.4,3.4),{
    textureWidth:320, textureHeight:192, clipBias:.0015, color:0x58caff,
    shader:{
      uniforms:{color:{value:null},tDiffuse:{value:null},textureMatrix:{value:null}},
      vertexShader:[
        'uniform mat4 textureMatrix; varying vec4 projected; varying vec2 floorUV;',
        'void main(){floorUV=uv;projected=textureMatrix*vec4(position,1.0);',
        'gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}'
      ].join('\n'),
      fragmentShader:[
        'uniform vec3 color; uniform sampler2D tDiffuse; varying vec4 projected; varying vec2 floorUV;',
        'void main(){ vec2 uv=projected.xy/projected.w;',
        'vec3 r=texture2D(tDiffuse,uv).rgb*.50;',
        'r+=(texture2D(tDiffuse,uv+vec2(.010,0.0)).rgb+texture2D(tDiffuse,uv-vec2(.010,0.0)).rgb)*.25;',
        'float alpha=.30*smoothstep(.04,.42,r.b)*(1.0-smoothstep(.09,.49,length(floorUV-.5)));',
        'gl_FragColor=vec4(mix(r,color,.35),alpha);}'
      ].join('\n')
    }
  });
  reflection.rotation.x=-Math.PI/2;
  reflection.position.y=-.016;
  reflection.material.transparent=true;
  reflection.material.depthWrite=false;
  scene.add(reflection);
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
    face:textureLoader.load('/cortana-face-match.png'),
    hair:textureLoader.load('/cortana-tv-hair.png'),badge:new T.CanvasTexture(badgeCanvas)};
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const materials = new Map();
  let host=stage, raf=0, yaw=0, wantedYaw=0, pitch=.047, wantedPitch=.047, dragging;
  let closeUp=false;
  let activeVoice, model, openedAt, lastDraw, energy=0;
  let jaw=()=>{}, mixer, activeAction, listening, speaking;
  let mouthWidth=0, mouthRound=0;
  const lipCorners=[], eyelids=[], gaze=[];
  let width=0,height=0;

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
    const frameSeconds=(now-(lastDraw||now-16))/1000;
    const dt=Math.min(.055,Math.max(.008,frameSeconds));
    lastDraw=now;
    const t=now/1000;
    const state=phase();
    if (mixer) {
      const next = !reduceMotion.matches && (state==='speaking' || activeVoice) ? speaking : listening;
      if (next !== activeAction) {
        next.reset().play().crossFadeFrom(activeAction,.33,false);
        activeAction=next;
      }
      mixer.update(reduceMotion.matches ? 0 : Math.min(.25,frameSeconds));
    }
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
      upper(.35*closure);
      lower(-.123*closure);
    }
    const glance=.032*Math.tanh(4*Math.sin(t*.81))*motion;
    for(const look of gaze) look(.014*Math.sin(t*.72)*motion,glance);
    jaw((.11 + .22*(1-bright))*energy);
    mouthWidth=T.MathUtils.damp(mouthWidth,energy*bright*.0048,24,dt);
    mouthRound=T.MathUtils.damp(mouthRound,energy*(1-bright)*.0044,20,dt);
    for(const shapeLip of lipCorners) shapeLip(mouthWidth,mouthRound);
    yaw=T.MathUtils.damp(yaw,wantedYaw,14,dt);
    pitch=T.MathUtils.damp(pitch,wantedPitch,14,dt);
    const occupied = Math.max(.36,Math.min(.75,1-(width<810?252:197)/height));
    const fitted = small ? Math.max(.48,.34/camera.aspect)
      : closeUp ? Math.max(.648,.42/camera.aspect)
      : Math.max(1.64/occupied,.78/camera.aspect);
    const distance = fitted/(2*Math.tan(T.MathUtils.degToRad(camera.fov/2)));
    const angle = small ? .08 : yaw;
    const viewPitch = small ? .025 : pitch;
    const targetHeight = small ? 1.40 : closeUp ? 1.41 : (width<810 ? .697 : .74);
    camera.position.set(Math.sin(angle)*distance*Math.cos(viewPitch),targetHeight+Math.sin(viewPitch)*distance,
      Math.cos(angle)*distance*Math.cos(viewPitch));
    camera.lookAt(0,targetHeight,0);
    reflection.visible=!small && !closeUp && height>410 && camera.position.y>.08;
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
  const ready = new T.GLTFLoader().loadAsync('/cortana-hologram-face.glb').then(gltf=>{
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
      lipCorners.push(mouthJoint(bone('oris03'),sign),mouthJoint(bone('oris07'),sign));
      eyelids.push([motionJoint(bone('orbicularis03')),motionJoint(bone('orbicularis04'))]);
      gaze.push(motionJoint(bone('eye')));
    }
    jaw=motionJoint(model.getObjectByName('jaw'));
    const idleClip=T.AnimationClip.findByName(gltf.animations,'Listening');
    const speechClip=T.AnimationClip.findByName(gltf.animations,'Speaking');
    if(!idleClip || !speechClip) throw new Error('The Blender motion clips are missing.');
    mixer=new T.AnimationMixer(model);
    listening=mixer.clipAction(idleClip);
    speaking=mixer.clipAction(speechClip);
    activeAction=listening.play();
    mixer.update(0);
    openedAt=performance.now();
  });
  return {
    ready, move, view,
    closer(value) { closeUp=value; },
    voice(context,buffer,start) { activeVoice={context,samples:buffer.getChannelData(0),rate:buffer.sampleRate,start}; },
    quiet() { activeVoice=null; },
  };
}
