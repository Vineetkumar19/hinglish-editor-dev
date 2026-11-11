/* Caption 2 measured ink, split headers and fixed complete-row slots. ES3. */
(function(g){
 function layout(page,metrics,width,height){
  var factor=width/720,gap=page.ink_gap*factor,rows=[],lookup={},i,j;
  function space(a,b){return Math.min(page.words[a].size,page.words[b].size)*factor*page.word_gap_em;}
  for(i=0;i<page.rows.length;i++){var src=page.rows[i],row={id:src.id,words:src.words,x:0,y:0,width:0,height:0,inkTop:1e20,inkBottom:-1e20};for(j=0;j<src.words.length;j++){var id=src.words[j];row.width+=metrics[id].width+(j?space(src.words[j-1],id):0);row.inkTop=Math.min(row.inkTop,metrics[id].top);row.inkBottom=Math.max(row.inkBottom,metrics[id].top+metrics[id].height);row.height=row.inkBottom-row.inkTop;}rows.push(row);lookup[row.id]=row;}
  var main=lookup.main||lookup.white,head=lookup.top_left,rightHead=lookup.top_right,bottom=lookup.bottom;
  var optics=page.optics||{};if(head){var h=optics.top_left||{x:.1,y:-.4};head.x=main.width*h.x;head.y=main.height*h.y;}
  if(rightHead){var rh=optics.top_right||{x:.56,y:-.15};rightHead.x=Math.max(main.width*rh.x,head.x+head.width+space(head.words[head.words.length-1],rightHead.words[0]));rightHead.y=main.height*rh.y;}
  if(bottom){var bt=optics.bottom||{right:1,y:1.02};bottom.x=main.width*bt.right-bottom.width;bottom.y=main.height*bt.y;}
  // Reference optical offsets are proposals. Check actual new-word glyph ink
  // before keeping them; an ascender in another word can occupy that space.
  function boxes(row){var result=[],pen=row.x;for(var k=0;k<row.words.length;k++){var id=row.words[k],m=metrics[id],ink=page.words[id].ink_boxes||[[0,0,1,1]],baseline=row.y-row.inkTop;for(var n=0;n<ink.length;n++){var b=ink[n];result.push([pen+m.width*b[0],baseline+m.top+m.height*b[1],pen+m.width*b[2],baseline+m.top+m.height*b[3]]);}pen+=m.width+(k+1<row.words.length?space(id,row.words[k+1]):0);}return result;}
  function clearance(a,b,below){var aa=boxes(a),bb=boxes(b),move=0;for(var ai=0;ai<aa.length;ai++)for(var bi=0;bi<bb.length;bi++){var x=aa[ai],y=bb[bi];if(Math.min(x[2],y[2])-Math.max(x[0],y[0])<=0)continue;if(below)move=Math.max(move,y[3]+gap-x[1]);else move=Math.max(move,x[3]+gap-y[1]);}return Math.max(0,move);}
  var lift=Math.max(head?clearance(head,main,false):0,rightHead?clearance(rightHead,main,false):0);if(head)head.y-=lift;if(rightHead)rightHead.y-=lift;if(bottom)bottom.y+=clearance(bottom,main,true);
  var left=1e20,right=-1e20,top=1e20,last=-1e20,zoom=1;
  for(i=0;i<page.camera.length;i++)zoom=Math.max(zoom,page.camera[i][1]);
  for(i=0;i<rows.length;i++){row=rows[i];left=Math.min(left,row.x);right=Math.max(right,row.x+row.width);top=Math.min(top,row.y);last=Math.max(last,row.y+row.height);}
  var fit=Math.min(.70,width*page.safe_width_fraction/Math.max(1,(right-left)*zoom+36*factor),height*.3/Math.max(1,(last-top)*zoom+32*factor)),dx=width/2-(left+right)*fit/2,dy=height/2-(top+last)*fit/2,result={words:[],rows:{},fit:fit};
  for(i=0;i<rows.length;i++){row=rows[i];var pen=row.x;result.rows[row.id]={left:dx+pen*fit,right:dx+(pen+row.width)*fit,top:dy+row.y*fit,bottom:dy+(row.y+row.height)*fit};for(j=0;j<row.words.length;j++){id=row.words[j];var m=metrics[id],x=dx+(pen+m.width/2)*fit,y=dy+(row.y-row.inkTop+m.top+m.height/2)*fit;result.words[id]={x:x,y:y,scale:fit,bounds:[x-m.width*fit/2,y-m.height*fit/2,x+m.width*fit/2,y+m.height*fit/2]};pen+=m.width+(j+1<row.words.length?space(id,row.words[j+1]):0);}}
  result.pivot=[width/2,height/2];result.ink_clearance_verified=true;result.ink_boxes=[];for(i=0;i<rows.length;i++){var blocks=boxes(rows[i]);for(j=0;j<blocks.length;j++)result.ink_boxes.push({row:rows[i].id,bounds:[dx+blocks[j][0]*fit,dy+blocks[j][1]*fit,dx+blocks[j][2]*fit,dy+blocks[j][3]*fit]});}return result;
 }
 g.StorylensCaptionGeometry={layout:layout};
})(typeof $!=='undefined'?$.global:this);
