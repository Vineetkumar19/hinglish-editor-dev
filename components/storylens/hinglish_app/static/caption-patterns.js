/* Fixed native AE recipes, separate from the accepted web caption renderers. */

(()=>{window.storylensCaptionPatterns=function(options){

 const {root,style,button,native,readScript,onStatus,showError}=options,row=document.createElement('div');row.className='row cp-settings';row.hidden=true;row.innerHTML='<label>Timing<select class="cp-timing"><option value="speech">Speech timing</option><option value="script">Script duration</option></select></label><label class="cp-seconds-label">Seconds<input class="cp-seconds" type="number" min="0.1" max="3600" step="0.1" placeholder="Timeline length"></label><small>Inter · AE patterns</small>';root.append(row);

 const timing=row.querySelector('.cp-timing'),seconds=row.querySelector('.cp-seconds'),secondsLabel=row.querySelector('.cp-seconds-label');timing.value='speech';let busy=false,pending=null,speechRequest=null,standard=true,preferred=null;

 try{const saved=JSON.parse(localStorage.getItem('storylens.caption1.ae')||'null');if(saved){preferred=saved.style==='caption_3'?'caption_4':['caption_2','caption_4','caption_6'].includes(saved.style)?saved.style:['caption_1','caption_1_ae'].includes(saved.style)?'caption_1':null;timing.value=saved.timing==='script'?'script':'speech';seconds.value=saved.seconds||'';}}catch(_){}

 function styleKey(){return style.value==='caption_3'?'caption_4':['caption_2','caption_4','caption_6'].includes(style.value)?style.value:'caption_1';}function styleName(){return {'caption_1':'Caption 1','caption_2':'Caption 2','caption_4':'Caption 4','caption_6':'Caption 6'}[styleKey()];}function selected(){return ['caption_1','caption_1_ae','caption_2','caption_3','caption_4','caption_6'].includes(style.value);}function sync(value=standard){standard=value;row.hidden=!standard||!selected();secondsLabel.hidden=timing.value!=='script';row.querySelector('small').textContent=styleKey()==='caption_6'?'Inter + Playfair \u00b7 AE patterns':styleKey()==='caption_4'?'Playfair \u00b7 AE patterns':'Inter \u00b7 AE patterns';}

 function save(){preferred=selected()?styleKey():null;localStorage.setItem('storylens.caption1.ae',JSON.stringify({timing:timing.value,seconds:seconds.value,style:preferred||style.value}));}function changed(){pending=null;speechRequest=null;sync();save();}

 timing.addEventListener('change',changed);seconds.addEventListener('input',changed);style.addEventListener('change',()=>{pending=null;speechRequest=null;sync();save();});sync();

 function nonce(){const b=new Uint8Array(16);crypto.getRandomValues(b);return Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');}

 function lock(value){busy=value;button.disabled=value;style.disabled=value;for(const n of row.querySelectorAll('input,select'))n.disabled=value;}

 async function apply(){lock(true);options.clearError?.();onStatus('Adding editable '+styleName()+' patterns…');try{const r=await native('caption3d',pending);if(!r.ok)throw Error(styleName()+' was not added.');onStatus((r.reused?'Already added: ':'Added ')+r.groups+' editable precomps · '+(pending.result_folder?'Speech timing':'Script timing')+(r.notice?' - '+r.notice:''));pending=null;return r;}catch(e){onStatus(styleName()+' is not confirmed. Retry uses the same request.');showError(e);}finally{lock(false);}}

 async function generateScript(){if(busy||options.isBusy?.())return;if(pending&&pending.script===readScript())return apply();pending=null;lock(true);try{const script=readScript();if(!script.trim())throw Error('Paste your script in Script & timeline first.');const context=await native('caption3d',{action:'patternContext'}),duration=seconds.value?Number(seconds.value):context.duration-context.time;pending={action:'patternInsert',style:styleKey(),script,duration,context,request_id:nonce()};return await apply();}catch(e){showError(e);}finally{lock(false);}}

 async function generateSpeech(){if(busy||options.isBusy?.())return;if(pending&&pending.script===readScript())return apply();lock(true);options.clearError?.();try{const script=readScript();if(!script.trim())throw Error('Paste your final spoken script in Script & timeline first.');if(!speechRequest||speechRequest.script!==script){const context=await native('caption3d',{action:'patternContext'}),timing_context=await native('caption3d',{action:'patternTimingContext'});if(context.project_id!==timing_context.project_id||context.comp_id!==String(timing_context.sequence_id))throw Error('The composition changed. Return to the intended caption timeline and retry.');speechRequest={action:'patternSpeechStart',style:styleKey(),script,context,timing_context,request_id:nonce()};}let state=await native('caption3d',speechRequest);while(['queued','running'].includes(state.status)){onStatus(state.stage||'Matching words to your speech…');await new Promise(resolve=>setTimeout(resolve,900));state=await native('caption3d',{action:'patternSpeechStatus',request_id:speechRequest.request_id});}if(state.status!=='complete'){speechRequest=null;const failure=state.failure||state.error;throw Object.assign(Error(failure?.message||'Speech timing stopped. Check the narration and retry.'),{code:failure?.code,details:failure?.details,captionMessage:failure?.message});}pending={action:'patternInsert',style:speechRequest.style,script:speechRequest.script,result_folder:state.folder,context:speechRequest.context,request_id:speechRequest.request_id};speechRequest=null;return await apply();}catch(e){onStatus(e.captionMessage||'Speech timing is not finished. Your script and saved progress are kept.');showError(e);}finally{lock(false);}}

 async function insertSpeech(context,folder,script){pending={action:'patternInsert',style:styleKey(),script,result_folder:folder,context,request_id:nonce()};return apply();}

 return {supports:id=>['caption_1','caption_1_ae','caption_2','caption_3','caption_4','caption_6'].includes(id),preferredStyle:()=>preferred,isSelected:selected,isRunning:()=>busy,usesScriptTiming:()=>timing.value==='script',sync,generateScript,generateSpeech,insertSpeech,hasPending:()=>!!pending&&pending.script===readScript(),retry:apply,option:(id='caption_1')=>new Option(id==='caption_6'?'Caption 6':['caption_3','caption_4'].includes(id)?'Caption 4':id==='caption_2'?'Caption 2':'Caption 1',id==='caption_3'?'caption_4':id)};

};window.storylensCaptionPatterns.supportedStyles=['caption_1','caption_2','caption_3','caption_4','caption_6'];})();

