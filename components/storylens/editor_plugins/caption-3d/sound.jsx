/* Portable short SFX. Save permanent sources so AE projects retain their audio links. */
(function(global){
 function decode(text){var chars='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/',out='',value=0,bits=0;for(var i=0;i<text.length;i++){var n=chars.indexOf(text.charAt(i));if(n<0)continue;value=(value<<6)|n;bits+=6;if(bits>=8){bits-=8;out+=String.fromCharCode((value>>bits)&255);}}return out;}
 function fileFor(asset){
  if(asset.path){var local=new File(asset.path);if(!local.exists)throw Error('The saved caption sound is missing. Reopen Storylens after restoring its sound files.');return local;}
  var parent=new Folder(Folder.myDocuments.fsName+'/Storylens');if(!parent.exists&&!parent.create())throw Error('Allow After Effects to save the caption sound files in Documents.');
  var folder=new Folder(parent.fsName+'/3D Caption Sounds');if(!folder.exists&&!folder.create())throw Error('The caption sound folder could not be created.');
  var file=new File(folder.fsName+'/'+asset.sha256+'.wav'),binary=decode(asset.base64),same=false;file.encoding='BINARY';
  if(file.exists&&file.open('r')){same=file.read()===binary;file.close();}
  if(!same){if(!file.open('w'))throw Error('The caption sound could not be saved.');try{if(!file.write(binary))throw Error('The caption sound could not be written.');}finally{file.close();}}
  return file;
 }
 function add(comp,start,events,root,owned){
  var data=global.StorylensCaptionAudioData,cache={},count=0;
  if(!data)throw Error('The caption sound files are not loaded. Reopen Storylens.');
  for(var i=0;i<events.length;i++){
   var e=events[i],time=start+e.time,end=Math.min(comp.duration,start+8,time+data[e.kind].duration);if(end-time<.02)continue;
   var asset=data[e.kind],source=cache[e.kind],marker='Storylens Caption SFX '+asset.sha256;
   if(!source){
    for(var n=1;n<=app.project.numItems;n++){var item=app.project.item(n);if(item.parentFolder===root&&String(item.comment||'')===marker){source=item;break;}}
    if(!source){source=app.project.importFile(new ImportOptions(fileFor(asset)));if(owned)owned.items.push(source);source.name='SFX - '+e.kind;source.parentFolder=root;source.comment=marker;}
    cache[e.kind]=source;
   }
   var l=comp.layers.add(source);if(owned)owned.layers.push(l);l.name='SFX - '+e.kind+' '+(i+1);l.audioEnabled=true;l.startTime=time;l.inPoint=time;l.outPoint=end;
   var levels=l.property('ADBE Audio Group').property('ADBE Audio Levels'),gain=typeof e.db==='number'?e.db:-20;
   levels.setValueAtTime(time,[-48,-48]);levels.setValueAtTime(time+.006,[gain,gain]);levels.setValueAtTime(Math.max(time+.007,end-.015),[gain,gain]);levels.setValueAtTime(end,[-48,-48]);l.moveToEnd();count++;
  }
  return count;
 }
 function events(mode,delay){
  mode=mode||'pop_click';delay=Number(delay||0);if(mode==='pop')return [{kind:'pop',time:delay,db:-20}];
  if(mode==='click')return [{kind:'click',time:delay,db:-20}];
  if(mode==='pop_click')return [{kind:'pop',time:delay,db:-20},{kind:'click',time:delay+.24,db:-23}];
  if(mode==='pop_click_whoosh')return [{kind:'whoosh',time:delay,db:-28},{kind:'pop',time:delay+.16,db:-20},{kind:'click',time:delay+.36,db:-23}];
  throw Error('Choose a supported caption sound.');
 }
 function state(source){var m=String(source.comment||'').match(/\[Storylens caption audio (pop_click_whoosh|pop_click|pop|click) ([01]) ([a-f0-9]*)\]/);if(!m)return null;return {mode:m[1],enabled:m[2]==='1',update:m[3]};}
 function mark(source,mode,enabled,request){source.comment=String(source.comment||'').replace(/\n?\[Storylens caption audio (pop_click_whoosh|pop_click|pop|click) [01] [a-f0-9]*\]/g,'')+'\n[Storylens caption audio '+mode+' '+(enabled?'1':'0')+' '+(request||'')+']';}
 global.StorylensCaptionSounds={add:add,events:events,state:state,mark:mark};
})(typeof $!=='undefined'?$.global:this);
