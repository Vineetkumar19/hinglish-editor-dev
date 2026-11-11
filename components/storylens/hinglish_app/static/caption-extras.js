/* All caption families live together; existing native/text executors are reused. */
(()=>{
 const root=document.getElementById('autoCaptionPanel'),chooser=window.storylensWeb3DCaptions;
 if(!root||!chooser)return;
 const nav=root.querySelector('.c3-families'),normal=[...root.children].filter(n=>!n.classList.contains('caption-3d'));
 const extra=document.createElement('section');extra.className='caption-extra';extra.hidden=true;root.append(extra);
 let selected=null;
 function reset(){extra.hidden=true;extra.replaceChildren();for(const n of normal){if(n.dataset.captionExtraHidden!==undefined){n.hidden=n.dataset.captionExtraHidden==='true';delete n.dataset.captionExtraHidden;}}for(const b of nav.querySelectorAll('[data-extra]'))b.setAttribute('aria-pressed','false');selected=null;}
 nav.addEventListener('click',e=>{if(e.target.closest('[data-family]'))reset();},true);
 for(const [id,label,url] of [['cinematic','Cinematic','editor-panel.html?host=aftereffects&browser=1&tool=textEffects&textOnly=1'],['important','Important words','important-captions.html']]){
  const button=document.createElement('button');button.type='button';button.dataset.extra=id;button.textContent=label;button.setAttribute('aria-pressed','false');
  button.onclick=()=>{if(chooser.isRunning()||window.storylensCaptionGenerator?.isRunning?.())return;reset();chooser.select('standard');selected=id;for(const n of normal){n.dataset.captionExtraHidden=String(n.hidden);n.hidden=true;}nav.querySelector('[data-family="standard"]').setAttribute('aria-pressed','false');button.setAttribute('aria-pressed','true');const frame=document.createElement('iframe');frame.src=url+(url.includes('?')?'&':'?')+'embedded=1';frame.title=label;extra.replaceChildren(frame);extra.hidden=false;};
  nav.append(button);
 }
 document.addEventListener('storylensmodechange',()=>{if(typeof mode!=='undefined'&&mode!=='captions'&&selected){reset();chooser.select('standard');}});
 const route=new URLSearchParams(location.search).get('tool');
 if(['textEffects','nativeCaptions'].includes(route)){setMode('captions');document.body.classList.add('tools-visible');if(route==='textEffects')nav.querySelector('[data-extra="cinematic"]').click();else chooser.select('3d1');}
})();
