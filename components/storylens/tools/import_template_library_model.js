/* ES3: one main project per owner template package. Paths remain data. */
var StorylensLibraryModel=(function(){
 function normal(p){return String(p).replace(/\\/g,'/').replace(/\/+$/,'').toLowerCase();}
 function marker(p){return 'Storylens template library v1|'+normal(p);}
 function rank(row){var n=String(row.path).split(String.fromCharCode(92)).join('/').split('/').pop(),years=n.match(/20\d\d/g)||[],year=0;for(var i=0;i<years.length;i++)year=Math.max(year,Number(years[i]));return [!/precomp/i.test(n)?1:0,!/CS5|CS6/i.test(n)?1:0,!/CC[\s_(]*\d|\b\d+x\b/i.test(n)?1:0,year,!/white|dark|light|short|medium/i.test(n)?1:0,row.modified||0,-n.length];}
 function better(a,b){var x=rank(a),y=rank(b);for(var i=0;i<x.length;i++)if(x[i]!==y[i])return x[i]>y[i];return normal(a.path)<normal(b.path);}
 function plan(rows,root){var base=normal(root)+'/',groups={},keys=[],out=[];for(var i=0;i<rows.length;i++){var r=rows[i],p=normal(r.path);if(p.indexOf(base)!==0||/(?:^|\/)\.\.(?:\/|$)/.test(p)||! /\.(aep|aepx|aet)$/.test(p))continue;var relative=p.slice(base.length),key=relative.split('/')[0];if(!groups[key])keys.push(key);if(!groups[key]||better(r,groups[key]))groups[key]=r;}keys.sort();for(i=0;i<keys.length;i++)out.push(groups[keys[i]]);return out;}
 function pending(rows,markers){var saved={},out=[];for(var i=0;i<markers.length;i++)saved[markers[i]]=true;for(i=0;i<rows.length;i++)if(!saved[marker(rows[i].path)])out.push(rows[i]);return out;}
 function historyKey(path){var s=normal(path),hash=0;for(var k=0;k<s.length;k++)hash=((hash*31)+s.charCodeAt(k))>>>0;return 'h'+hash;}
 function packageMarker(path,root){var base=normal(root)+'/',p=normal(path);if(p.indexOf(base)!==0)return '';return 'Storylens template package v1|'+base+p.slice(base.length).split('/')[0];}
 function batch(rows,comments,history,random,root){
  var saved={},used={},fresh=[],old=[],unique={},i,j,lines,key,pkg;
  for(i=0;i<comments.length;i++){lines=String(comments[i]).split(/\r?\n/);for(j=0;j<lines.length;j++){saved[lines[j]]=true;if(root&&lines[j].indexOf('Storylens template library v1|')===0)saved[packageMarker(lines[j].slice('Storylens template library v1|'.length),root)]=true;}}
  for(i=0;i<history.length;i++)used[history[i]]=true;
  for(i=0;i<rows.length;i++){key=marker(rows[i].path);pkg=root?packageMarker(rows[i].path,root):key;if(saved[key]||saved[pkg]||unique[pkg])continue;unique[pkg]=true;((used[key]||used[historyKey(rows[i].path)])?old:fresh).push(rows[i]);}
  function shuffle(a){for(var k=a.length-1;k>0;k--){var n=Math.floor(Math.max(0,Math.min(.999999999,Number(random())||0))*(k+1)),t=a[k];a[k]=a[n];a[n]=t;}return a;}
  return shuffle(fresh).concat(shuffle(old)).slice(0,20);
 }
 function mediaCandidate(missing,paths,project,root){
  function decoded(p){try{return normal(decodeURI(String(p)));}catch(_){return normal(p);}}
  var base=decoded(root)+'/',p=decoded(project),old=decoded(missing).split('/'),name=old[old.length-1],best=[],score=0;
  if(p.indexOf(base)!==0)return {path:null,reason:'outside_library'};
  var pkg=base+p.slice(base.length).split('/')[0]+'/';
  for(var i=0;i<paths.length;i++){
   var path=decoded(paths[i]);if(path.indexOf(pkg)!==0||/(?:^|\/)\.\.(?:\/|$)/.test(path))continue;
   var parts=path.split('/');if(parts[parts.length-1]!==name)continue;
   var common=0;while(common<Math.min(parts.length,old.length)&&parts[parts.length-1-common]===old[old.length-1-common])common++;
   if(common>score){score=common;best=[paths[i]];}else if(common===score)best.push(paths[i]);
  }
  return {path:best.length===1?best[0]:null,reason:best.length>1?'ambiguous':best.length?'matched':'not_in_package'};
 }
 return {plan:plan,marker:marker,pending:pending,packageMarker:packageMarker,historyKey:historyKey,batch:batch,mediaCandidate:mediaCandidate};
})();
