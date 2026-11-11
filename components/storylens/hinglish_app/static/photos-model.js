(function(root){
  const api={
    active:job=>!!job&&!['done','failed','cancelled','interrupted','archived'].includes(job.status),
    startPayload:(id,name,minEdge=0,profile='general',destination='folder',previews=true)=>{if(!id)throw Error('Add a screenshot before collecting photos.');return {upload_id:id,name:String(name||'').trim().slice(0,100),profile,min_edge:Number(minEdge),destination,previews}},
    canImport:row=>['ready','saved','duplicate'].includes(row.status)||!!row.preview_file,
    previewLabel:job=>api.active(job)?'Preview · finding original':'Preview · original unresolved',
    receiptFor:(job,host='aftereffects')=>job.native_receipts?.[host]||(host==='aftereffects'?job.ae_receipt:null)||null,
    canSave:row=>['ready','saved','duplicate'].includes(row.status),
    previewKind:row=>['ready','saved','duplicate'].includes(row.status)?'photo':'crop',
    publicLink:value=>{try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null}catch(_){return null}},
    resultLabel:row=>({saved:'Downloaded · photo matched',duplicate:'Duplicate of photo '+row.duplicate_of,review:'Needs review · not downloaded',missing:'Not found',pending:'Waiting for a match'})[row.status]||'Finding photo…',
    summary:job=>{const c=job.counts;return `${c.found??c.saved+c.duplicates} ready · ${c.saved} saved · ${c.review+c.missing+(c.low_quality||0)} unresolved · ${c.total} photos`}
  };
  root.PhotoCollector=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
