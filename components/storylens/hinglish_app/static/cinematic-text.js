/* Cached galleries browse on disk. Only an explicit design choice inserts a native title. */
(()=>{window.storylensCinematicText=function({native,isBusy,showError,clearError}){
 const $=id=>document.getElementById(id);let running=false,visible=false,timer=null,catalog=[],pack=null,groupId=null,loaded=null,generation=0;
 const session=Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);let serial=0;const pendingChoices=new Map();
 const message=text=>$('effectsStatus').textContent=text;
 function fail(e){showError(e);message(window.storylensError(e));const details=document.getElementById('storylensErrorDetails');if(details)$('effectsStatus').append(details);}
 function button(text,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=fn;return b;}
 function blocked(){if(running||isBusy()){message('Wait for the current Storylens task to finish, then choose this title.');return true;}return false;}
 async function work(fn){if(blocked())return;running=true;clearError();try{return await fn();}catch(e){fail(e);}finally{running=false;}}
 function controls(disabled){for(const el of $('effectsScenes').children||[])if(el._add)el._add.disabled=disabled;}
 function packs(){const nodes=catalog.map(p=>{const b=button(p.name,()=>openGroup(p));b.title=p.expected?p.expected+' scenes':'Discover scenes';b.setAttribute('aria-pressed',String(groupId===p.id));return b;});$('effectsPacks').replaceChildren(...nodes);}
 function openGroup(p){if(blocked())return;groupId=p.id;$('effectsProjects').replaceChildren();if((p.projects||[]).length<2)return openPack(p);generation++;pack=null;loaded=null;packs();$('effectsScenes').replaceChildren();$('effectsProjects').append(...p.projects.map(project=>button(project.name,()=>openPack(project))));message('Choose a project in '+p.name+'.');}
 async function refresh(){if(running)return;try{const r=await native('catalog'),next=r.packs||[];if(JSON.stringify(next)!==JSON.stringify(catalog)){catalog=next;packs();if(pack&&!next.flatMap(p=>p.projects||[p]).some(p=>p.id===pack.id&&p.signature===pack.signature)){generation++;loaded=null;pack=null;$('effectsProjects').replaceChildren();$('effectsScenes').replaceChildren();message('The library changed. Select the updated pack.');}}if(!catalog.length)message('Add an extracted After Effects project to Text templates, then refresh.');}catch(e){fail(e);}}
 const base=p=>({pack_id:p.id,signature:p.signature});
 function mount(p,scene){const card=document.createElement('article');card.className='effect-scene';let receipt=null;const choiceKey=p.id+'|'+p.signature+'|'+scene.id;let pending=pendingChoices.get(choiceKey)||null;
  const missing=(scene.fonts||[]).filter(f=>f.missing).map(f=>f.name),check={checked:false};
  const add=button(scene.name,()=>work(async()=>{if(!loaded||pack.id!==p.id)throw Error('Open this pack again before choosing a scene.');controls(true);message('Adding '+scene.name+'…');try{
   if(!pending){const destination=await native('destination');pending={...destination,request_id:session+'-'+(++serial)};pendingChoices.set(choiceKey,pending);}
   const answer=await native('insertChoice',{...base(p),...pending,scene_id:scene.id,background_off:check.checked});receipt={...answer,project_id:answer.project_id||pending.project_id};pending=null;pendingChoices.delete(choiceKey);message(scene.name+' added at '+Number(answer.start||0).toFixed(2)+'s'+(answer.background_off?' · Background off':'')+'.');
  }finally{controls(false);}}));add.className='effect-preview';add.title='Add only '+scene.name+' at the current playhead';add.disabled=false;card._add=add;card._missing=false;
  const image=document.createElement('img');image.alt='';image.hidden=true;const name=document.createElement('span');name.textContent=scene.name;add.replaceChildren(image,name);card.append(add);
  const warning=document.createElement('p');warning.className='effect-font-warning';warning.textContent='';warning.hidden=true;card.append(warning);card._warning=warning;
  const label=button('Remove BG',()=>work(async()=>{const desired=!check.checked;if(receipt)await native('background',{...base(p),scene_id:scene.id,project_id:receipt.project_id,receipt,background_off:desired});check.checked=desired;label.textContent=desired?'Restore BG':'Remove BG';label.setAttribute('aria-pressed',String(desired));message(receipt?scene.name+' · Background '+(desired?'removed':'restored')+'.':scene.name+' will be added '+(desired?'without its background.':'with its background.'));}));label.className='effect-background';label.disabled=!scene.backgrounds;label.setAttribute('aria-pressed','false');
  const preview=button('Preview',()=>work(async()=>{message('Refreshing '+scene.name+' preview…');await gallery(p,'refreshPreview',scene.id,generation);}));preview.className='effect-preview-retry';const actions=document.createElement('div');actions.className='effect-scene-actions';actions.append(label,preview);card.append(actions);card._preview=preview;card._image=image;card._scene=scene;return card;
 }
 function update(p,r){loaded=r;const existing=new Map(Array.from($('effectsScenes').children||[]).map(c=>[String(c._scene.id),c]));const cards=(r.scenes||[]).map(scene=>{const c=existing.get(String(scene.id))||mount(p,scene);const missing=(scene.fonts||[]).filter(f=>f.missing).map(f=>f.name);c._missing=false;c._add.disabled=false;c._warning.hidden=true;c._warning.textContent='';if(scene.image){c._image.src=scene.image;c._image.hidden=false;}c._preview.title=scene.preview_status==='failed'?(scene.preview_error||'Retry preview'):'Refresh preview';if(scene.preview_details)c._preview.title+=' · '+scene.preview_details;return c;});$('effectsScenes').replaceChildren(...cards);
  if(r.status==='building')message('Preparing previews · '+Number(r.completed||0)+'/'+(cards.length||'…')+'. Please wait.');
  else if(r.status==='failed')throw Object.assign(Error(r.error||'Text previews could not finish. Reopen this pack to retry.'),{code:'cinematic_text',details:r.details});
  else message(cards.length+' scenes. Choose one to add only that design.'+(r.status==='partial'?' Some previews need retrying.':''));
 }
 async function gallery(p,action,sceneId,gen){let r=await native(action,{...base(p),...(sceneId?{scene_id:sceneId}:{})});while(gen===generation){update(p,r);if(r.status!=='building')return;await new Promise(resolve=>setTimeout(resolve,750));r=await native('galleryStatus',base(p));}}
 async function openPack(p){return work(async()=>{generation++;const gen=generation;pack=p;loaded=null;packs();$('effectsScenes').replaceChildren();message('Preparing '+p.name+' previews…');await gallery(p,'gallery',null,gen);});}
 $('effectsCinematic').onclick=()=>{$('effectsLibrary').hidden=!$('effectsLibrary').hidden;};
 $('effectsRefresh').onclick=()=>refresh();
 for(const [id,off] of [['effectsRemoveBackground',true],['effectsRestoreBackground',false]])$(id).onclick=()=>work(async()=>{message(off?'Removing selected title background…':'Restoring selected title background…');const r=await native('selectedBackground',{background_off:off});message((off?'Background removed':'Background restored')+' · '+r.changed+' layers.');});
 window.addEventListener('focus',()=>{if(visible)refresh();});
 return {isRunning:()=>running,async select(){visible=true;$('effectsLibrary').hidden=false;await refresh();if(!timer)timer=setInterval(()=>{if(visible)refresh();},5000);},hide(){visible=false;},refresh};
};})();
