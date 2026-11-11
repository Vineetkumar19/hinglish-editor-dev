(()=>{'use strict';
window.storylensAnimationPresets=({native,isBusy,showError,clearError})=>{
 const $=id=>document.getElementById(id);let tree=null,current='root',section='cc',running=false,reading=false,visible=false,signature='';
 const status=text=>$('animationPresetStatus').textContent=text;
 const button=(text,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=fn;return b;};
 function locate(node,id,trail=[]){if(node.id===id)return {node,trail:[...trail,node]};for(const f of node.folders){const found=locate(f,id,[...trail,node]);if(found)return found;}return null;}
 async function work(fn){if(running||reading||isBusy())return;running=true;clearError();render();try{await fn();}catch(e){status('Preset needs attention. See the message below.');showError(e);}finally{running=false;render();}}
 function filtered(node){const folders=node.folders.map(filtered).filter(n=>n.folders.length||n.presets.length||n.other.length);return {...node,folders,presets:node.presets.filter(p=>(p.category||'effects')===section),other:node.other.filter(p=>(p.category||'effects')===section)};}
 function count(node){return node.presets.length+node.folders.reduce((sum,f)=>sum+count(f),0);}
 function render(){if(!tree)return;const selected=filtered(tree),found=locate(selected,current)||{node:selected,trail:[selected]};current=found.node.id;
  for(const [id,key] of [['animationPresetCC','cc'],['animationPresetEffects','effects']]){const b=$(id);b.setAttribute('aria-pressed',String(section===key));b.disabled=running;}
  $('animationPresetCount').textContent=count(selected)+' '+(section==='cc'?'CC':'Effects')+' presets';
  $('animationPresetBreadcrumb').replaceChildren(...found.trail.map(f=>button(f.name,()=>{current=f.id;render();})));
  const nodes=found.node.folders.map(f=>{const b=button('Folder · '+f.name,()=>{current=f.id;render();});b.title=f.name;b.disabled=running;return b;});
  const query=$('animationPresetSearch').value.trim().toLowerCase();
  function matches(node,trail){for(const p of node.presets)if(!query||p.name.toLowerCase().includes(query)){const b=button(p.name,()=>work(async()=>{status('Applying '+p.name+'…');const r=await native('animationPresets',{action:'apply',id:p.id,signature:p.signature,target:$('animationPresetTarget').value});status(p.name+' applied to '+(r.adjustment?'a new adjustment layer':r.layers+' selected layer(s)')+' at '+Number(r.time).toFixed(2)+'s.');}));b.title=trail+' / '+p.name;b.disabled=running;nodes.push(b);}if(query)for(const f of node.folders)matches(f,trail+' / '+f.name);}
  matches(found.node,found.node.name);$('animationPresetFiles').replaceChildren(...nodes);
  $('animationPresetOther').textContent=found.node.other.length?'Supporting files: '+found.node.other.map(f=>f.name).join(', ')+'. Only .ffx animation presets apply to layers. Extract ZIP packs into this folder to use their presets.':'';
  $('animationPresetCreate').disabled=running;$('animationPresetTarget').disabled=running;
 }
 async function refresh(){if(!visible||running||reading||isBusy())return;reading=true;try{const r=await native('animationPresets',{action:'catalog'}),next=JSON.stringify(r.tree);if(next!==signature){tree=r.tree;signature=next;render();status(r.total+' presets · folders update automatically. Select a layer, then click a preset.');}}catch(e){showError(e);}finally{reading=false;}}
 $('animationPresetRefresh').onclick=refresh;$('animationPresetSearch').oninput=render;
 for(const [id,key] of [['animationPresetCC','cc'],['animationPresetEffects','effects']])$(id).onclick=()=>{if(running)return;section=key;current='root';$('animationPresetSearch').value='';render();status('Choose a '+(section==='cc'?'CC':'Effects')+' folder or preset.');};
 $('animationPresetCreate').onclick=()=>work(async()=>{const r=await native('animationPresets',{action:'adjustment'});status('Adjustment layer created at '+Number(r.time).toFixed(2)+'s. Click a preset to apply it.');$('animationPresetTarget').value='selected';});
 setInterval(refresh,5000);window.addEventListener('focus',refresh);
 return {isRunning:()=>running,open(){visible=true;refresh();},hide(){visible=false;}};
};})();
