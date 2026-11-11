/* Short tool inventory shown inside opened features only. */
(() => {
  const tools={voiceover:'Qwen · VoiceStudio · OmniVoice · PyAV',photos:'Local Vision · Web search · Pixel matching',downloader:'yt-dlp · FFmpeg',clean:'Silero VAD · PyAV',script:'Qwen · Qwen ASR',captions:'Hyperframes / Qwen + Vision',
    'auto-caption-2':'Hyperframes / Qwen + Vision',broll:'Qwen · Website search',visuals:'Qwen · Web image search',
    zoom:'OpenCV YuNet · FFmpeg',sound:'Qwen · Vision · CLAP · Clipwing · Earshot · Openverse',eyecontact:'Hsu ONNX · MediaPipe',shorts:'Qwen · FFmpeg',
    aivideo:'Qwen · Wan / GSAP · Three.js · Agent Reach',motion:'Qwen + Vision · Agent Reach · PNG · GSAP · Hyperframes · ThreeUI',gaming:'Qwen · FFmpeg',thumbnail:'Qwen · Z-Image Turbo · Pillow',
    cinematic:'Visual comparison · NVIDIA export',colorGrade:'Resolve native nodes',reelRecreate:'Native editable layers',templateImport:'After Effects panel',templateAligner:'After Effects panel',templateText:'Speech alignment · Native text',copyPaste:'Adobe panel',imageDownload:'Clipboard · Download',nativeCaptions:'Native AE 3D',presetLibrary:'After Effects library',animationPresets:'Native presets',textEffects:'Native text templates',effectsLibrary:'Native effects',beats:'NumPy · PyAV',publisher:'Qwen · Browser / APIs',chrome:'Chrome extension',workflow:'Local LLM · Storylens tools',
    assistant:'Qwen · Storylens tools'};
  for (const key of ['thumbnail','aivideo','sound','captions','auto-caption-2']) tools[key]+=' · ReelMimic refs';
  const css=document.createElement('style');css.textContent='.feature-tools{display:block!important;font-size:10px!important;line-height:1.4;letter-spacing:.015em;color:#b6c1cb!important;margin:4px 0 0!important;font-weight:500!important;overflow-wrap:anywhere}.feature-tools-heading{font-size:12px!important;margin:5px 0 10px!important}';document.head.append(css);
  const badge=(parent,value,heading=false)=>{if(!value)return;const tag=document.createElement('small');tag.className='feature-tools'+(heading?' feature-tools-heading':'');tag.textContent=value;tag.setAttribute('aria-label','Tools: '+value);parent.append(tag);return tag;};
  const title=document.querySelector('#modeTitle');
  if(title){const tag=badge(title.parentElement,tools[document.querySelector('.mode.active')?.dataset.mode],true);new MutationObserver(()=>{const value=tools[document.querySelector('.mode.active')?.dataset.mode]||'';tag.textContent=value;tag.setAttribute('aria-label','Tools: '+value);}).observe(title,{childList:true,subtree:true,characterData:true});}
  else{const id=location.pathname.split('/').pop().replace('.html','');const heading=document.querySelector('main h1,main h2,h1,h2');if(heading&&tools[id]){const span=document.createElement('div');heading.after(span);badge(span,tools[id],true);}}
})();
