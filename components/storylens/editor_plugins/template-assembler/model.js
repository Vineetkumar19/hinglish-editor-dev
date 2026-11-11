/* Shared frame-accurate planner; ES3-compatible for After Effects and Premiere. */
(function(root){
  function fail(code,detail){var e=new Error(detail);e.code=code;throw e;}
  function number(v,min,max,label){v=Number(v);if(!isFinite(v)||v<min||v>max)fail('template_settings',label+' is outside the supported range.');return v;}
  function normalized(s){return String(s).toLowerCase().replace(/[_\-]+/g,' ').replace(/^\s+|\s+$/g,'').replace(/^\d+[ .]+/,'');}
  function rank(c,stem){
    var n=normalized(c.name),score=0;
    if(/^(main|main comp|main composition|render|render comp|final|final comp|master|master comp)$/.test(n))score=100;
    else if(/(^|\s)(main|render|final|master)(\s|$)/.test(n))score=75;
    if(normalized(stem)===n)score=Math.max(score,85);
    if(c.renderQueued)score+=100;
    if(!c.usedBy)score+=20;
    if(/placeholder|precomp|pre comp|footage|logo holder|text holder|do not edit/.test(n))score-=120;
    score+=Math.min(10,Number(c.duration)/60);
    return score;
  }
  function choose(comps,stem){
    var sorted=comps.slice(0),i;
    for(i=0;i<sorted.length;i++)sorted[i].score=rank(sorted[i],stem);
    sorted.sort(function(a,b){return b.score-a.score || a.name.localeCompare(b.name);});
    return {comps:sorted,selected:sorted.length&&(sorted.length===1 || (sorted[0].score>=95 && sorted[0].score-(sorted[1]?sorted[1].score:-999)>=15))?sorted[0].id:null};
  }
  function plan(rows,options){
    options=options||{};
    if(!rows||!rows.length)fail('template_empty','Add at least one project and choose its main composition.');
    var first=rows[0].comp;if(!first)fail('template_choice','Choose the main composition for template 1.');
    var fps=number(options.fps||first.fps,1,120,'Frame rate'),seconds=number(options.seconds,1,10800,'Target duration');
    var target=Math.round(seconds*fps),segments=[],prepared=[],i,row,c,inTime,duration,frames,total=0,at=0,index=0;
    for(i=0;i<rows.length;i++){
      row=rows[i];c=row.comp;if(!c)fail('template_choice','Choose the main composition for template '+(i+1)+'.');
      inTime=options.workArea?number(c.workAreaStart,0,10800,'Work area start'):0;
      duration=options.workArea?number(c.workAreaDuration,0,10800,'Work area duration'):number(c.duration,0,10800,'Composition duration');
      duration=Math.min(duration,Number(c.duration)-inTime);
      frames=Math.floor(duration*fps+1e-5);if(frames<1)fail('template_settings','Template '+(i+1)+' is shorter than one output frame.');
      total+=frames;prepared.push({row:row,frames:frames,sourceIn:inTime,index:i});
    }
    if(total<target&&!options.repeat)fail('template_short','The ordered list is '+((target-total)/fps).toFixed(2)+' seconds short. Add templates or enable Repeat in order.');
    while(at<target){
      var item=prepared[index%prepared.length];frames=Math.min(item.frames,target-at);
      segments.push({rowIndex:item.index,cycle:Math.floor(index/prepared.length)+1,startFrame:at,endFrame:at+frames,frames:frames,sourceIn:item.sourceIn,trimmed:frames<item.frames});
      at+=frames;index++;
      if(index>10000)fail('template_settings','Too many placements. Use longer compositions or a shorter target.');
    }
    return {fps:fps,frames:target,duration:target/fps,width:Number(first.width),height:Number(first.height),pixelAspect:Number(first.pixelAspect||1),segments:segments,unused:Math.max(0,rows.length-Math.min(index,rows.length)),repeated:index>rows.length};
  }
  root.SLTemplateModel={plan:plan,choose:choose,rank:rank};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.SLTemplateModel;
})(typeof $!=='undefined'&&$.global?$.global:(typeof window!=='undefined'?window:this));
