/* One paused GSAP timeline, measured layout and absolute-time ThreeUI rendering. */
(() => {
  let W = 1920, H = 1080;
  let timeline, orbit, duration = 4, sceneData, layoutErrors = [], soundEvents = [];
  const stage = document.getElementById('stage');
  const element = (tag, cls, text, parent) => {
    const node = document.createElement(tag); node.className = cls;
    if (text != null) node.textContent = String(text);
    parent.append(node); return node;
  };
  function fit(node, maxHeight) {
    let size = parseFloat(getComputedStyle(node).fontSize);
    while ((node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > maxHeight) && size > 24) {
      size -= 2; node.style.fontSize = size + 'px';
    }
  }
  function measure() {
    const content = stage.querySelector('.content');
    stage.querySelectorAll('.title').forEach(n => fit(n, H * .3));
    stage.querySelectorAll('.value').forEach(n => fit(n, H * .28));
    stage.querySelectorAll('.support').forEach(n => fit(n, H * .15));
    stage.querySelectorAll('.step').forEach(n => fit(n, H * .18));
    // Scale the whole fixed layout only as a last resort, never the visible prefix.
    const limit = H * (stage.querySelector('.orbit') ? .39 : .75);
    if (content.scrollHeight > limit) {
      const ratio = limit / content.scrollHeight;
      content.querySelectorAll('.title,.value,.support,.step').forEach(n => {
        n.style.fontSize = Math.max(22, parseFloat(getComputedStyle(n).fontSize) * ratio) + 'px';
      });
    }
    layoutErrors = [];
    content.querySelectorAll('.title,.value,.support,.step').forEach(n => {
      const r = n.getBoundingClientRect(), b = stage.getBoundingClientRect();
      if (n.scrollWidth > n.clientWidth + 2 || r.left < b.left + b.width * .04 || r.right > b.left + b.width * .96 ||
          r.top < b.top + b.height * .04 || r.bottom > b.top + b.height * .96) layoutErrors.push('Text needs more space: ' + n.textContent);
    });
  }
  window.mgLoad = async scene => {
    if (!window.gsap) throw new Error('Creative motion tools missing: GSAP');
    timeline?.kill(); orbit?.dispose(); orbit = null;
    window.__timelines = {}; stage.replaceChildren();
    W = stage.clientWidth; H = stage.clientHeight;
    sceneData = scene; duration = Math.max(.5, Number(scene.duration) || 4);
    document.body.className = scene.width >= scene.height ? 'landscape' : 'portrait';
    stage.className = scene.mode === 'overlay' ? 'overlay' : 'full';
    ['--bg','--paper','--accent','--panel'].forEach(k => stage.style.removeProperty(k));
    Object.entries(scene.theme || {}).forEach(([k,v]) => { if (/^--[a-z-]+$/.test(k)) stage.style.setProperty(k, String(v)); });
    const d = scene.data || {}, kind = scene.template;
    const group = element('div', 'composition ' + (kind === 'orbital_title' ? 'orbit' : kind === 'product_card' ? 'product' : kind === 'asset_hero' ? 'has-assets' : ''), null, stage);
    if (kind === 'orbital_title' || (kind === 'asset_hero' && d.depth)) {
      const canvas = element('canvas', 'orbital', null, group);
      try {
        orbit = StorylensOrbit.createOrbitalSphereRenderer(canvas, () => ({...StorylensOrbit.ORBITAL_SPHERE_DEFAULTS, speed:.65, particleOpacity:.58, orbitOpacity:.14}));
        orbit.resize(W, H); orbit.render(0);
      } catch (error) { throw new Error('Creative depth unavailable: ' + error.message); }
    }
    if (kind === 'asset_hero') {
      if (!d.assets?.length) throw new Error('Motion assets unavailable: this scene needs a saved image.');
      const visuals = element('div','asset-visuals',null,group);
      for (const asset of d.assets.slice(0,2)) {
        const layer = element('div','asset-layer',null,visuals);
        const img = element('img','asset-picture',null,layer); img.src = asset.src;
        await img.decode();
      }
    }
    const content = element('section', 'content', null, group);
    const rule = element('div', 'rule', null, content);
    if (kind === 'product_card' && d.assets?.[0]?.src) {
      const img = element('img', 'product-image', null, content); img.src = d.assets[0].src;
      await img.decode();
    }
    const title = element('h1', 'title', null, content);
    String(d.title || '').split(/(\s+)/).filter(Boolean).forEach(w => {
      if (/^\s+$/.test(w)) title.append(document.createTextNode(' '));
      else element('span', '', w, title);
    });
    if (kind === 'motion_number') element('div', 'value accent', d.value || '', content);
    if (d.label) element('p', 'support', d.label, content);
    if (kind === 'explainer_steps') {
      const steps = element('div', 'steps', null, content);
      (d.items || []).slice(0,4).forEach((text, i) => {
        const step = element('div', 'step', null, steps);
        element('span', 'step-index', String(i+1).padStart(2,'0'), step); element('span','step-copy',text,step);
      });
    }
    await document.fonts.ready; measure();
    const entrance = Math.min(.65, duration * .2), leave = Math.min(.3, duration * .12);
    soundEvents = [{time:0,phase:'entrance',label:d.title || kind},
      {time:entrance,phase:'landing',label:'main entrance settles'},
      {time:duration-leave,phase:'exit',label:'motion fades out'}];
    const words = title.querySelectorAll('span');
    const stagger = Math.min(.07, entrance * .4 / Math.max(1, words.length - 1));
    timeline = gsap.timeline({paused:true});
    timeline.fromTo(rule,{scaleX:0},{scaleX:1,duration:entrance,ease:'power3.out'},0);
    timeline.fromTo(words,{opacity:0,y:28},{opacity:1,y:0,duration:entrance*.6,stagger,ease:'power3.out'},0);
    timeline.fromTo(content.querySelectorAll('.support,.value,.product-image'),{opacity:0,y:18},
      {opacity:1,y:0,duration:entrance*.7,ease:'power2.out'},entrance*.25);
    const steps = content.querySelectorAll('.step');
    steps.forEach((step,i) => soundEvents.push({time:entrance*.95+i*Math.min(.17,duration*.08),
      phase:'landing',label:step.textContent}));
    if (steps.length) timeline.fromTo(steps,{opacity:0,y:22},{opacity:1,y:0,duration:entrance*.65,
      stagger:Math.min(.17,duration*.08),ease:'power3.out'},entrance*.3);
    if (kind === 'product_card') timeline.fromTo(content,{rotationY:-8,scale:.94},{rotationY:0,scale:1,duration:entrance,ease:'power3.out'},0);
    const layers = group.querySelectorAll('.asset-layer');
    layers.forEach((layer,i) => soundEvents.push({time:entrance+i*.12,phase:'landing',
      label:d.assets?.[i]?.label || d.assets?.[i]?.name || `visual asset ${i+1}`}));
    if (layers.length) {
      const from = {opacity:0, x:0, y:0, scale:1};
      if (d.motion === 'slide-left') from.x = 110;
      else if (d.motion === 'slide-right') from.x = -110;
      else if (d.motion === 'push') from.scale = .82;
      else from.y = d.motion === 'float' ? 35 : 80;
      timeline.fromTo(layers,from,{opacity:1,x:0,y:0,scale:1,duration:entrance,stagger:.12,ease:'power3.out'},0);
      timeline.to(group.querySelectorAll('.asset-picture'),{y:-14,x:8,duration:Math.max(.1,duration-entrance-leave),ease:'sine.inOut'},entrance);
    }
    timeline.to(group,{opacity:0,duration:leave,ease:'power2.in'},duration-leave);
    // Explicit duration makes out-of-order seeks and the terminal frame repeatable.
    timeline.set(group,{opacity:0},duration);
    window.__timelines.main = timeline;
    window.mgSeek(0); return true;
  };
  window.mgSeek = seconds => {
    const t = Math.min(duration, Math.max(0, Number(seconds) || 0));
    timeline?.totalTime(t, false).pause(); orbit?.render(t); return true;
  };
  window.mgReady = () => document.fonts.ready.then(() => true);
  window.mgCheck = () => [...layoutErrors];
  window.mgSoundEvents = () => soundEvents.map(e => ({...e}));
  window.mgReceipt = () => ({engine:'GSAP',version:gsap.version,template:sceneData?.template,
    clock:'absolute seconds',depth:!!orbit,errors:[...layoutErrors]});
  window.addEventListener('hf-seek', e => e.detail.waitUntil(Promise.resolve(window.__creativeReady).then(() => window.mgSeek(e.detail.time))));
})();
