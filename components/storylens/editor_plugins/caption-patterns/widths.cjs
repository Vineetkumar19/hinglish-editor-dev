// Measured glyph widths distinguish wide/narrow letters; AE rechecks actual ink.
const metrics=require('./inter-ink-metrics.json');
function wordWidth(text,role,size,tracking=0){
 const font=metrics.fonts[role],units=font.units_per_em;let pen=0,left=Infinity,right=-Infinity;
 for(const char of String(text)){
  const code=char.codePointAt(0),glyph=font.glyphs[code];
  if(!glyph){const advance=/\p{M}/u.test(char)?0:units;left=Math.min(left,pen);right=Math.max(right,pen+advance);pen+=advance+tracking*units/1000;continue;}
  left=Math.min(left,pen+glyph[1]);right=Math.max(right,pen+glyph[2]);pen+=glyph[0]+tracking*units/1000;
 }
 return Math.max(1,Number.isFinite(right-left)?(right-left)*size/units:0);
}
function rowWidth(words,profile){return words.reduce((n,w,i)=>n+wordWidth(w.text,w.font,w.size,profile.tracking[w.font])+(i?Math.min(words[i-1].size,w.size)*profile.word_gap_em:0),0);}
module.exports={wordWidth,rowWidth};
