const metrics=require('./glyph-metrics.json');
function width(text,role,size,tracking=0){const f=metrics[role];let pen=0,left=Infinity,right=-Infinity;for(const char of text){const g=f.glyphs[char.codePointAt(0)]||[f.units,0,0,f.units,f.units];left=Math.min(left,pen+g[1]);right=Math.max(right,pen+g[3]);pen+=g[0]+tracking*f.units/1000;}return Math.max(1,(right-left)*size/f.units);}
function rowWidth(words,profile){return words.reduce((n,w,i)=>n+width(w.text,w.font,w.size,w.tracking)+(i?Math.min(words[i-1].size,w.size)*profile.word_gap_em:0),0);}
module.exports={width,rowWidth};
