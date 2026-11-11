/* Publishing form contracts. The server resolves paths and owns all drafts. */
(function(root){
  function accountLabel(account,handles={}){
    if(!account?.connected)return 'Not connected';
    return String(handles[account.id]||account.name||account.id||'Connected').trim();
  }
  function sourceModes(profile){
    return [{value:'finished',label:'Finished export'},...(profile==='gaming'?[{value:'stream',label:'Stream → highlights'}]:[])];
  }
  function pickedVideo(value,sourceMode='finished'){
    const paths=String(value||'').split(/\r?\n/).map(p=>p.trim()).filter(Boolean);
    if(!paths.length)return null;
    if(paths.length!==1)throw Error('Choose one video at a time. Your previous file is kept.');
    const path=paths[0];
    if(!/^(?:[A-Za-z]:[\\/]|\/)/.test(path))throw Error('The file picker did not return a complete local path. Choose the file again.');
    const supported=sourceMode==='stream'?/\.(?:mp4|mov|mkv|webm|mxf|avi)$/i:/\.mp4$/i;
    if(!supported.test(path))throw Error(sourceMode==='stream'?'Choose a supported video recording.':'Choose a finished MP4 export for this video.');
    return path;
  }
  function connectionLink(profile){
    if(!['cricket','gaming'].includes(profile))throw Error('Choose Cricket or Gaming first.');
    return '/prepare-post.html?profile='+profile+'#connections';
  }
  function intake(form){
    const profile=form.profile;
    if(!['cricket','gaming'].includes(profile))throw Error('Choose Cricket or Gaming before preparing this video.');
    const path=String(form.path||'').trim().replace(/^"(.*)"$/,'$1');
    if(!path)throw Error('Enter the complete path to your finished video or stream.');
    if(/[\r\n]/.test(path))throw Error('Enter one video path. Put instructions in Creator notes.');
    const youtubeSource=form.sourceMode==='stream'&&/^https:\/\/(?:www\.)?(?:youtube\.com\/watch\?|youtube\.com\/live\/|youtu\.be\/)/i.test(path);
    if(!youtubeSource&&!/^(?:[A-Za-z]:[\\/]|\/)/.test(path))throw Error('Enter the complete video path, or a YouTube stream link in Gaming stream mode.');
    const count=Number(form.count);
    if(!Number.isInteger(count)||count<1||count>40)throw Error('Choose between 1 and 40 Shorts.');
    if(form.sourceMode==='stream'&&profile!=='gaming')throw Error('Select Gaming for a stream-to-highlights edit.');
    if(form.sourceMode==='stream')return {route:'prepare',profile,source_mode:'stream',video_path:path,target_minutes:15,shorts_count:count,platforms:form.platforms==='paired'?['youtube','instagram']:['youtube'],notes:String(form.notes||''),script:String(form.script||''),make_shorts:true,daily_window:true,refresh_copy:form.refreshCopy===true};
    return {route:'prepare',profile,video_path:path,kind:form.kind||'auto',shorts_count:count,platforms:form.platforms==='paired'?['youtube','instagram']:['youtube'],notes:String(form.notes||''),script:String(form.script||''),make_shorts:form.makeShorts===true,daily_window:true,refresh_copy:form.refreshCopy===true};
  }
  function workspace(){
    let active=null;const saved=new Map();
    const empty={command:'',sourceMode:'finished',publishKind:'auto',publishDestinations:'youtube',sourceScript:'',notes:'',makeShorts:false,refreshCopy:false};
    return {activate(profile,fields){
      if(active===null){active=profile;return {...fields};}
      if(active===profile)return {...fields};
      saved.set(active,{...fields});active=profile;return {...(saved.get(profile)||empty)};
    }};
  }
  const api={intake,workspace,pickedVideo,connectionLink,sourceModes,accountLabel};if(typeof module==='object'&&module.exports)module.exports=api;else root.StorylensPublisherIntake=api;
})(typeof window==='object'?window:globalThis);
