/* Shared ES3 library rules. No project mutations in this module. */
(function(root,factory){var api=factory();if(typeof $!=='undefined'&&$.global)$.global.SLCinematicModel=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SLCinematicModel=api;})(this,function(){
 function natural(a,b){var aa=String(a).toLowerCase().match(/\d+|\D+/g)||[],bb=String(b).toLowerCase().match(/\d+|\D+/g)||[];for(var i=0;i<Math.min(aa.length,bb.length);i++){var x=aa[i],y=bb[i];if(x===y)continue;if(/^\d+$/.test(x)&&/^\d+$/.test(y))return Number(x)-Number(y);return x<y?-1:1;}return aa.length-bb.length;}
 function scenes(rows,kind){var patterns={interactive:/^Scene\s+\d+$/i,cinematic:/^title_0*[1-3]$/i,intro:/^Cinematic Title\s+\d+$/i,lowerThirds:/^Cinematic Lower Third\s+\d+$/i},out=[],i;
  for(i=0;i<rows.length;i++){var r=rows[i];if(patterns[kind]){if(patterns[kind].test(r.name))out.push(r);}else if(r.text&&!/(?:edit|change|color|colour|control|placeholder|preview|master|render|final output)/i.test(r.name)&&(/^(?:scene|title|cinematic title|text animation)[ _-]*\d+$/i.test(r.name)||!r.usedBy))out.push(r);}
  out.sort(function(a,b){return natural(a.name,b.name);});return out;
 }
 function background(r){if(r.text||r.containsText||r.matte||r.controller||r.adjustment)return false;var name=String(r.name||'')+' '+String(r.sourceName||'');if((/(?:^|[ _.-])(?:bgs?|backgrounds?|backdrops?)(?:$|[ _.-])/i.test(name)||/media[ _-]*place[ _-]*holder\s*\d*/i.test(name))&&/^(solid|shape|footage|comp)$/.test(r.kind))return true;if(r.masked||r.parent)return false;return (r.kind==='solid'||r.kind==='shape'&&r.filled===true)&&r.fullFrame===true&&r.bottom===true;}
 return {natural:natural,scenes:scenes,background:background};
});
