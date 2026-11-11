const fonts=require('./glyph-ink.json');
module.exports=function(word){
 const f=fonts[word.font]||fonts.bold,boxes=[];let pen=0,left=Infinity,right=-Infinity,top=Infinity,bottom=-Infinity;
 for(const char of word.text){const g=f.glyphs[char.codePointAt(0)];if(!g)return null;
  if(g[3]>g[1]&&g[4]>g[2]){const b=[pen+g[1],-g[4],pen+g[3],-g[2]];boxes.push(b);left=Math.min(left,b[0]);right=Math.max(right,b[2]);top=Math.min(top,b[1]);bottom=Math.max(bottom,b[3]);}
  pen+=g[0]+word.tracking*f.units/1000;
 }
 return boxes.map(b=>[(b[0]-left)/(right-left),(b[1]-top)/(bottom-top),(b[2]-left)/(right-left),(b[3]-top)/(bottom-top)]);
};
