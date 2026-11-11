const profile=require('./profile.json'),base=require('../caption-patterns/model.cjs'),{rowWidth}=require('./metrics.cjs');
const key=s=>String(s).toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
function adapt(group,recipe,cursor){
 const source=recipe.text.split(/\s+/),exact=group.length===source.length&&group.every((w,i)=>key(w.source)===key(source[i])),mapping=group.map((_,i)=>Math.min(source.length-1,Math.floor((i+.5)*source.length/group.length)));
 const rows=recipe.rows.flatMap(row=>{const words=mapping.flatMap((source,i)=>row.words.includes(source)?[i]:[]);return words.length?[{...row,words}]:[];});
 // Equal-onset words in a replacement sequence form ONE state, never several
 // coincident layers whose earlier states would immediately disappear.
 if(recipe.replace_words)for(let i=1;i<rows.length;){const a=rows[i-1],b=rows[i];if(group[a.words[0]].start===group[b.words[0]].start){a.words.push(...b.words);rows.splice(i,1);}else i++;}
 const words=group.map((w,i)=>{const row=rows.find(r=>r.words.includes(i));return {...w,index:cursor+i,slot:i,text:row.case==='upper'?w.source.toUpperCase():exact?source[i]:w.source.toLowerCase(),row:row.id,role:row.role,font:row.font,size:row.size,tracking:profile.tracking[row.font],colour:row.fill_rgb[0]===255&&row.fill_rgb[1]===255?'white':row.fill_rgb[1]>row.fill_rgb[0]?'green':'red',fill_rgb:row.fill_rgb,gradient:false,motion:{x:0,y:recipe.motion==='cut'?0:profile.motion.travel,rotation:0,seconds:(row.rise_frames||6)/30,fade_seconds:(row.fade_frames||3)/30},source_onset:row.source_onset,source_frame:recipe.source_start};});
 return {words,rows};
}
function prepare(input={}){
 const intake=base.prepareWords(input),{words:all,...original}=intake,pages=[];let cursor=0;
 const first=Number.isInteger(input.template_slot)&&input.template_slot>=0?input.template_slot:0;
 while(cursor<all.length){
  const slot=(first+pages.length)%profile.recipes.length,r=profile.recipes[slot];let minimum=1;while(cursor+minimum<all.length&&all[cursor+minimum].start===all[cursor].start)minimum++;
  if(minimum>12)throw Error('This phrase has too many words sharing one audio time. Review that speech alignment before adding Caption 6.');
  let n=Math.max(minimum,Math.min(r.text.split(/\s+/).length,12,all.length-cursor));
  for(let i=minimum-1;i<n;i++)if(/[.!?]$/.test(all[cursor+i].source)||i+1<n&&all[cursor+i+1].start-all[cursor+i].end>.55){n=i+1;break;}
  let group;while(n){while(n>minimum&&cursor+n<all.length&&all[cursor+n-1].start===all[cursor+n].start)n--;group=adapt(all.slice(cursor,cursor+n),r,cursor);if(n<=minimum||group.rows.every(row=>row.words.length===1||rowWidth(row.words.map(i=>group.words[i]))<=490))break;n--;}
  const start=group.words[0].start,end=Math.min(original.duration,group.words.at(-1).end+.12);
  for(const [i,row] of group.rows.entries())for(const id of row.words){group.words[id].visible_end=r.replace_words&&group.rows[i+1]?group.words[group.rows[i+1].words[0]].start:end;group.words[id].reveal_start=group.words[id].start;}
  pages.push({index:pages.length,pattern_id:r.id,template_slot:slot,template_source:r.text,reference_sha256:profile.reference_sha256,source_start:cursor,source_frame:r.source_start,source_end_frame:r.source_end,kind:r.replace_words?'replacement_states':'reference_rows',replace_words:r.replace_words,motion_kind:r.motion,anchor_y:profile.anchor_y,safe_width_fraction:profile.safe_width_fraction,word_gap_em:profile.word_gap_em,ink_gap:profile.ink_gap,words:group.words,rows:group.rows,decorations:r.decorations,start,end});cursor+=n;
 }
 for(let i=0;i<pages.length;i++){const p=pages[i];if(pages[i+1])p.end=Math.min(p.end,pages[i+1].start);if(p.end<=p.start)throw Error('Caption 6 needs distinct phrase timing. Review this script against the audio.');for(const w of p.words)w.visible_end=Math.min(w.visible_end,p.end);}
 return {...original,style:profile.id,reference_sha256:profile.reference_sha256,pages};
}
module.exports={prepare,profile};
