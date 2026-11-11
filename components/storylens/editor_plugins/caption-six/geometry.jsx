/* Native Caption 6: source bands/offsets, complete slots and common baselines. */
(function(g){
 function layout(page,metrics,width,height){
  var factor=Math.min(width,height*.75)/720,limit=width*page.safe_width_fraction,rows=[],bands=[],i,j,reserve=36*factor;for(i=0;i<page.decorations.length;i++)if(page.decorations[i].kind==='circle')reserve=152*factor;
  for(i=0;i<page.rows.length;i++){
   var src=page.rows[i],row={id:src.id,source_row:src.source_row,band:src.band,words:src.words,width:0,top:1e20,bottom:-1e20,offset:src.offset*factor};
   for(j=0;j<src.words.length;j++){var id=src.words[j],m=metrics[id];row.width+=m.width;if(j)row.width+=Math.min(page.words[id].size,page.words[src.words[j-1]].size)*factor*page.word_gap_em;row.top=Math.min(row.top,m.top);row.bottom=Math.max(row.bottom,m.top+m.height);}
   row.scale=Math.min(1,(limit-reserve)/Math.max(1,row.width));row.width*=row.scale;row.height=(row.bottom-row.top)*row.scale;
   row.x=-row.width/2+Math.max(-(limit-row.width)/2,Math.min((limit-row.width)/2,row.offset));rows.push(row);
   var band=null;if(!page.replace_words)for(j=0;j<bands.length;j++)if(bands[j].id===row.band)band=bands[j];if(!band){band={id:page.replace_words?src.id:row.band,rows:[]};bands.push(band);}band.rows.push(row);
  }
  var last=0,left=1e20,right=-1e20;
  for(i=0;i<bands.length;i++){
   var b=bands[i],edge=-1e20,desiredLeft=1e20,desiredRight=-1e20;b.rows.sort(function(a,b){return a.offset-b.offset;});
   for(j=0;j<b.rows.length;j++){row=b.rows[j];desiredLeft=Math.min(desiredLeft,row.x);desiredRight=Math.max(desiredRight,row.x+row.width);}
   for(j=0;j<b.rows.length;j++){row=b.rows[j];row.x=Math.max(row.x,edge+8*factor);edge=row.x+row.width;}
   var packedLeft=b.rows[0].x,packedRight=edge,shift=(desiredLeft+desiredRight-packedLeft-packedRight)/2,fit=Math.min(1,(limit-reserve)/Math.max(1,packedRight-packedLeft)),centre=(packedLeft+packedRight)/2;
   b.top=1e20;b.bottom=-1e20;
   for(j=0;j<b.rows.length;j++){row=b.rows[j];row.x=(row.x-centre)*fit+(centre+shift)*fit;row.scale*=fit;row.width*=fit;row.height*=fit;b.top=Math.min(b.top,row.top*row.scale);b.bottom=Math.max(b.bottom,row.bottom*row.scale);}
   b.y=page.replace_words?0:last+(i?page.ink_gap*factor:0);b.height=b.bottom-b.top;
   for(j=0;j<b.rows.length;j++){row=b.rows[j];row.y=b.y+(row.top*row.scale-b.top);left=Math.min(left,row.x);right=Math.max(right,row.x+row.width);}
   last=page.replace_words?Math.max(last,b.height):b.y+b.height;
  }
  var fit=Math.min(1,height*.35/Math.max(1,last+60*factor)),dx=width*.5-(left+right)*fit/2,dy=height*page.anchor_y-last*fit/2,result={words:[],rows:{},fit:fit,factor:factor,pivot:[width*.5,height*page.anchor_y]};
  for(i=0;i<rows.length;i++){
   row=rows[i];var pen=0;result.rows[row.id]={source_row:row.source_row,left:dx+row.x*fit,right:dx+(row.x+row.width)*fit,top:dy+row.y*fit,bottom:dy+(row.y+row.height)*fit};
   for(j=0;j<row.words.length;j++){id=row.words[j];m=metrics[id];var scale=row.scale*fit,x=dx+(row.x+pen+m.width*row.scale/2)*fit,y=dy+row.y*fit+(m.top-row.top+m.height/2)*scale;
    if(page.replace_words)y=height*page.anchor_y+(m.top-row.top+m.height/2-(row.bottom-row.top)/2)*scale;
    result.words[id]={x:x,y:y,scale:scale,bounds:[x-m.width*scale/2,y-m.height*scale/2,x+m.width*scale/2,y+m.height*scale/2]};pen+=m.width*row.scale;if(j+1<row.words.length)pen+=Math.min(page.words[id].size,page.words[row.words[j+1]].size)*factor*page.word_gap_em*row.scale;
   }
  }
  return result;
 }
 g.StorylensCaptionGeometry={layout:layout};
})(typeof $!=='undefined'?$.global:this);
