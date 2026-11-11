/* Caption 3 source-specific offset rows; fixed slots and shared row baselines. */
(function(g){
 function layout(page,metrics,width,height){
  var factor=Math.min(width,height*.75)/720,limit=width*page.safe_width_fraction,rows=[],top=0,left=1e20,right=-1e20,last=0,peak=1,i,j;
  for(i=0;i<page.camera.length;i++)peak=Math.max(peak,page.camera[i][1]);
  for(i=0;i<page.rows.length;i++){var src=page.rows[i],row={id:src.id,words:src.words,width:0,inkTop:1e20,inkBottom:-1e20,offset:src.offset*factor,scale:1};for(j=0;j<src.words.length;j++){var id=src.words[j],m=metrics[id];row.width+=m.width;if(j)row.width+=Math.min(page.words[src.words[j-1]].size,page.words[id].size)*factor*page.word_gap_em;row.inkTop=Math.min(row.inkTop,m.top);row.inkBottom=Math.max(row.inkBottom,m.top+m.height);}row.scale=Math.min(1,(limit/peak-32*factor)/Math.max(1,row.width));row.width*=row.scale;row.height=(row.inkBottom-row.inkTop)*row.scale;row.x=-row.width/2+Math.max(-(limit/peak-row.width)/2,Math.min((limit/peak-row.width)/2,row.offset));row.y=last;if(i)row.y+=page.ink_gap*factor;last=row.y+row.height;left=Math.min(left,row.x);right=Math.max(right,row.x+row.width);rows.push(row);}
  var fit=Math.min(1,(height*.40)/(Math.max(1,last)*peak+48*factor)),dx=width/2-(left+right)*fit/2,dy=height*page.anchor_y-last*fit/2,result={words:[],rows:{},fit:fit,pivot:[width/2,height*page.anchor_y]};
  for(i=0;i<rows.length;i++){row=rows[i];var pen=0;result.rows[row.id]={left:dx+row.x*fit,right:dx+(row.x+row.width)*fit,top:dy+row.y*fit,bottom:dy+(row.y+row.height)*fit};for(j=0;j<row.words.length;j++){id=row.words[j];m=metrics[id];var scale=row.scale*fit,x=dx+(row.x+pen+m.width*row.scale/2)*fit,y=dy+row.y*fit+(m.top-row.inkTop+m.height/2)*scale;result.words[id]={x:x,y:y,scale:scale,bounds:[x-m.width*scale/2,y-m.height*scale/2,x+m.width*scale/2,y+m.height*scale/2]};pen+=m.width*row.scale;if(j+1<row.words.length)pen+=Math.min(page.words[id].size,page.words[row.words[j+1]].size)*factor*page.word_gap_em*row.scale;}}
  return result;
 }
 g.StorylensCaptionGeometry={layout:layout};
})(typeof $!=='undefined'?$.global:this);
