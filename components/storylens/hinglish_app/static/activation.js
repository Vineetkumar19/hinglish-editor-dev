(()=>{
  const $=s=>document.querySelector(s),token=document.documentElement.dataset.token;
  const edition=new URLSearchParams(location.search).get('edition')==='plugins'?'plugins':'desktop';
  let timer;
  async function api(path,data){
    const r=await window.storylensFetch(path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},body:data?JSON.stringify(data):undefined});
    const v=await window.storylensResponse(r);if(!r.ok)throw Error(v.error||'Activation unavailable.');return v;
  }
  function active(){
    clearInterval(timer);$('#activate').hidden=true;$('#code-panel').hidden=true;
    $('#status').textContent=edition==='plugins'?'Your Plugin edition is activated. Return to your editing software.':'This computer is activated.';
    $('#open').hidden=edition==='plugins';
  }
  async function poll(){
    try{
      const v=await api('/api/license?edition='+edition);
      if(v.active)active();
      else if(v.error){clearInterval(timer);$('#status').textContent=v.error;}
      else $('#status').textContent='Waiting for approval in your account…';
    }catch(e){$('#status').textContent=window.storylensError(e);}
  }
  $('#activate').onclick=async()=>{
    $('#activate').disabled=true;
    try{
      const v=await api('/api/license/start',{edition});$('#code').textContent=v.user_code;
      $('#account').href=v.verification_uri;$('#code-panel').hidden=false;
      clearInterval(timer);timer=setInterval(poll,5000);
    }catch(e){$('#status').textContent=window.storylensError(e);}
    finally{$('#activate').disabled=false;}
  };
  $('#usage-consent').onchange=async()=>{try{const v=await api('/api/license/usage-preference',{enabled:$('#usage-consent').checked});$('#privacy-status').textContent=v.enabled?'Usage reporting enabled.':'Usage reporting disabled.'}catch(e){$('#privacy-status').textContent=window.storylensError(e);$('#usage-consent').checked=!$('#usage-consent').checked}};
  api('/api/license?edition='+edition).then(v=>{$('#usage-consent').checked=Boolean(v.usage_reporting);if(v.active)active();}).catch(e=>$('#status').textContent=window.storylensError(e));
})();
