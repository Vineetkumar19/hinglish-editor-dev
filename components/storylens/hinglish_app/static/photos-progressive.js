(function(root){
 const ready=row=>['ready','saved','duplicate'].includes(row.status)&&row.width>0&&row.height>0;
 const key=(id,item)=>String(id)+':'+String(item);
 function delivered(job,host){const result=new Set(),receipt=job.native_receipts?.[host]||(host==='aftereffects'?job.ae_receipt:null);for(const kind of ['imported','upgraded','already_present'])for(const row of receipt?.[kind]||[])result.add(String(row.photo_id));return result;}
 root.PhotoProgressive={ready,key,delivered,waiting:(job,queued)=>(job.photos||[]).filter(row=>ready(row)&&!row.download_file&&!queued.has(key(job.id,row.id)))};
})(globalThis);
