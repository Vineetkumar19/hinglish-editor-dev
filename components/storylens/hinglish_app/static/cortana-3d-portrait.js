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
      vec2 collar = collarDistances(holoRest);
      float neckDistance = collar.x;
      float collarOutside = collar.y;
      float neckFeather = clamp(fwidth(neckDistance)*.64,.0004,.0018);
      float rear = 1.0-smoothstep(-.030,.018,depth);
      float arm = smoothstep(.150,.194,x)*smoothstep(.81,.96,y);

      // One rail centreline gives all three stripes the same tangent at the collar.
      // Compensate for the shallow depth change where the chest meets the neck.
      float railPerspective = 1.0-.97*(abs(holoTailor.z)-.10);
      float railX = abs(holoTailor.x)/railPerspective;
      float bend = clamp((1.247-holoTailor.y)/.125,0.0,1.0);
      float inner = .073+.056*bend*bend*(3.0-2.0*bend);
      float side = .127-.025*(1.0-smoothstep(.976,1.144,y))+.020*(1.0-smoothstep(.866,.967,y));
      inner = mix(side,inner,smoothstep(1.086,1.136,y));
      float innerDelta = (railX-inner)*railPerspective;
      float railSlope = .056*6.0*bend*(1.0-bend)/.125;
      float railOffset = (railX-inner)*inversesqrt(1.0+railSlope*railSlope);
      float belowNeck = smoothstep(-.0012-neckFeather,-.0012+neckFeather,collarOutside);
      float sideJoin = max(smoothstep(.038,.092,depth),1.0-smoothstep(-.043,.004,depth));
      float innerEnd = mix(sideJoin,1.0,smoothstep(1.173,1.224,y));
      float innerLane = min(abs(railOffset),min(abs(railOffset-.0053),abs(railOffset+.0053)));
      float innerAa = clamp(fwidth(railOffset)*.64,.00032,.00145);
      float innerMask = (1.0-smoothstep(.00120-innerAa*.4,.00120+innerAa,innerLane))
        *smoothstep(1.108,1.159,y)*(1.0-arm)*mix(1.0,.72,rear)*belowNeck*innerEnd;

      // The sleeve seam climbs across the shoulder, then bends inward at the cuff.
      float outer = .155+.048*clamp((1.311-y)/.138,0.0,1.0);
      outer += .014*rear;
      float outerDelta = x-outer;
      float outerLane = min(abs(outerDelta),min(abs(outerDelta-.0060),abs(outerDelta+.0060)));
      float outerAa = clamp(fwidth(outerDelta)*.6,.00055,.0021);
      float outerMask = (1.0-smoothstep(.00155-outerAa*.4,.00155+outerAa,outerLane))
        *smoothstep(1.151,1.190,y)*smoothstep(.126,.146,x);
      float cuffAxis = x+.78*(1.16-y);
      float cuffEdge = .267+.008*smoothstep(.021,.061,depth)-.010*smoothstep(.260,.297,x);
      float cuffDelta = cuffAxis-cuffEdge;
      float cuffLane = min(abs(cuffDelta),abs(cuffDelta-.0072));
      float cuffAa = clamp(fwidth(cuffDelta)*.6,.0006,.0021);
      float cuff = (1.0-smoothstep(.00115-cuffAa*.4,.00115+cuffAa,cuffLane))
        *arm*smoothstep(1.048,1.100,y);
      float panel = smoothstep(-.001,.004,innerDelta)
        *mix(smoothstep(1.10,1.158,y),1.0-smoothstep(-.005,.000,cuffDelta),arm);
      float sidePanel = smoothstep(.000,.005,x-side)*smoothstep(.861,.924,y)
        *(1.0-smoothstep(1.106,1.157,y))*(1.0-arm);
      panel = max(panel,sidePanel*.92);

      // Slim inset beneath the shoulder, with room between the two triple seams.
      float slashT = clamp((x-.079)/.115,0.0,1.0);
      float slashY = 1.302-.043*slashT;
      float slashWidth = .006*(1.0-slashT)+.0020;
      float slash = smoothstep(.008,.014,innerDelta)*(1.0-smoothstep(-.018,-.008,outerDelta))
        *(1.0-smoothstep(slashWidth,slashWidth+.0015,abs(y-slashY)))*(1.0-rear);
      float backPatch = smoothstep(.009,.015,innerDelta)*(1.0-smoothstep(-.014,-.006,outerDelta))
        *smoothstep(1.203,1.211,y)*(1.0-smoothstep(1.257,1.265,y))*rear;
      panel *= 1.0-max(slash,backPatch)*.84;

      // Staggered rings retain dark centres and a small upper catchlight.
      vec3 axes = pow(abs(normalize(cross(dFdx(holoRest),dFdy(holoRest)))),vec3(5.0));
      axes /= max(dot(axes,vec3(1.0)),.00001);
      vec2 pitch = vec2(214.0,226.0);
      float rings = dot(axes,vec3(fabricRing(vec2(depth,y)*pitch),
                                 fabricRing(vec2(holoRest.x,depth)*pitch),
                                 fabricRing(vec2(holoRest.x,y)*pitch)));
      vec3 textile = vec3(.004,.146,.271)+vec3(.032,.250,.386)*rings;
      vec2 pixelGrid = vec2(holoRest.x*76.0+depth*22.0,y*158.0);
      vec2 pixel = fract(pixelGrid)-.5;
      float row = floor(pixelGrid.y);
      float column = floor(pixelGrid.x);
      float spark = step(.91,fract(sin(column*19.47+floor(row/9.0)*36.62)*1836.72));
      float dots = (1.0-smoothstep(.09,.23,length(pixel*vec2(1.48,1.0))))*(.12+.88*spark);
      vec3 navy = vec3(.0018,.018,.046)+vec3(.003,.082,.148)*dots;
      holoTint = mix(navy,textile,panel);

      float innerTrack = (1.0-smoothstep(.0071,.010,abs(innerDelta)))
        *smoothstep(1.111,1.163,y)*(1.0-arm)*belowNeck*innerEnd;
      float outerTrack = (1.0-smoothstep(.0078,.0104,abs(outerDelta)))*smoothstep(1.15,1.188,y)
        *smoothstep(.126,.146,x);
      holoTint = mix(holoTint,navy*.83,max(innerTrack,outerTrack)*.83);
      holoTint = mix(holoTint,vec3(.021,.260,.460),max(max(innerMask,outerMask),cuff)*.97);

      float waistHeight = .913+.039*smoothstep(.074,.145,x);
      float waist = (1.0-smoothstep(.0038,.0070,abs(y-waistHeight)))*torso*(1.0-arm);
      float seamX = .083-.022*clamp((.697-y)/.055,0.0,1.0)+.001*smoothstep(.697,.91,y);
      float legWindow = smoothstep(.553,.568,y)*(1.0-smoothstep(.909,.920,y))
        *smoothstep(.027,.053,depth)*torso*(1.0-arm);
      float piping = (1.0-smoothstep(.0010,.00225,abs(x-seamX)))
        +(1.0-smoothstep(.0007,.00175,abs(x-seamX-.0048)));
      float kneeHeight = .411+.048*pow(clamp(abs(x-.140)/.045,0.0,1.0),2.3);
      float knee = (1.0-smoothstep(.004,.0065,abs(y-kneeHeight)))*smoothstep(.075,.103,x)
        *smoothstep(.006,.040,abs(depth));
      float wrist = (1.0-smoothstep(.0013,.004,abs(x-.418)))*smoothstep(.82,.88,y);
      float detail = clamp(max(max(waist,knee),max(piping*legWindow*.85,wrist)),0.0,1.0);
      holoTint = mix(holoTint,vec3(.024,.217,.358),detail*.94);

      // Match the fabric beneath the skinned collar when the neck bends.
      float bindingFeather=clamp(fwidth(collarOutside)*.6,.00035,.0016);
      float binding=(1.0-smoothstep(-bindingFeather,bindingFeather,collarOutside))
        *smoothstep(-neckFeather,neckFeather,neckDistance);
      float bindingCenter=smoothstep(-.0006,.0006,neckDistance+.52*collarOutside);
      vec3 bindingTint=mix(vec3(.033,.245,.431),vec3(.013,.142,.291),bindingCenter);
      holoTint=mix(holoTint,bindingTint,binding);
      float hands = smoothstep(.421,.431,x)*smoothstep(.80,.84,y);
      holoTint = mix(holoTint,vec3(.100,.379,.667),hands);
    `,
  ],
  'Cortana Collar Binding': ['#409ed8', 'holoTint=vec3(.033,.245,.431);'],
  'Cortana Collar Outer Ring': ['#226b9c', 'holoTint=vec3(.013,.142,.291);'],
  'Cortana Face': [
    '#639ab9',
    String.raw`
      float underChin=.77+.23*smoothstep(1.347,1.409,holoRest.y);
      holoTint=vec3(.120,.457,.753)*underChin;
    `,
  ],
  'Cortana Boots': ['#172b38', [
    'float toe=(1.0-smoothstep(.058,.077,holoRest.y))*smoothstep(.048,.089,holoRest.z);',
    'float sole=smoothstep(.011,.017,holoRest.y);',
    'holoTint=mix(vec3(.007,.029,.049),vec3(.024,.176,.307),toe)*sole+vec3(.004,.008,.010)*(1.0-sole);'
  ].join('\n')],
  'Cortana Eyes': [
    '#4a93bd',
    String.raw`
      vec2 eye=vec2(abs(holoRest.x)-.0295,holoRest.y-1.4742);
      float radius=length(eye);
      float angle=atan(eye.y,eye.x);
      float fibers=.82+.10*sin(angle*38.0+radius*510.0)+.08*sin(angle*61.0);
      float iris=(1.0-smoothstep(.0060,.0069,radius))*smoothstep(.108,.118,holoRest.z);
      float limbal=smoothstep(.0046,.0063,radius);
      float pupil=(1.0-smoothstep(.0021,.0027,radius))*iris;
      vec2 shine=vec2(holoRest.x+.0015-sign(holoRest.x)*.0295,holoRest.y-1.476);
      float glint=exp(-pow(length(shine)/.00075,2.0));
      vec3 irisBlue=mix(vec3(.040,.195,.32)*fibers,vec3(.013,.049,.082),limbal*.76);
      holoTint=mix(vec3(.068,.227,.385),irisBlue,iris);
      holoTint=mix(holoTint,vec3(.005,.013,.026),pupil)+vec3(.09,.19,.29)*glint;
    `,
  ],
  'Cortana Hair': [
    '#07182c',
    String.raw`
      float flow=holoUv.x+.003*sin(holoUv.y*6.0+holoUv.x*12.56)*holoUv.y;
      float detail=1.0-smoothstep(.001,.008,fwidth(flow));
      float fine=.095*sin(flow*1847.0)+.075*sin(flow*2711.0)+.050*cos(flow*993.0);
      float lock=.76+.045*sin(flow*382.0)+.036*cos(flow*547.0);
      float roots=smoothstep(.019,.148,holoUv.y);
      holoTint=vec3(.003,.012,.030)*(.74+roots*(lock+detail*fine)*.64);
    `,
  ],
};

const fabricShader = String.raw`
vec2 collarDistances(vec3 p) {
  // Same tilted neck opening as the two skinned loops authored in Blender.
  float depth=p.z-.013;
  float front=depth/max(length(vec2(p.x,depth)),.001);
  float inside=1.343-.024*front+.002*(1.0-front*front);
  float outside=inside-.0092-.0012*front;
  return vec2(inside,outside)-p.y;
}

