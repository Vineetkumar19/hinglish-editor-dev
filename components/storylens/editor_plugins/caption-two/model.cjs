const profile=require('./profile.json'),base=require('../caption-patterns/model.cjs'),{rowWidth}=require('../caption-patterns/widths.cjs');
const stops=new Set('a an the and or of to in at on for is it that with we you your our can but as if so be have has been are this these those i its my they them hai hain ka ki ke ko se aur hum tum apne ke liye ek bhi mein toh to tab ab na hi jo thi tha ho'.split(' '));
const key=t=>t.toLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
function take(words,start,max,letters){let n=0,len=0;while(start+n<words.length&&n<max){const size=words[start+n].source.length;if(n&&len+size>letters)break;len+=size;n++;if(/[.!?]$/.test(words[start+n-1].source))break;}return n;}
function recipeRows(words,r){
 if(r.white||words.every(w=>stops.has(key(w.source))))return [{id:'white',words:words.map((_,i)=>i)}];
 if(words.length===1)return [{id:'main',words:[0]}];
 const rows=[],n=words.length;let top=Math.min(take(words,0,r.id==='understand'||r.id==='content'?1:r.two_line?4:2,r.two_line?18:11),n-1),main=Math.min(r.main_words,n-top);
 // A main phrase must contain a content word. Move the boundary, keeping order.
 if(words.slice(top,top+main).every(w=>stops.has(key(w.source)))){const next=words.findIndex((w,i)=>i>=top&&!stops.has(key(w.source)));if(next>=0)top=next;else{top=0;}main=Math.min(r.main_words,n-top);}
 if(main===2&&(words[top].source.length+words[top+1].source.length>17||stops.has(key(words[top+1].source))))main=1;
 if(top)rows.push({id:'top_left',words:Array.from({length:top},(_,i)=>i)});
 rows.push({id:'main',words:Array.from({length:main},(_,i)=>top+i)});let cursor=top+main;
 if(r.split&&n-cursor>2){let size=take(words,cursor,2,11);rows.push({id:'top_right',words:Array.from({length:size},(_,i)=>cursor+i)});cursor+=size;}
 if(cursor<n)rows.push({id:'bottom',words:Array.from({length:n-cursor},(_,i)=>cursor+i)});
 return rows;
}
function decorate(words,rows,r,offset){let hero=0;return words.map((w,i)=>{
 const row=rows.find(row=>row.words.includes(i)).id,main=row==='main',text=w.source.toLowerCase();
 const display=main&&hero++===0?text.replace(/\p{L}/u,c=>c.toUpperCase()):text;
 const size=main?r.main_size:row==='top_left'||row==='top_right'?(r.header_size||40):row==='bottom'?(r.footer_size||40):40;
 return {...w,text:display,index:offset+i,slot:i,row,role:main?'main':'support',font:row==='bottom'&&r.footer_font==='regular'?'regular':'bold',size,colour:main||row==='bottom'&&['understand','camera'].includes(r.id)&&i===words.length-1&&!stops.has(key(w.source))?'lime':'white',fill_rgb:(main||row==='bottom'&&['understand','camera'].includes(r.id)&&i===words.length-1&&!stops.has(key(w.source)))?(r.lime_rgb||[224,253,85]):[255,255,255],appearance:profile.appearance,tracking:r.split&&row!=='main'?-75:-60,gradient:false,motion:{x:0,y:0,rotation:0,seconds:.23,fade_seconds:.16}};
 });}
function prepare(input={}){
 const original=base.prepare(input),words=original.pages.flatMap(p=>p.words),pages=[];let cursor=0;
 while(cursor<words.length){const slot=((input.template_slot||0)+pages.length)%profile.recipes.length,r=profile.recipes[slot];
  let n=take(words,cursor,r.white?3:r.two_line?6:r.split||r.id==='record'?7:6,55),rows,group;
  while(n){const raw=words.slice(cursor,cursor+n);rows=recipeRows(raw,r);group=decorate(raw,rows,r,cursor);
   const valid=rows.every(row=>row.words.length<=(row.id==='bottom'?3:row.id==='white'?3:row.id==='top_left'&&r.two_line?4:row.id==='main'?2:2)&&(row.words.length===1||row.words.reduce((sum,i)=>sum+group[i].source.length,0)<=(row.id==='main'?17:row.id==='top_left'&&r.two_line?18:20)));
   const widthOK=rows.every(row=>row.words.length===1||rowWidth(row.words.map(i=>({...group[i],font:group[i].font==='regular'?'support':group[i].font})),profile)<=680);if(valid&&widthOK||n===1)break;n--;
  }
  const start=group[0].start,end=Math.min(original.duration,group.at(-1).end+.12);
  const delay=(r.main_delay||0),zoom=[[0,r.camera[0][1],0,0],...r.camera.map(k=>[k[0]+delay,k[1],0,0])];
  pages.push({index:pages.length,pattern_id:r.id,template_slot:slot,source_start:cursor,kind:r.white?'white':r.split?'split':r.two_line?'two_line':'stack',words:group,rows,start,end,word_gap_em:profile.word_gap_em,safe_width_fraction:profile.safe_width_fraction,camera:r.camera,camera_path:zoom,optics:r.optics||{},ink_gap:profile.ink_gap});cursor+=n;
 }
 for(let i=0;i<pages.length-1;i++)pages[i].end=Math.min(pages[i].end,pages[i+1].start);
 if(pages.some(p=>p.end<=p.start))throw Error('Caption 2 needs distinct spoken phrase timings. Review this phrase before adding it.');
 for(const page of pages)for(const word of page.words)word.ink_boxes=require('./ink.cjs')(word);
 return {...original,style:profile.id,reference_sha256:profile.reference_sha256,pages};
}
module.exports={prepare,profile};
