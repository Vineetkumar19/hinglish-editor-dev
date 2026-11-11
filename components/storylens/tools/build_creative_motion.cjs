// Bake the pinned GSAP easing functions once for the native Smart Visuals renderer.
const fs = require('node:fs');
const path = require('node:path');
const {gsap} = require('../hinglish_motion/web/vendor/gsap.min.js');
const curves = {};
for (const name of ['power3.out', 'power2.in', 'sine.inOut']) {
  const ease = gsap.parseEase(name);
  curves[name] = Array.from({length:2049}, (_,i) => Number(ease(i / 2048).toFixed(9)));
}
fs.writeFileSync(path.join(__dirname,'../hinglish_motion/gsap_curves.json'), JSON.stringify({
  engine:'GSAP',version:gsap.version,samples:2049,curves
}));
