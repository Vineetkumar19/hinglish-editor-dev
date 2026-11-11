/* Small sampled native frames; no source text, layer timing or owner playhead edits. */
(function(){var root='D:/Full Drive/remove silence',result={frames:[],errors:[]},c=app.project.itemByID(24516),old=c.resolutionFactor;
 try{var samples=[5.42,48.48,377.34,416.1,507.3,703.04,728.97,537.4];c.resolutionFactor=[2,2];
  for(var i=0;i<samples.length;i++){var path=root+'/output/template-text-repair/full-review-'+String(i+1)+'.png';try{c.saveFrameToPng(samples[i],new File(path));result.frames.push({time:samples[i],path:path});}catch(e){result.errors.push({time:samples[i],error:String(e)});}}
 }finally{c.resolutionFactor=old;var f=new File(root+'/output/template-text-repair/full-frame-review.json');f.open('w');f.write(JSON.stringify(result));f.close();}
})();
