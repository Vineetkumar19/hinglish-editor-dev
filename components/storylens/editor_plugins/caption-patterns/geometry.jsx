/* Shared measured-ink geometry. ES3 for AE; also used by offline layout checks. */
(function(g){
 function layout(page,metrics,width,height,uniformScale){
  var factor=width/720,inkGap=9*factor,rows=[],lookup={},i,j;
  function wordGap(a,b){return Math.min(page.words[a].size,page.words[b].size)*factor*(page.word_gap_em||.26);}
  function measure(row,scale){var w=0,top=0,bottom=0;for(var k=0;k<row.words.length;k++){var m=metrics[row.words[k]];w+=m.width*scale+(k?wordGap(row.words[k-1],row.words[k])*scale:0);top=Math.min(top,m.top*scale);bottom=Math.max(bottom,(m.top+m.height)*scale);}return {width:w,top:top,bottom:bottom,height:bottom-top};}
  for(i=0;i<page.rows.length;i++){var source=page.rows[i],r={id:source.id,words:source.words,scale:1,x:0,y:0};r.box=measure(r,1);rows.push(r);lookup[r.id]=r;}
  var main=lookup.main||lookup.inline;
  if(page.kind==='stack'){if(lookup.top){lookup.top.x=0;lookup.top.y=-inkGap-lookup.top.box.height;}main.y=0;if(lookup.bottom){lookup.bottom.x=main.box.width-lookup.bottom.box.width;lookup.bottom.y=main.box.height+inkGap;}}
  else if(page.kind==='pair'){lookup.top.y=0;main.x=lookup.top.box.width*.35;main.y=lookup.top.box.height+inkGap;}
  var left=1e20,right=-1e20,top=1e20,bottom=-1e20;
  for(i=0;i<rows.length;i++){var r=rows[i];left=Math.min(left,r.x);right=Math.max(right,r.x+r.box.width);top=Math.min(top,r.y);bottom=Math.max(bottom,r.y+r.box.height);}
  var safeWidth=Math.min(.66,page.safe_width_fraction||.66),naturalFit=Math.min(1,width*safeWidth/Math.max(1,right-left),height*.34/Math.max(1,bottom-top)),fit=typeof uniformScale==='number'?Math.min(naturalFit,uniformScale):naturalFit,dx=width/2-(left+right)*fit/2,dy=height/2-(top+bottom)*fit/2,result={words:[],rows:{},fit:fit};
  for(i=0;i<rows.length;i++){var r=rows[i],pen=r.x,baseline=r.y-r.box.top;result.rows[r.id]={left:dx+r.x*fit,right:dx+(r.x+r.box.width)*fit,top:dy+r.y*fit,bottom:dy+(r.y+r.box.height)*fit};for(j=0;j<r.words.length;j++){var id=r.words[j],m=metrics[id],scale=r.scale*fit,x=dx+(pen+m.width*r.scale/2)*fit,y=dy+(baseline+(m.top+m.height/2)*r.scale)*fit;result.words[id]={x:x,y:y,scale:scale,bounds:[x-m.width*scale/2,y-m.height*scale/2,x+m.width*scale/2,y+m.height*scale/2]};pen+=(m.width+(j+1<r.words.length?wordGap(id,r.words[j+1]):0))*r.scale;}}
  return result;
 }
 g.StorylensCaptionGeometry={layout:layout};
})(typeof $!=='undefined'?$.global:this);
