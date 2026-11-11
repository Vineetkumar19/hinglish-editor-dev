/* Template Aliner: ES3, one ordered pass, active-video duration, no repeats. */
(function(root){
 function fail(message){throw Error(message);}
 function natural(a,b){var x=String(a).toLowerCase().match(/\d+|\D+/g)||[],y=String(b).toLowerCase().match(/\d+|\D+/g)||[],i;
  for(i=0;i<Math.min(x.length,y.length);i++){if(x[i]===y[i])continue;if(/^\d+$/.test(x[i])&&/^\d+$/.test(y[i])){if(Number(x[i])!==Number(y[i]))return Number(x[i])-Number(y[i]);}else return x[i]<y[i]?-1:1;}return x.length-y.length;}
 function choose(comps,stem,target,explicit){var ranked=[],i,c,score,bad;
  if(typeof explicit!=='undefined'&&explicit!==null&&explicit!==''){
   for(i=0;i<comps.length;i++)if(String(comps[i].id)===String(explicit))return {selected:comps[i].id,comps:comps};
   fail('The chosen composition does not belong to this template folder. Read the folders again.');
  }
  for(i=0;i<comps.length;i++){c=comps[i];bad=/placeholder|precomp|pre comp|footage|logo holder|text holder|do not edit|tutorial|preview|help|^(text|image|photo|media|audio|music|sound|texture|overlay|overley|leaks|noise)([ _\-\d]|$)/i.test(c.name);
   score=SLTemplateModel.rank(c,String(stem).replace(/\.aepx?$/i,''));
   var ratio=Number(c.width)/Number(c.height),wanted=Number(target.width)/Number(target.height);
   score+=40*Math.min(ratio/wanted,wanted/ratio);
   if(!c.usedBy)score+=180;
   score+=Math.min(100,18*Math.log(1+(Number(c.descendants)||0)));
   score+=Math.min(30,Number(c.duration)/3);
   if(/render|rander|output|master|final|customize|color[ _-]*edit/i.test(c.name))score+=55;
   if(/long[ _-]*version|full[ _-]*version/i.test(c.name))score+=20;
   if(/short[ _-]*version|demo|sample/i.test(c.name))score-=20;
   if(bad)score-=400;
   if(Number(c.numLayers)===0)score-=80;
   ranked.push({comp:c,score:score});
  }
  ranked.sort(function(a,b){return b.score-a.score||natural(a.comp.name,b.comp.name)||Number(a.comp.id)-Number(b.comp.id);});
  var selected=ranked.length?ranked[0].comp.id:null;
  var choices=[];for(i=0;i<ranked.length;i++)choices.push(ranked[i].comp);
  return {selected:selected,comps:choices};
 }
 function plan(rows,target){var fps=Number(target.fps),seconds=Number(target.duration),frames=Math.round(seconds*fps),at=0,out=[],i,n,c;
  if(!isFinite(fps)||fps<=0||!isFinite(seconds)||seconds<=0||frames<1)fail('Open a video composition with a valid duration and frame rate.');
  for(i=0;i<rows.length&&at<frames;i++){c=rows[i].comp;n=Math.floor(Number(c.duration)*fps+1e-5);
   if(!isFinite(n)||n<1)fail('Template '+rows[i].folder+' is shorter than one video frame.');
   var used=Math.min(n,frames-at);out.push({rowIndex:i,start:at/fps,end:Math.min(seconds,(at+used)/fps),trimmed:used<n});at+=used;
  }
  return {fps:fps,duration:seconds,segments:out,covered_duration:at/fps,uncovered_duration:Math.max(0,seconds-at/fps),repeated:false};
 }
 function fresh(rows,target,previous,random){
  var indexes=[],ordered=[],i,j,t;random=random||Math.random;previous=previous||[];
  for(i=0;i<rows.length;i++)indexes.push(i);
  for(i=indexes.length-1;i>0;i--){j=Math.floor(Math.max(0,Math.min(.999999999,Number(random())||0))*(i+1));t=indexes[i];indexes[i]=indexes[j];indexes[j]=t;}
  // A fresh run must have a different opening whenever a second template exists.
  if(indexes.length>1&&previous.length&&String(rows[indexes[0]].folderId)===String(previous[0])){j=1+Math.floor(Math.max(0,Math.min(.999999999,Number(random())||0))*(indexes.length-1));t=indexes[0];indexes[0]=indexes[j];indexes[j]=t;}
  for(i=0;i<indexes.length;i++)ordered.push(rows[indexes[i]]);
  var result=plan(ordered,target);
  for(i=0;i<result.segments.length;i++)result.segments[i].rowIndex=indexes[result.segments[i].rowIndex];
  result.variety_available=rows.length>1;result.full_template_animations=true;
  return result;
 }
 root.SLTemplateAlinerModel={natural:natural,choose:choose,plan:plan,fresh:fresh};
})(typeof $!=='undefined'&&$.global?$.global:(typeof window!=='undefined'?window:this));
