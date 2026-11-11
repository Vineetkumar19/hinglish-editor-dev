(function(root,factory){const api=factory();root.storylensPanel=api;if(typeof module==='object'&&module.exports)module.exports=api;})(typeof window==='object'?window:this,()=>({
 hosts:['premiere','aftereffects','capcut'],
 tools:['clean','script','captions','broll','visuals','zoom','sound','beats','cinematic','downloader','photos'],
 soundActions:['recommend','auto'],
 choiceCount(format){return format==='long'?2:5;},
 accepts(event,source){return event.source===source;},
 request(mode,shared,context,settings){return {mode,context_id:context.id,script:shared.script,content_format:shared.content_format,settings};}
}));
