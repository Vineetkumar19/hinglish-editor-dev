// Approved patterns are reusable slots, independent of the example's language.
globalThis.storylensTemplatePattern=(words,recipes)=>{
  if(!words.length||!recipes.length)return null;
  const active=typeof cues!=='undefined'&&typeof video!=='undefined'?cues.find(q=>q.start<=video.currentTime&&video.currentTime<q.end):null;
  const original=active?.template_source||'',target=original?original.split(/\s+/):words;
  const token=w=>String(w).toLowerCase().replace(/[^\p{L}\p{N}]/gu,''),numeric=target.some(w=>/^\d+$/.test(token(w)));
  let candidates=recipes.filter(r=>r.text),compatible=candidates.filter(r=>r.text.split(/\s+/).some(w=>/^\d+$/.test(token(w)))===numeric);
  if(compatible.length)candidates=compatible;
  const source=candidates.find(r=>original&&r.text.split(/\s+/).map(token).join(' ')===target.map(token).join(' '))||(active?.template_slot>=0?candidates[active.template_slot%candidates.length]:candidates.reduce((a,b)=>Math.abs(b.text.split(/\s+/).length-target.length)<Math.abs(a.text.split(/\s+/).length-target.length)?b:a));
  const old=source.text.split(/\s+/),n=words.length,m=old.length,mapping=words.map((_,i)=>Math.min(m-1,Math.floor((i+.5)*m/n))),nearest=j=>mapping.reduce((best,v,i)=>Math.abs(v-j)<Math.abs(mapping[best]-j)?i:best,0);
  const main=source.rows?.find(r=>r.role==='main'||r.blue);
  if(main&&!mapping.some(j=>main.words.includes(j)))mapping[nearest(main.words[0])]=main.words[0];
  const out=JSON.parse(JSON.stringify(source));
  for(const key of ['start','end','starts','sample_beats','display','hero_frame','replace_words'])delete out[key];
  Object.assign(out,{text:words.join(' '),template_pattern:source.text,adapted:true});
  if(source.rows)out.rows=source.rows.flatMap(row=>{
    const ids=mapping.flatMap((j,i)=>row.words.includes(j)?[i]:[]);if(!ids.length)return [];
    const r={...JSON.parse(JSON.stringify(row)),words:ids};delete r.frame;
    if(row.green)r.green=ids.filter(i=>row.green.includes(mapping[i]));
    for(const field of ['sizes','tones'])if(row[field])r[field]=Array.isArray(row[field])?ids.map(i=>row[field][row.words.indexOf(mapping[i])]):Object.fromEntries(ids.filter(i=>String(mapping[i]) in row[field]).map(i=>[String(i),row[field][String(mapping[i])]]));
    return [r];
  });
  if(source.runs)out.runs=mapping.map(j=>({...source.runs[j],source_word:old[j]}));
  for(const field of ['hero','support_focus'])if(Number.isInteger(source[field])&&source[field]>=0)out[field]=nearest(source[field]);
  if(Array.isArray(source.motion))out.motion=mapping.map((j,i)=>({...source.motion[j],start_word:nearest(source.motion[j].start_word??mapping[i])}));
  for(const d of out.decorations||[])if('trigger' in d)d.trigger=nearest(d.trigger);
  return out;
};

globalThis.storylensTemplateRebound=words=>{const q=typeof cues!=='undefined'&&typeof video!=='undefined'?cues.find(q=>q.start<=video.currentTime&&video.currentTime<q.end):null,clean=t=>t.toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');return Boolean(q?.template_source&&q.template_source.split(/\s+/).map(clean).join(' ')!==words.map(clean).join(' '))};
