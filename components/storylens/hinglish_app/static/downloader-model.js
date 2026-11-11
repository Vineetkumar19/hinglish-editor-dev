(function(root,factory){const api=factory();root.storylensDownloader=api;if(typeof module==='object'&&module.exports)module.exports=api;})(typeof window==='object'?window:this,()=>({
  platform(value){try{const h=new URL(value).hostname.toLowerCase();if(['youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be','www.youtu.be'].includes(h))return 'youtube';if(['instagram.com','www.instagram.com','m.instagram.com'].includes(h))return 'instagram';if(['pinterest.com','www.pinterest.com','in.pinterest.com','uk.pinterest.com','pinterest.co.uk','www.pinterest.co.uk','pin.it','www.pin.it'].includes(h))return 'pinterest';if(['facebook.com','www.facebook.com','m.facebook.com','web.facebook.com','fb.watch','www.fb.watch'].includes(h))return 'facebook';}catch(_){}return '';},
  request(url,quality,mode,audio_format,extra={}){return {url:url.trim(),quality:this.platform(url)==='youtube'?quality:'best',mode,audio_format,...extra};},
  progress(job){
    if(job.source){
      const percent=Number.isFinite(job.stage_progress)?Math.min(99,Math.max(0,job.stage_progress)):null;
      return {downloaded:true,percent,stage:job.stage+(percent===null?'':' · '+percent+'%')};
    }
    const percent=Math.min(99,Math.max(0,Math.floor((Number(job.progress)||0)*100/85)));
    return {downloaded:false,percent,stage:job.stage};
  },
  summary(asset){const duration=`${Number(asset.duration).toFixed(1)} sec`;return asset.kind==='audio'?`${duration} · ${asset.channels} channel${asset.channels===1?'':'s'} · ${asset.sample_rate/1000} kHz`:`${asset.width} × ${asset.height} · ${duration}`;}
}));
