// Review-only cinematic caption reference engine; font metrics and times shared with local export.
(()=>{
 const config=project.cinematic_reference_profile;if(!config)return;
 const originalDraw=draw,canvas=document.createElement('canvas'),pen=canvas.getContext('2d');
 canvas.style.cssText='display:block;width:100%;height:auto';canvas.setAttribute('role','img');
 draw=function(){
  originalDraw();if(!config[currentStyle]||visibility==='spoken')return;
  const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end);
  if(index<0){caption.replaceChildren();return}
  const q=cues[index],words=wordsAt(index),W=1280,H=Math.round(W*stage.clientHeight/stage.clientWidth),limit=H>=W?4:7;
  canvas.width=W;canvas.height=H;
  let a=0;for(let i=0;i<words.length;i+=limit)if((i?q.words[i].start:q.start)<=now)a=i;
  const b=Math.min(words.length,a+limit),cfg=config[currentStyle],ratio=H>=W?W/720*1.3:Math.min(W/1280,H/720),runs=[];let span=0;
  for(let i=a;i<b;i++){
   const script=currentStyle==='cinematic_mixed_draft'&&i===a,bold=currentStyle==='cinematic_mixed_draft'&&cfg.bold_words.includes((q.template_source?.split(/\s+/)[i]||words[i]).replace(/[,.!?]/g,'').toLowerCase());
   const points=(script?cfg.script_size:cfg.size)*ratio,chosen=$('#font').value,family=script?'Great Vibes':bold?'Inter Caption 1':'Roboto',css=chosen==='template'?`${bold?700:400} ${points}px "${family}"`:`400 ${points}px ${fonts[chosen].css}`;
   pen.font=css;runs.push({i,x:span,css,points});span+=pen.measureText(words[i]).width+cfg.space*ratio;
  }
  span-=cfg.space*ratio;const fit=Math.min(1,W*.88/span),baseline=H*templates[currentStyle].default_position+cfg.size*ratio*.32;
  pen.save();pen.translate(W/2,H*templates[currentStyle].default_position);pen.scale(fit,fit);pen.translate(-W/2,-H*templates[currentStyle].default_position);
  for(const r of runs){
   if(now<q.words[r.i].start||(visibility==='styled_spoken'&&now>=q.words[r.i].end))continue;
   const p=Math.max(0,Math.min(1,(now-q.words[r.i].start)/cfg.fade));
   pen.font=r.css;pen.globalAlpha=p*p*(3-2*p);pen.filter=`blur(${cfg.blur*ratio*(1-p)}px)`;pen.fillStyle=wordColors[index]?.[r.i]||'#FFFFFF';
   pen.fillText(words[r.i],(W-span)/2+r.x,baseline+cfg.rise*ratio*(1-p)**3);
  }
  pen.restore();canvas.setAttribute('aria-label',words.slice(a,b).filter((_,i)=>now>=q.words[a+i].start).join(' '));
  caption.replaceChildren(canvas);caption.className='cinematic-reference-draft';
  Object.assign(caption.style,{left:'0',right:'0',top:'50%',width:'100%',maxWidth:'none',transform:'translateY(-50%)',padding:'0',background:'transparent',opacity:'1',filter:'none',visibility:'visible'});updateSelection();
 };
 Promise.all([document.fonts.load('400 40px Roboto'),document.fonts.load('400 44px "Great Vibes"'),document.fonts.load('700 32px "Inter Caption 1"')]).then(()=>draw());
 video.addEventListener('seeked',draw);video.addEventListener('pause',draw);
})();