float fabricRing(vec2 grid) {
  vec2 mark = fract(grid+vec2(.5*mod(floor(grid.y),2.0),0.0))-.5;
  float footprint = length(fwidth(grid));
  float feather = clamp(footprint*.34,.035,.17);
  float ring = 1.0-smoothstep(.042,.065+feather,abs(length(mark)-.240));
  return ring*mix(.68,1.0,smoothstep(-.15,.16,mark.y))*(1.0-smoothstep(.36,.95,footprint));
}
`;

function hologramMaterial(name, signal) {
  const body = name === 'Cortana Suit' || name === 'Cortana Face';
  const [base, treatment] = shaderParts[name] || shaderParts['Cortana Suit'];
  const color = body ? `
    { ${shaderParts['Cortana Suit'][1]} }
    vec3 uniformTint = holoTint;
    { ${shaderParts['Cortana Face'][1]} }
    float skinOffset = .0004-collarDistances(holoRest).x;
    float skinFeather = clamp(fwidth(skinOffset)*.64,.0004,.0018);
    float faceWeight = smoothstep(-skinFeather,skinFeather,skinOffset);
    holoTint = mix(uniformTint,holoTint,faceWeight);
  ` : treatment;
  const hair = name === 'Cortana Hair';
  const eyes = name === 'Cortana Eyes';
  // The reference is projected in mesh rest space, so details follow the skinned face.
  const reference = body || eyes;
  const badge = body ? `
    vec2 badgeUv=vec2((holoRest.x+.073)/.055,(holoRest.y-1.171)/.015);
    if (badgeUv.x>0.0 && badgeUv.x<1.0 && badgeUv.y>0.0 && badgeUv.y<1.0 && holoRest.z>.056)
      holoTint += texture2D(holoBadge,badgeUv).a*vec3(.11,.40,.58);
  ` : '';
  const roughness = {'Cortana Hair':.58,'Cortana Eyes':.39};
  const material = new T.MeshStandardMaterial({
    color: base, roughness: roughness[name] || .73, metalness: .025,
    side: name === 'Cortana Hair' ? T.DoubleSide : T.FrontSide,
    skinning: true,
  });
  material.customProgramCacheKey = () => 'cortana-hologram/' + name;
  material.onBeforeCompile = shader => {
    shader.uniforms.holoClock = signal.clock;
    shader.uniforms.holoOrbit = signal.orbit;
    shader.uniforms.holoBoot = signal.boot;
    shader.uniforms.holoEnergy = signal.energy;
    shader.uniforms.holoPortrait = {value:signal.portrait};
    shader.uniforms.holoBadge = {value:signal.badge};
    const varying = 'varying vec3 holoRest, holoTailor; varying vec2 holoUv;\n';
    const tailorAttribute = body ? 'attribute vec3 _tailor;\n' : '';
    shader.vertexShader = tailorAttribute + varying + shader.vertexShader.replace('#include <begin_vertex>', 
      '#include <begin_vertex>\nholoRest=position; holoUv=uv; holoTailor='+(body ? '_tailor' : 'position')+';');
    shader.fragmentShader = varying + 'uniform float holoClock, holoBoot, holoEnergy, holoOrbit; uniform sampler2D holoPortrait, holoBadge;\n' + (body ? fabricShader : '') + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', String.raw`
      #include <color_fragment>
      vec3 holoTint = diffuseColor.rgb;
      ${color}
      ${badge}
      diffuseColor.rgb = holoTint;
    `);
    shader.fragmentShader = shader.fragmentShader.replace('#include <tonemapping_fragment>', String.raw`
      float scanDepth = mix(.030,.007,smoothstep(1.294,1.403,holoRest.y));
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
        + vec3(.003,.163,.378)*(rim*mix(.87,.63,skinRegion)+bootEdge+sweep*.07)
        + vec3(.0015,.046,.115)*(halo*.48+holoEnergy*.037);
      ${hair ? `
        // The highlight follows the strands through the turn and around the back.
        vec3 tangent=dFdx(vViewPosition)*dFdy(holoUv.x)-dFdy(vViewPosition)*dFdx(holoUv.x);
        tangent*=inversesqrt(max(dot(tangent,tangent),1e-14));
        vec3 halfLight=normalize(normalize(vViewPosition)+vec3(-.45,.65,.61));
        float along=dot(tangent,halfLight);
        float sheen=pow(max(0.0,1.0-along*along),11.0);
        float lit=max(0.0,dot(normal,vec3(-.45,.65,.61)));
        float strandLight=smoothstep(.035,.19,holoUv.y)*(.91+.09*sin(holoUv.x*781.0));
        gl_FragColor.rgb=gl_FragColor.rgb*.66+vec3(.002,.067,.141)*sheen*lit*strandLight;
        // The reference guides the sweep in the front view. At a turn the
        // highlight comes entirely from the strands and the sculpted surface.
        float crown=smoothstep(1.530,1.619,holoRest.y);
        vec2 frontHair=vec2(611.0+holoRest.x*1762.0,
          265.0-(holoRest.y-1.4742)*(1830.0-226.0*crown));
        vec3 pigment=texture2D(holoPortrait,vec2(frontHair.x,1254.0-frontHair.y)/1254.0).rgb;
        float frontal=1.0-smoothstep(.12,.53,abs(holoOrbit));
        float hairPixels=max(1.0-smoothstep(115.0,145.0,frontHair.y),1.0-smoothstep(.20,.36,pigment.r));
        float surface=smoothstep(.055-.037*crown,.121-.062*crown,holoRest.z);
        float weight=.74*frontal*surface*hairPixels*(1.0-smoothstep(.085,.104,abs(holoRest.x)));
        if (gl_FrontFacing) gl_FragColor.rgb=mix(gl_FragColor.rgb,pow(pigment,vec3(2.2)),weight);
        else gl_FragColor.rgb*=.30;
      ` : ''}
      ${body ? `
        float handsWeight=smoothstep(.421,.431,abs(holoRest.x))*smoothstep(.80,.84,holoRest.y);
        float skinWeight=max(faceWeight,handsWeight);
        float lightness=dot(gl_FragColor.rgb,vec3(.2126,.7152,.0722));
        float skinPaletteBlend=smoothstep(1.336,1.417,holoRest.y);
        vec3 skinPalette=mix(vec3(.105,.449,.748),vec3(.137,.486,.792),skinPaletteBlend);
        vec3 skinBlue=skinPalette*clamp(.70+.62*lightness,.73,1.15)*scan;
        // Shade the undercut in depth so the chin has a clean, curved edge.
        float chinArch=1.378+.006*pow(clamp(abs(holoRest.x)/.048,0.0,1.0),1.6);
        float jawShadow=exp(-pow((holoRest.y-chinArch)/.012,2.0));
        float neckFront=smoothstep(.028,.085,holoRest.z);
        float belowJaw=1.0-smoothstep(.083,.122,holoRest.z);
        float cheekEdge=smoothstep(.038,.066,abs(holoRest.x));
        float cheekHeight=smoothstep(1.385,1.412,holoRest.y)*(1.0-smoothstep(1.463,1.490,holoRest.y));
        skinBlue *= 1.0-.28*jawShadow*neckFront*belowJaw-.22*cheekEdge*cheekHeight;
        float neckBand=smoothstep(1.308,1.330,holoRest.y)*(1.0-smoothstep(1.373,1.395,holoRest.y));
        float neckY=clamp(436.0+(1.379-holoRest.y)*1730.0,434.0,539.0);
        float neckX=611.0+holoRest.x*1540.0;
        vec3 neckPlate=texture2D(holoPortrait,vec2(neckX,1254.0-neckY)/1254.0).rgb;
        float neckLight=.67*neckBand*neckFront*belowJaw*smoothstep(.35,.56,neckPlate.g);
        skinBlue=mix(skinBlue,pow(neckPlate,vec3(2.2)),neckLight);
        skinBlue += mix(vec3(.002,.070,.147),vec3(.003,.133,.261),neckBand)*rim;
        gl_FragColor.rgb=mix(gl_FragColor.rgb*vec3(.47,1.0,1.03),skinBlue,skinWeight);
      ` : ''}
      ${reference ? `
        // Registration against the supplied portrait: irises at x=559/663, y=265.
        float heightFromEyes=holoRest.y-1.4742;
        float referenceY=265.0-heightFromEyes*(heightFromEyes>0.0?1830.0:1930.0);
        referenceY-=12.0*smoothstep(1.375,1.410,holoRest.y)*(1.0-smoothstep(1.44,1.4742,holoRest.y));
                vec2 portraitPixel=vec2(611.0+holoRest.x*1762.0,referenceY);
        vec3 plate=texture2D(holoPortrait,vec2(portraitPixel.x,1254.0-portraitPixel.y)/1254.0).rgb;
        vec3 portraitColor=pow(plate,vec3(2.2));
        float py=clamp(referenceY,154.0,463.0);
        float left=511.0+45.0*(1.0-smoothstep(181.0,238.0,py))
          +66.0*(1.0-smoothstep(149.0,182.0,py))+49.0*smoothstep(343.0,450.0,py);
        float right=730.0-31.0*(1.0-smoothstep(180.0,252.0,py))
          -43.0*(1.0-smoothstep(146.0,182.0,py))-60.0*smoothstep(354.0,453.0,py);

        ${body ? `
          // Sample inside the reference's hairline when the 3D fringe reveals extra skin.
          vec2 skinPixel=vec2(clamp(portraitPixel.x,left+7.0,right-7.0),py);
          plate=texture2D(holoPortrait,vec2(skinPixel.x,1254.0-skinPixel.y)/1254.0).rgb;
          portraitColor=pow(plate,vec3(2.2));
          float front=smoothstep(.068,.106,holoRest.z);
          float faceHeight=smoothstep(1.360,1.395,holoRest.y);
          float atEdge=1.0-smoothstep(.058,.090,abs(holoRest.x));
          vec2 orbit=vec2((abs(holoRest.x)-.0295)/.0076,(holoRest.y-1.4742)/.0068);
          float aroundIris=smoothstep(.72,1.20,length(orbit));
          float notHair=smoothstep(.24,.43,plate.g);
          float inset=min(portraitPixel.x-left,right-portraitPixel.x);
          float feather=smoothstep(-15.0,11.0,inset)
            *smoothstep(144.0,163.0,referenceY)*(1.0-smoothstep(430.0,466.0,referenceY));
          float portraitView=1.0-smoothstep(.24,1.08,abs(holoOrbit));
          float weight=mix(.25,.98,portraitView)*front*faceHeight*atEdge*mix(.89,1.0,aroundIris)*notHair*feather;
        ` : `
          float pupilX=holoRest.x<0.0?559.0:663.0;
          float eyeX=holoRest.x-sign(holoRest.x)*.0295;
          vec2 eyePixel=vec2(pupilX+eyeX*1770.0,265.0-(holoRest.y-1.4742)*1790.0);
          portraitColor=pow(texture2D(holoPortrait,vec2(eyePixel.x,1254.0-eyePixel.y)/1254.0).rgb,vec3(2.2));
          // Retain the reference's iris detail and keep the sclera in the same blue light.
          float eyeLight=dot(portraitColor,vec3(.2126,.7152,.0722));
          portraitColor=eyeLight*vec3(.28,1.0,1.59);
          gl_FragColor.rgb*=vec3(.43,.83,1.0);
          float weight=.67*smoothstep(.105,.120,holoRest.z)
            *(1.0-smoothstep(.0070,.0120,abs(eyeX)));
        `}
        gl_FragColor.rgb=mix(gl_FragColor.rgb,portraitColor,weight);
      ` : ''}
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
  const signal = {clock:{value:0},boot:{value:0},energy:{value:0},orbit:{value:0},
    portrait:textureLoader.load('/cortana-front-reference.png'),badge:new T.CanvasTexture(badgeCanvas)};
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
    signal.orbit.value=Math.atan2(Math.sin(angle),Math.cos(angle));
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
  const ready = new T.GLTFLoader().loadAsync('/cortana-hologram-portrait.glb?v=20261109-avatar-finish').then(gltf=>{
    model=gltf.scene;
    model.traverse(mesh=>{
      if(!mesh.isMesh) return;
      const name=mesh.material.name;
      if (name === 'Cortana Piping') {
        mesh.visible=false;
        return;
      }
      // The neck spans two mesh primitives. Shade both with the same material.
      const materialName=name==='Cortana Face' ? 'Cortana Suit' : name;
      // Keep the baked garment coordinates attached to the surface during motion.
      if (materialName === 'Cortana Suit' && !mesh.geometry.hasAttribute('_tailor')) {
        mesh.geometry.setAttribute('_tailor',mesh.geometry.getAttribute('position'));
      }
      if(!materials.has(materialName)) materials.set(materialName,hologramMaterial(materialName,signal));
      mesh.material=materials.get(materialName);
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
