/* Categorized tools use the existing guarded native request queue. */
(()=>{window.storylensEffectsToolkit=function({settings,gallery,native,work,message,blocked}){
 let tools=[],categories=[],category='',query='',view='category',cards=[],report='',searchInput,viewSelect;
 const key='storylens.effects-toolkit.v1';let saved={favourites:[],recent:[],settings:{},previews:{}};
 try{const data=JSON.parse(localStorage.getItem(key)||'null');if(data&&Array.isArray(data.favourites)&&Array.isArray(data.recent)&&data.settings&&data.previews)saved=data;}catch(ignore){}
 const persist=()=>{try{localStorage.setItem(key,JSON.stringify(saved));return true;}catch(ignore){return false;}};
 const node=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e;};
 const button=(label,fn)=>{const b=node('button','',label);b.type='button';b.onclick=fn;return b;};
 function values(card){const out={};for(const d of card._tool.settings){const raw=card._inputs[d.id].value,value=d.type==='number'?Number(raw):raw;if(d.type==='number'&&(!raw.trim()||!Number.isFinite(value)||value<d.min||value>d.max))throw Object.assign(Error(d.label+' must be between '+d.min+' and '+d.max+'.'),{code:'effects_toolkit'});out[d.id]=value;}return out;}
 async function apply(card){if(blocked())return;if(card._tool.ui){view=card._tool.ui==='favourites'?'favourites':'all';query='';if(searchInput){searchInput.value='';searchInput.focus?.();}viewSelect.value=view;render();return;}
  return work(async()=>{const options=values(card);saved.settings[card._tool.id]=options;persist();for(const c of cards)c._add.disabled=true;
   try{message('Applying '+card._tool.name+'…');const r=await native('toolkitApply',{id:card._tool.id,settings:options});if(r.error)throw Object.assign(Error(r.error),{code:r.code||'effects_toolkit',details:r.details});report=r.report||'';
    if(r.changed>0)saved.recent=[card._tool.id,...saved.recent.filter(id=>id!==card._tool.id)].slice(0,20);
    if(r.preview_frames){saved.previews[r.preview_tool]=r.preview_frames;render();}const durable=persist();showReport();message((r.message||card._tool.name+' applied.')+(!durable?' Panel storage is full; settings remain for this session and captured PNGs remain in the native cache.':''));
   }finally{for(const c of cards)c._add.disabled=false;}
  });
 }
 function showReport(){gallery.querySelector?.('.toolkit-report')?.remove();if(report){const details=node('details','toolkit-report'),summary=node('summary','','Result details'),pre=node('pre','',report);details.append(summary,pre);gallery.append(details);}}
 function render(){
  const selected=tools.filter(t=>{const haystack=(t.name+' '+t.help+' '+(categories.find(c=>c.id===t.category)?.name||'')+' '+t.id).toLowerCase();return (!query||query.split(/\s+/).every(word=>haystack.includes(word)))&&(view==='favourites'?saved.favourites.includes(t.id):view==='recent'?saved.recent.includes(t.id):query||view==='all'||t.category===category);});if(view==='recent')selected.sort((a,b)=>saved.recent.indexOf(a.id)-saved.recent.indexOf(b.id));
  cards=selected.map(t=>{
   const card=node('article','effect-scene toolkit-card'),applyButton=button(t.name,()=>apply(card));applyButton.className='toolkit-apply';applyButton.draggable=!t.ui;applyButton.title=t.help;applyButton.ondragstart=e=>{if(blocked()){e.preventDefault();return;}e.dataTransfer.setData('text/plain','storylens-tool:'+t.id);};
   const frames=saved.previews[t.id];if(Array.isArray(frames)&&frames.length===8&&frames.every(f=>typeof f==='string'&&f.startsWith('data:image/png;base64,'))){const img=node('img','toolkit-preview');img.alt=t.name+' — captured native frames';img.src=frames[0];let timer=null,index=0;img.onmouseenter=()=>{if(!timer)timer=setInterval(()=>{index=(index+1)%frames.length;img.src=frames[index];},140);};img.onmouseleave=()=>{clearInterval(timer);timer=null;img.src=frames[0];};card.append(img);card._stop=()=>{clearInterval(timer);timer=null;};}
   const star=button(saved.favourites.includes(t.id)?'★ Saved':'☆ Favourite',()=>{saved.favourites=saved.favourites.includes(t.id)?saved.favourites.filter(id=>id!==t.id):[...saved.favourites,t.id];persist();star.textContent=saved.favourites.includes(t.id)?'★ Saved':'☆ Favourite';if(view==='favourites')render();});star.className='toolkit-star';star.setAttribute('aria-label','Favourite '+t.name);
   const help=node('p','toolkit-help',t.help),details=node('details','toolkit-adjustments'),summary=node('summary','','Adjustments'),fields=node('div','toolkit-fields'),inputs={};
   for(const d of t.settings){const previewChoice=t.id==='preview-cache'&&d.id==='tool',label=node('label','',previewChoice?'Preview for':d.label),input=node(d.type==='select'||previewChoice?'select':d.multiline?'textarea':'input');input.setAttribute('aria-label',t.name+' · '+d.label);
    if(d.type==='select'||previewChoice){for(const option of previewChoice?tools.filter(x=>!x.ui).map(x=>({id:x.id,name:x.name})):d.options.map(x=>({id:x,name:x}))){const opt=node('option','',option.name);opt.value=option.id;input.append(opt);}}
    else{input.type=d.type;input.min=d.min;input.max=d.max;input.step=d.step;if(d.maxLength)input.maxLength=d.maxLength;}input.value=String(saved.settings[t.id]?.[d.id]??d.value);inputs[d.id]=input;input.onchange=()=>{try{saved.settings[t.id]=values(card);persist();}catch(ignore){}};label.append(input);fields.append(label);
   }
   details.append(summary,fields);card.append(applyButton,star,help);if(t.settings.length)card.append(details);Object.assign(card,{_add:applyButton,_star:star,_tool:t,_inputs:inputs});return card;
  });for(const old of gallery.children||[])old._stop?.();gallery.replaceChildren(...cards);showReport();message(cards.length+' tools. Select layers or keyframes, then click a tool. Adjustments stay editable in AE.');
 }
 function controls(){
  const row=node('div','toolkit-toolbar'),label=node('label','','Category '),select=node('select');for(const c of categories){const option=node('option','',c.name);option.value=c.id;select.append(option);}select.value=category;select.onchange=()=>{if(blocked())return;category=select.value;query='';searchInput.value='';view='category';viewSelect.value=view;render();};label.append(select);
  const search=node('input');searchInput=search;search.type='search';search.placeholder='Search all tools and categories';search.setAttribute('aria-label','Find an Effects tool');search.oninput=()=>{query=search.value.trim().toLowerCase();render();};
  viewSelect=node('select');viewSelect.setAttribute('aria-label','Tool library filter');for(const [id,name] of [['category','This category'],['all','All tools'],['favourites','Favourites'],['recent','Recent']]){const opt=node('option','',name);opt.value=id;viewSelect.append(opt);}viewSelect.value=view;viewSelect.onchange=()=>{view=viewSelect.value;render();};row.append(label,search,viewSelect);
  const drop=node('div','toolkit-drop','Select layers or keyframes, then click a tool — or drop a tool here to apply to the selected items.');drop.ondragover=e=>{if(!blocked())e.preventDefault();};drop.ondrop=async e=>{e.preventDefault();if(blocked())return;const value=e.dataTransfer.getData('text/plain'),card=cards.find(c=>value==='storylens-tool:'+c._tool.id);if(card)await apply(card);};settings.replaceChildren(row,drop);
 }
 return {async open(){const r=await native('toolkitCatalog');tools=r.tools||[];categories=r.categories||[];if(!categories.some(c=>c.id===category))category=categories[0]?.id||'';controls();render();}};
};})();
