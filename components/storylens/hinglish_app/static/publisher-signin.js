/* Google sign-in feedback only. Account selection and consent belong to the user. */
(function(root){
 function googleUrl(value){
  const url=new URL(value);
  if(url.protocol!=='https:'||url.hostname!=='accounts.google.com'||url.username||url.password||url.hash||!['','443'].includes(url.port)||!['/o/oauth2/auth','/o/oauth2/v2/auth'].includes(url.pathname))throw Error('The Google sign-in link could not be verified. Try again.');
  return url.href;
 }
 function create({button,status,link,start,profile,clientFile,refresh,openWindow,error,label='Sign in with Google'}){
  let requesting=false,popup=null,popupSent=false,pending=false;
  function popupMessage(message){
   if(!popup||popupSent)return;
   try{
    const doc=popup.document;doc.title='YouTube sign-in';
    let messageNode=doc.getElementById('youtubeWindowStatus');
    if(!messageNode){
     const main=doc.createElement('main'),heading=doc.createElement('h1');messageNode=doc.createElement('p');messageNode.id='youtubeWindowStatus';
     heading.textContent='YouTube sign-in';main.append(heading,messageNode);
     doc.body.style.cssText='margin:0;padding:32px;background:#111;color:#eee;font:16px/1.6 system-ui,sans-serif';
     heading.style.cssText='font-size:24px;line-height:1.3;margin:0 0 20px';doc.body.append(main);
    }
    messageNode.textContent=message;
   }catch(_){}
  }
  function ensureWindow(){
   if(!popup||popup.closed){popup=openWindow();popupSent=false;if(popup)popup.opener=null;}
   try{popup?.focus?.();}catch(_){}
  }
  function showUrl(value){
   const url=googleUrl(value);link.href=url;link.hidden=false;
   status.textContent='Open Google to continue';
   if(popup&&!popupSent){try{popup.location.replace(url);popupSent=true;}catch(_){popup=null;}}
  }
  function failed(message){
   requesting=false;button.disabled=false;button.textContent=label;link.hidden=true;status.textContent=message;
   popupMessage(message);
  }
  function observe(tasks){
   const current=tasks.filter(t=>t.kind==='youtube_signin'&&t.profile===profile()).at(-1);
   pending=!!current&&current.status==='working';
   if(current){
    if(current.status==='working'){
     button.disabled=false;button.textContent=label;status.textContent=current.message;popupMessage(current.message);
     if(current.authorization_url){try{showUrl(current.authorization_url);}catch(e){failed(error(e));}}
    }else if(!requesting){button.disabled=false;button.textContent=label;link.hidden=true;status.textContent=current.message;}
    return;
   }
   // Old service attempts have no kind/profile. Show their real waiting state,
   // without marking them cancelled or creating more queued sign-ins.
   const legacy=tasks.find(t=>!t.kind&&t.status==='working'&&(/Complete Google sign-in/.test(t.message||'')||t.can_stop===false&&t.can_resume===false&&/^Preparing/.test(t.message||'')));
   if(legacy){pending=true;button.disabled=false;button.textContent=label;status.textContent='Waiting for Google';link.hidden=true;popupMessage(status.textContent);}
   else if(!requesting){button.disabled=false;button.textContent=label;status.textContent='';link.hidden=true;}
  }
  async function click(){
   try{
    const selected=profile();if(!['cricket','gaming'].includes(selected))throw Error('Choose Cricket or Gaming before connecting YouTube.');
    try{ensureWindow();}catch(_){popup=null;}
    if(requesting||pending){popupMessage(status.textContent||'Waiting for the Google sign-in link from Storylens.');if(!link.hidden)showUrl(link.href);return;}
    requesting=true;button.disabled=false;button.textContent=label;status.textContent='Opening Google';link.hidden=true;
    popupMessage(status.textContent);
    const result=await start({client_file:clientFile()},selected);
    if(result.authorization_url)showUrl(result.authorization_url);
    else{status.textContent='Waiting for Google';popupMessage(status.textContent);}
    requesting=false;await refresh();
   }catch(e){failed(error(e));}
  }
  button.onclick=click;button.disabled=false;
  return {click,observe};
 }
 const api={create};if(typeof module==='object'&&module.exports)module.exports=api;else root.StorylensPublisherSignIn=api;
})(typeof window==='object'?window:globalThis);
