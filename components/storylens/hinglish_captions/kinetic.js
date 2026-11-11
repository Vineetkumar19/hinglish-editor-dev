// Kinetic Documentary uses a canvas so font metrics, spacing, reveal frames and
// simple layout and colors follow the same plan as the Python exporter.
(() => {
  const config = project.kinetic_profile;
  if (!config) return;
  // Generated studios can also be opened from older server sessions. Reuse
  // Storylens' shared catalog and collapsible diagnostics for their save errors.
  if (!window.storylensProblem && location.protocol !== 'file:') {
    const feedback = document.createElement('script');
    feedback.src = '/feedback.js';document.head.append(feedback);
  }
  const normalize = word => String(word).toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]/gu, '');
  function planFor(words, overrideEffect=null) {
    const tokens = words.map(normalize), key = tokens.join(' ');
    let known = config.phrases.find(row => row.text.split(/\s+/).map(normalize).join(' ') === key);
    if(storylensTemplateRebound(words))known=null;
    if (!words.length) return {top:[],hero:[],bottom:[],effect:'plain',color:0};
    if(!known&&words.length===1)return {top:[],hero:[[0]],bottom:[],effect:overrideEffect||'plain',color:0};
    if(!known){const p=storylensTemplatePattern(words,config.phrases.map(r=>({...r,rows:[{words:r.top,role:'support'},...r.hero.map(ids=>({words:ids,role:'main'})),{words:r.bottom,role:'footer'}]})));const {rows,top,hero,bottom,...rest}=p;return {...rest,top:words.map((_,i)=>i).slice(0,p.rows.find(r=>r.role==='main')?.words[0]??0),hero:[[p.rows.find(r=>r.role==='main')?.words[0]??0]],bottom:words.map((_,i)=>i).slice((p.rows.find(r=>r.role==='main')?.words[0]??0)+1),effect:overrideEffect||(['stack','bar'].includes(p.effect)?'plain':p.effect)}}
    const stops = new Set(config.stop_words);
    const candidates=known?known.hero.flat():words.map((_,i)=>i);
    let hero = 0, score = -Infinity;
    candidates.forEach(i => {const word=tokens[i],next = word.length*3-(stops.has(word)?100:0); if (next>score) {score=next;hero=i}});
    const seed = Array.from(key).reduce((sum,c)=>sum+c.codePointAt(0),0);
    let effect = overrideEffect || (known?known.effect:['plain','plain','echo','plain','plain','plain'][seed%6]);
    if(effect==='stack'||effect==='bar')effect='plain';
    const result={top:words.slice(0,hero).map((_,i)=>i),hero:[[hero]],bottom:words.slice(hero+1).map((_,i)=>i+hero+1),effect,color:known?known.color:seed%3};
    for(const field of ['handwriting','handwriting_ratio','handwriting_gap_ratio','hero_offset_ratio','support_ratio','top_gap_ratio'])if(known && field in known)result[field]=known[field];
    return result;
  }
  const highlightColor = words => '#FFFFFF';
  const smooth = value => {const p=Math.max(0,Math.min(1,value));return p*p*(3-2*p)};
  function echoScale(age) {
    const keys=config.echo_zoom;
    if(age<=keys[0][0])return keys[0][1];
    for(let i=1;i<keys.length;i++){
      const a=keys[i-1],b=keys[i];
      if(age<=b[0])return a[1]+(b[1]-a[1])*(age-a[0])/(b[0]-a[0]);
    }
    return keys[keys.length-1][1];
  }
  const canvas = document.createElement('canvas');
  canvas.width=1080;canvas.height=Math.round(1080*config.region_ratio);
  canvas.style.cssText='display:block;width:100%;height:auto;margin:0';
  canvas.setAttribute('role','img');
  const context=canvas.getContext('2d'), originalDraw=draw;
  // Check the running renderer's capability, not its persistent bridge token.
  // Authentication identity does not identify the loaded renderer revision.
  const saveCurrentEdits=studioSave.onclick;
  let checkingEngine=false;
  studioSave.addEventListener('click',async event=>{
    if(!['kinetic_documentary','caption_one'].includes(templates[currentStyle]?.layout))return;
    event.preventDefault();event.stopImmediatePropagation();
    if(checkingEngine||studioSaving)return;
    checkingEngine=true;studioSave.disabled=true;
    try{
      const request=window.storylensFetch||fetch;
      const bridgeResponse=await request('/api/bridge',{cache:'no-store'});
      if(!bridgeResponse.ok)throw new Error('Could not connect to the caption exporter. Refresh the editor and try again.');
      const bridge=await bridgeResponse.json();studioBridge=bridge;
      const runtimeResponse=await request('/api/captions/capabilities',{cache:'no-store',headers:{'X-Hinglish-Token':bridge.token}});
      if(!runtimeResponse.ok)throw new Error('Could not check the caption exporter. Refresh the editor and retry; your draft is kept.');
      const runtime=await runtimeResponse.json();
      if(!(runtime.reference_layout_revision>=2))throw Object.assign(new Error('Restart Storylens to load the current reference caption exporter, then retry. Your saved captions and draft are kept.'),{code:'caption_restart_required',details:'The running exporter does not advertise reference_layout_revision 2.'});
      await saveCurrentEdits();
    }catch(error){
      persistStudio();
      studioStatus.textContent=window.storylensError?window.storylensError(error):error.message;
    }finally{checkingEngine=false;if(!studioSaving)studioSave.disabled=false}
  },true);
  // The normal size control and saved per-word colors are also used by export.
  const controls=document.createElement('div');
  controls.innerHTML=`<p class="studio-hint">Reference typography without background stripes. 10% smaller by default. Size (%) adjusts every caption group.</p>
    <button id="kineticDefaultSize" type="button">Reset to default size</button>`;
  $('#sizeNumber').parentElement.after(controls);
  function heroWords(index){return wordsAt(index).map(w=>w.replace(/^[.,!?:;"']+|[.,!?:;"']+$/g,'')||w)}
  function refreshControls(){controls.hidden=templates[currentStyle]?.layout!=='kinetic_documentary'}
  controls.querySelector('button').onclick=()=>{setCaptionScale(1);dirtyStudio();draw()};
  function renderKinetic(q,index,now) {
    const W=canvas.width,unit=Math.min(W,W*stage.clientHeight/Math.max(1,stage.clientWidth)*config.landscape_unit_ratio)*(config.default_scale??.9);
    const H=Math.round(unit*config.region_ratio);if(canvas.height!==H)canvas.height=H;
    const words=heroWords(index),plan=planFor(words,templates[currentStyle].reference_effect),colors=wordColors[index]||[];
    const heroIndex=plan.hero[0]?.[0];
    context.clearRect(0,0,W,H);if(heroIndex===undefined)return;
    canvas.style.transform='none';
    canvas.dataset.heroWord=words[heroIndex];
    canvas.dataset.heroColor=colors[heroIndex]||highlightColor(words);
    const enter=config.enter_frames/config.reference_fps;
    const leave=smooth((q.end-now)/(config.exit_frames/config.reference_fps));
    const gap=unit*config.gap_ratio,safe=W*config.safe_width*(config.default_scale??.9);
    const chosen=$('#font').value;
    const main=chosen==='template'?'Impact':(fonts[chosen]?.css||'Impact');
    const mainWeight=chosen==='template'?'400':'700';
    function font(ids,ratio,family,weight='400',script=false) {
      const text=ids.map(i=>script?words[i]:words[i].toUpperCase()).join(' ')||'H';
      let size=Math.max(2,Math.round(unit*ratio));
      context.font=`${weight} ${size}px ${family}`;
      const width=context.measureText(text).width;
      if(width>safe)size=Math.max(2,Math.floor(size*safe/width));
      const css=`${weight} ${size}px ${family}`;context.font=css;
      const metrics=context.measureText('H');
      return {css,size,family,weight,cap:metrics.actualBoundingBoxAscent+metrics.actualBoundingBoxDescent};
    }
    const isScript=plan.effect==='script';
    const hero=font([heroIndex],isScript?config.script_ratio:config.hero_ratio,isScript?'Inkfree':main,isScript?'400':mainWeight,isScript);
    context.font=hero.css;
    const heroMetrics=context.measureText(isScript?words[heroIndex]:words[heroIndex].toUpperCase());
    hero.cap=heroMetrics.actualBoundingBoxAscent+heroMetrics.actualBoundingBoxDescent;
    const heroTop=H/2-hero.cap/2+unit*(plan.hero_offset_ratio||0);
    const handwriting=plan.handwriting||[],smallTop=plan.top.filter(i=>!handwriting.includes(i));
    const small=font([...smallTop,...plan.bottom],plan.support_ratio??config.small_ratio,'Arial','700');
    const topGap=unit*(plan.top_gap_ratio??config.gap_ratio);
    context.textBaseline='alphabetic';
    function visible(i) {
      const word=q.words[i];return word && word.start<=now && (visibility!=='styled_spoken'||now<word.end);
    }
    const alpha=i=>visible(i)?smooth((now-q.words[i].start)/enter)*leave:0;
    function row(ids,selected,y,script=false,outline=false,opacity=1) {
      context.font=selected.css;
      const texts=ids.map(i=>script?words[i]:words[i].toUpperCase());
      let x=(W-context.measureText(texts.join(' ')).width)/2;
      const space=context.measureText(' ').width;
      const baseline=y+context.measureText(texts.join(' ')||'H').actualBoundingBoxAscent;
      ids.forEach((i,j)=>{
        const text=texts[j],metrics=context.measureText(text);
        const fade=alpha(i);
        if(fade>0){
          const color=colors[i]||(i===heroIndex?highlightColor(words):'#FFFFFF');
          context.save();context.globalAlpha=fade;
          const blur=(1-fade)*unit*.005;context.filter=blur>.15?`blur(${blur}px)`:'none';
          if(outline){
            context.globalAlpha=fade*opacity;
            context.strokeStyle=color;context.lineWidth=Math.max(1,Math.round(unit/540))*2;
            context.strokeText(text,x,baseline);
          }else{
            context.fillStyle='#000000';context.globalAlpha=leave;context.fillText(text,x,baseline);
            context.fillStyle=color;context.globalAlpha=fade;context.fillText(text,x,baseline);
          }
          context.restore();
        }
        x+=metrics.width+space;
      });
    }
    context.save();
    if(config.zoom_styles.includes(currentStyle)){
      const scale=echoScale(now-q.words[heroIndex].start),ax=W/2,ay=heroTop+hero.cap/2;
      context.translate(ax,ay);context.scale(scale,scale);context.translate(-ax,-ay);
    }
    if(plan.effect==='echo'){
      const echo={...hero,size:Math.round(hero.size*(config.echo_ratio??1.15))};
      echo.css=`${echo.weight} ${echo.size}px ${echo.family}`;context.font=echo.css;
      const measured=context.measureText(words[heroIndex].toUpperCase()).width;
      const cameraPeak=config.zoom_styles.includes(currentStyle)?Math.max(...config.echo_zoom.map(k=>k[1])):1,echoSafe=W*.90/cameraPeak;
      if(measured>echoSafe){echo.size=Math.floor(echo.size*echoSafe/measured);echo.css=`${echo.weight} ${echo.size}px ${echo.family}`}
      row([heroIndex],echo,heroTop+hero.cap*(config.echo_offset??.28),false,true,config.echo_opacity??.16);
    }
    if(handwriting.length){
      const script=font(handwriting,plan.handwriting_ratio,'Inkfree','400',true);
      context.font=script.css;const metrics=context.measureText(handwriting.map(i=>words[i]).join(' '));
      const cap=metrics.actualBoundingBoxAscent+metrics.actualBoundingBoxDescent;
      row(handwriting,script,heroTop-small.cap-topGap-unit*plan.handwriting_gap_ratio-cap,true);
    }
    row(smallTop,small,heroTop-small.cap-topGap);
    row([heroIndex],hero,heroTop,isScript,plan.effect==='outline');
    row(plan.bottom,small,heroTop+hero.cap+gap);
    context.restore();
    canvas.setAttribute('aria-label',words.filter((_,i)=>visible(i)).join(' '));
  }
  video.removeEventListener('seeked',originalDraw);video.removeEventListener('pause',originalDraw);window.removeEventListener('resize',originalDraw);
  draw=function(){
    originalDraw();refreshControls();
    if(templates[currentStyle]?.layout!=='kinetic_documentary' || visibility==='spoken')return;
    const now=video.currentTime,index=cues.findIndex(q=>q.start<=now && now<q.end);
    if(index<0){caption.replaceChildren();return}
    const q=cues[index];caption.replaceChildren(canvas);
    caption.className='kinetic-reference';
    Object.assign(caption.style,{left:'0',right:'0',top:(templates[currentStyle].default_position*100)+'%',width:'100%',maxWidth:'none',
      transform:'translateY(-50%)',filter:'none',opacity:'1',background:'transparent',visibility:'visible',padding:'0',textShadow:'none'});
    renderKinetic(q,index,now);updateSelection();
  };
  video.addEventListener('seeked',draw);video.addEventListener('pause',draw);window.addEventListener('resize',draw);
  draw();document.fonts.ready.then(()=>draw());
})();
