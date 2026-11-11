const catalog=require('./catalog.json');
function prepare(input={}){
 const family=catalog.families.find(f=>f.id===input.family),v=family?.variants.find(v=>v.id===input.variant);
 if(!v)throw Error('Choose a 3D title preset.');
 const format=input.format||'vertical';if(!['vertical','horizontal'].includes(format))throw Error('Choose Vertical or Horizontal format.');
 const motions=['none','emerge','attach','fade','words','typewriter','slide','line-slide'];const motion=input.motion||(family.id==='3d1'?'line-slide':'none');if(!motions.includes(motion)||(family.id!=='3d1'&&motion==='line-slide')||(family.id==='3d1'&&motion!=='line-slide'))throw Error('Choose a supported animation.');
 const surface=input.surface||(v.layout==='corner'?'both':v.layout==='ground'?'ground':v.orientation&&v.orientation[1]>0?'left':'right');if(!['left','right','front','both','ground'].includes(surface)||(v.layout==='corner'&&!['left','right','both'].includes(surface)))throw Error('Choose a supported wall or surface.');
 const text=String(input.text===undefined?v.text:input.text).trim();if(text.length>240||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(text))throw Error('Use a short title.');
 const words=text.split(/\s+/).filter(w=>/[\p{L}\p{N}]/u.test(w)).map(w=>family.id==='3d1'?w:formatWord(w,family.id==='3d2'&&v.id==='yellow'));
 if(input.family==='3d1'){
  const rows=text.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);if(rows.length!==2)throw Error('Use two title lines.');
  return {family:family.id,variant:v.id,index:family.variants.indexOf(v),format,rows:rows.map(text=>({text})),text,motion,surface,depth:settings(input).depth,delay:settings(input).delay,perspective:{...poseDefaults(v.layout,surface),...settings(input).perspective},sound_mode:soundMode(input.sound_mode),sound_fx:input.sound_fx!==false};
 }
 if(words.length!==v.words)throw Error('Use '+v.words+' words for this preset.');
 let cursor=0;const rows=v.rows.map(row=>({...row,text:words.slice(cursor,cursor+=row.count).join(' ')}));
 return {family:family.id,variant:v.id,format,layout:v.layout,font:'Anton-Regular',colour:v.colour,colourValue:catalog.colours[v.colour],words:v.words,rows,text:words.join(' '),orientation:v.orientation,motion,surface,depth:settings(input).depth,delay:settings(input).delay,perspective:{...poseDefaults(v.layout,surface),...settings(input).perspective},duration:8,sound_mode:soundMode(input.sound_mode),sound_fx:input.sound_fx!==false};
}
function formatWord(text,upper=false){if(upper)return text.toUpperCase();const lower=text.toLowerCase();for(let i=0;i<lower.length;i++){const c=lower.charAt(i);if(c.toUpperCase()!==c.toLowerCase())return lower.slice(0,i)+c.toUpperCase()+lower.slice(i+1);}return lower;}
function poseDefaults(layout,surface){if(layout==='ground')return {pitch:-64,turn:12,roll:-8,seam:0};if(layout==='corner')return {pitch:18,turn:0,roll:0,seam:0};if(layout==='column')return {pitch:8,turn:-44,roll:8,seam:0};if(surface==='left')return {pitch:12,turn:44,roll:3,seam:0};if(surface==='front')return {pitch:12,turn:0,roll:0,seam:0};return {pitch:12,turn:-44,roll:-3,seam:0};}
function soundMode(mode){mode=mode||'pop_click';if(!['pop','click','pop_click','pop_click_whoosh'].includes(mode))throw Error('Choose a caption sound: Pop, Click, Pop + Click, or Pop + Click + Whoosh.');return mode;}
function settings(input={}){
 const delay=input.delay===undefined?.35:Number(input.delay);if(!Number.isFinite(delay)||delay<0||delay>4)throw Error('Use an animation delay between 0 and 4 seconds.');
 const perspective={};for(const [key,limit] of Object.entries({pitch:78,turn:75,roll:45,seam:80})){if(input.perspective?.[key]!==undefined){const v=Number(input.perspective[key]);if(!Number.isFinite(v)||Math.abs(v)>limit||(key==='seam'&&v<0))throw Error('Use a supported perspective angle or seam gap.');perspective[key]=v;}}
 const depth=input.depth===undefined?100:Number(input.depth);if(!Number.isFinite(depth)||depth<1||depth>400)throw Error('Use a depth between 1 and 400 pixels.');return {delay,perspective,depth};
}
function prepareUpdate(input={}){const motion=input.motion||'none';if(!['none','emerge','attach','fade','words','typewriter','slide'].includes(motion))throw Error('Choose a supported animation.');const surface=input.surface||'right';if(!['left','right','front','ground','both'].includes(surface))throw Error('Choose a supported direction.');return {motion,surface,...settings(input),sound_mode:soundMode(input.sound_mode),sound_fx:input.sound_fx!==false};}
module.exports={catalog,prepare,prepareUpdate};
