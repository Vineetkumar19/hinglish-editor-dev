// The server prepends the same error catalog used by Python. No AI call is
// needed to explain a failure, including when the model service is offline.
(()=>{
  const rules=(window.storylensErrorCatalog||[]).map(rule=>({...rule,match:new RegExp(rule.pattern,'i')}));
  const fallback='Storylens could not finish this step because an unexpected error occurred. Check saved progress before retrying. If it happens again, keep the technical details for repair.';
  function clean(value){return String(value||'').replace(/([?&](?:token|access_token|key|api_key)=)[^\s&#"'<>]+/gi,'$1[hidden]').replace(/(Bearer\s+)[A-Za-z0-9._~+/-]+/gi,'$1[hidden]').replace(/(["']?(?:api_key|access_token|refresh_token|X-Hinglish-Token|X-Storylens-Browser)["']?\s*[:=]\s*["']?)[^\s,"'}]+/gi,'$1[hidden]').slice(0,16000)}
  function issue(value,status){
    const raw=String(value?.message||value?.error||value||'');
    const evidence=value?.name&&/Error$/.test(value.name)?value.name+': '+raw:raw;
    let code=value?.code||value?.error_code,message=raw;
    if(!(code&&raw)){
      const rule=rules.find(rule=>rule.match.test(evidence));
      if(rule){code=rule.code;message=rule.message}
      else if(/Failed to fetch|NetworkError|Load failed/i.test(raw)){code='local_connection';message='Cannot reach Storylens. Keep the local editor running and check the connection. Your task may still be processing; reconnect before starting it again.'}
      else if(status===404){code='not_found';message='This saved item or feature is unavailable. Refresh Storylens and select it again.'}
      else if(status===401||status===403){code='connection_required';message='This page is not connected to Storylens. Reopen it from the local editor, then try again.'}
      else if(/Unexpected token|Unexpected end.*JSON|JSON.parse/i.test(raw)){code='unreadable_response';message='The local service returned an unreadable response. Refresh Storylens and check saved progress before retrying.'}
      else if(/Traceback|\b(?:TypeError|KeyError|AttributeError|RuntimeError|ReferenceError|SyntaxError)\b|https?:\/\/|^Command\s|^\(?[45]\d\d\b|^\s*[\[{]/i.test(evidence)||status>=500||!raw){code='task_failed';message=fallback}
      else {code='request_failed';if(!/\b(?:choose|select|check|try|reopen|refresh|start|resume|give|tell|supply|keep|connect|sign in|wait|attach|open|install|use|enter|paste|remove|split|name|enable|set)\b/i.test(raw))message=raw.replace(/\.$/,'')+'. Check this feature’s selected files and settings, then retry the unfinished step. For uploads, check saved receipts first.'}
    }
    return {code,message:clean(message),details:clean(value?.details||value?.error_details||(message!==raw?evidence:''))};
  }
  window.storylensProblem=issue;
  window.storylensDetails=value=>{
    const p=issue(value);if(!p.details||p.details===p.message)return null;
    const box=document.createElement('details');box.className='storylens-error-details';
    box.style.cssText='margin:12px 0;padding:12px;border:1px solid #46515b;border-radius:8px;overflow-wrap:anywhere';
    const summary=document.createElement('summary'),raw=document.createElement('pre');summary.textContent='Technical details';raw.textContent=p.details;
    raw.style.cssText='white-space:pre-wrap;max-height:240px;overflow:auto;font-size:13px';box.append(summary,raw);return box;
  };
  window.storylensError=value=>{
    const p=issue(value),details=window.storylensDetails(p);
    const old=document.getElementById('storylensErrorDetails');if(old)old.remove();
    if(details){details.id='storylensErrorDetails';details.style.margin='16px';
      (document.querySelector('dialog[open]')||document.querySelector('main')||document.body).append(details)}
    return p.message;
  };
  window.storylensJobError=job=>Object.assign(Error(job.error||job.message||job.stage||fallback),{code:job.error_code,details:job.error_details});
  window.storylensFetch=async(...args)=>{
    try{return await fetch(...args)}catch(error){
      const p=issue(error);throw Object.assign(Error(p.message),{code:p.code,details:p.details||clean(error?.message),cause:error});
    }
  };
  window.storylensResponse=async response=>{
    let data;
    try{data=await response.json()}catch(_){
      const p=issue('',response.status);throw Object.assign(Error(p.message),{code:p.code,details:'The local service returned an unreadable response (HTTP '+response.status+').'});
    }
    if(!response.ok){
      const p=issue(data?.error?{message:data.error,code:data.error_code,details:data.error_details}:null,response.status);
      throw Object.assign(Error(p.message),{code:p.code,details:p.details||('HTTP '+response.status)});
    }
    return data;
  };
  window.storylensXHR=xhr=>window.storylensResponse({status:xhr.status,ok:xhr.status>=200&&xhr.status<300,json:async()=>JSON.parse(xhr.responseText)});
  function unexpected(value){
    const box=document.getElementById('storylensUnexpectedError')||document.createElement('section');
    box.id='storylensUnexpectedError';box.setAttribute('role','alert');box.style.cssText='position:fixed;bottom:18px;left:18px;right:18px;z-index:10000;padding:18px;background:#20272e;color:#ffb9a5;border:1px solid #9a5b46;border-radius:12px;max-height:45vh;overflow:auto';
    const p=issue(value),text=document.createElement('p'),close=document.createElement('button');text.textContent=p.message;close.textContent='Dismiss';close.onclick=()=>box.remove();
    box.replaceChildren(text);const details=window.storylensDetails(p);if(details)box.append(details);box.append(close);document.body.append(box);
  }
  window.storylensShowError=unexpected;
  window.storylensClearError=()=>document.getElementById('storylensErrorDetails')?.remove();
  window.addEventListener?.('unhandledrejection',event=>unexpected(event.reason));
  window.addEventListener?.('error',event=>{if(event.error)unexpected(event.error)});
})();
