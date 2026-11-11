/* ES3 naming/output rules. Source names are data; never executable instructions. */
(function(root,factory){var api=factory();if(typeof $!=='undefined'&&$.global)$.global.SLPresetModel=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SLPresetModel=api;})(this,function(){
 var known=[
  [/editorial.motion.gallery/i,'editorial','Motion Gallery'],[/modern.carousel.slideshow/i,'modernCarousel','Modern Carousel'],[/vertical.carousel/i,'verticalCarousel','Vertical Carousel'],
  [/cinematic.cut.transitions/i,'cinematicCut','Cinematic Cuts'],[/flash.frame.transitions/i,'flashFrame','Flash Frames'],[/glow.light.line/i,'glowLine','Glow Lines'],[/grunge.transitions/i,'grunge','Grunge'],[/match.cut.intro/i,'matchIntro','Match Intro'],[/match.cut.text.reveal/i,'matchReveal','Text Reveal'],
  [/comic.book.opener/i,'comicOpener','Comic Book'],[/dynamic.video.opener/i,'dynamicOpener','Video Opener'],[/conference.speed.ramp|speed.ramp.conference/i,'speedRamp','Conference'],
  [/12.text.interactive/i,'interactive','12 Text'],[/cinematic.lower.third/i,'lowerThirds','Lower Thirds'],[/cinematic.title.pack/i,'cinematic','Cinematic Title'],[/intro.cinematic/i,'intro','Intro Cinematic'],[/rolling.text.animation/i,'rolling','Text Animation'],[/text.swap.transitions/i,'textSwap','Text Swap'],[/vintage.movie/i,'vintage','Vintage Movie'],[/chat.kit/i,'chat','Chat Kit'],[/phone.call.notifications/i,'phone','Phone Calls']
 ];
 function base(value){return String(value||'').replace(/\.(?:aepx?|aet)$/i,'').replace(/\s+copy(?:\s+\d+(?:\.\d+|\.x)?)?\s*$/i,'').replace(/[-_](?:\d{7,})$/,'').replace(/[-_]/g,' ').replace(/\s+/g,' ').replace(/^\s+|\s+$/g,'');}
 function profile(value){var text=base(value);for(var i=0;i<known.length;i++)if(known[i][0].test(text))return known[i][1];return 'generic';}
 function shortName(value){var text=base(value);for(var i=0;i<known.length;i++)if(known[i][0].test(text))return known[i][2];text=text.replace(/\s+(?:for\s+)?after\s+effects.*$/i,'').replace(/\s+(?:template|preset|pack)s?$/i,'');var words=text.split(' '),out=[];for(i=0;i<words.length&&i<5;i++){if(out.join(' ').length+words[i].length>38&&out.length)break;out.push(words[i]);}return out.join(' ')||'Untitled';}
 function natural(a,b){var aa=String(a).toLowerCase().match(/\d+|\D+/g)||[],bb=String(b).toLowerCase().match(/\d+|\D+/g)||[];for(var i=0;i<Math.min(aa.length,bb.length);i++){if(aa[i]===bb[i])continue;if(/^\d+$/.test(aa[i])&&/^\d+$/.test(bb[i]))return Number(aa[i])-Number(bb[i]);if(aa[i]<bb[i])return -1;return 1;}return aa.length-bb.length;}
 function cover(rows,name){var ranked=[],wanted=base(name).toLowerCase().replace(/(?:cc)?\d{4}|[^a-z0-9]/g,'');for(var i=0;i<rows.length;i++){var r=rows[i],n=String(r.name||''),f=String(r.folder||'');if(!(r.duration>0)||/^(?:PO_|SQ_)|control|placeholder|^image(?:_|\b)|^photo[_\s]*\d|^text[_\s]*\d|^footage(?:_|\b)|^media(?:_|\b)|^color(?:_|\b)/i.test(n))continue;var normalized=base(n).toLowerCase().replace(/[^a-z0-9]/g,''),score=0;if(!r.usedBy)score+=20;if(/final|render|output|main|master/i.test(n))score+=70;if(/final|render/i.test(f))score+=35;if(wanted&&normalized.length>3&&(wanted.indexOf(normalized)===0||normalized.indexOf(wanted)===0))score+=90;if(/assets?|media|footage|placeholders?|images?|solids?/i.test(f))score-=100;ranked.push({row:r,score:score});}ranked.sort(function(a,b){return b.score-a.score||b.row.duration-a.row.duration||natural(a.row.name,b.row.name);});return ranked.length?ranked[0].row:null;}
 function select(rows,kind,name){if(kind==='documentaryCover'){var chosen=cover(rows,name);return chosen?[chosen]:[];}if(kind==='documentary'){var finals=[],roots=[];for(var di=0;di<rows.length;di++){var dr=rows[di],dn=String(dr.name||''),df=String(dr.folder||'');if(!(dr.duration>0)||/control|placeholder|^image(?:_|\b)|^photo[_\s]*\d|^text[_\s]*\d|^footage(?:_|\b)|^media(?:_|\b)|^color(?:_|\b)|^logo\s*\d/i.test(dn)||/(?:^|\/)(?:assets?|media|footage|placeholders?|images?|solids?)(?:\/|$)/i.test(df))continue;if(!dr.usedBy)roots.push(dr);if(/final|render|output|main|master/i.test(dn)||/render|final/i.test(df))finals.push(dr);}var complete=finals.length?finals:roots;complete.sort(function(a,b){return natural(a.name,b.name)||Number(a.id)-Number(b.id);});return complete;}
 var out=[],i;for(i=0;i<rows.length;i++){var r=rows[i],n=r.name,f=String(r.folder||''),yes=false;
  if(kind==='editorial')yes=/^Carousel (?:Arc|Shuffle|Vertical|Wide)/i.test(n)&&/\bFinal\b/i.test(f);
  else if(kind==='modernCarousel')yes=/^Carousel [1-3] (Horizontal|Vertical)$/i.test(n)&&/Final Comp/i.test(f);
  else if(kind==='verticalCarousel')yes=/^Version 0[1-3]$/i.test(n)&&/Others\/Comps\/Version/i.test(f);
  else if(kind==='cinematicCut')yes=/(?:^|\/)01\. Transitions(?:\/|$)/i.test(f);
  else if(kind==='flashFrame')yes=/^Final Scene \d+$/i.test(n)&&/Final Scenes/i.test(f);
  else if(kind==='glowLine')yes=/^Transition \d+$/i.test(n)&&/Edit comp/i.test(f);
  else if(kind==='grunge')yes=/^.+ \d+$/i.test(n)&&/\bRender\b/i.test(f);
  else if(kind==='matchIntro')yes=/^INTRO$/i.test(n);
  else if(kind==='matchReveal')yes=/^Match Cut_\d+$/i.test(n)&&/Edit Comp\/(Editable Cut|Square Version|Vertical Version)$/i.test(f);
  else if(kind==='comicOpener'||kind==='rolling')yes=/^Scene \d+$/i.test(n)&&/To Edit\/Scene \d+$/i.test(f);
  else if(kind==='dynamicOpener')yes=/^RENDER$/i.test(n)&&/FINAL COMP$/i.test(f);
  else if(kind==='speedRamp')yes=/^Comp \d+ \/ Placeholder \d+$/i.test(n)&&/All Scene$/i.test(f);
  else if(kind==='interactive')yes=/^Scene \d+$/i.test(n)&&/Final comp$/i.test(f);
  else if(kind==='lowerThirds')yes=/^Cinematic Lower Third \d+$/i.test(n);
  else if(kind==='cinematic')yes=/^title_0*[1-3]$/i.test(n);
  else if(kind==='intro')yes=/^Cinematic Title \d+$/i.test(n);
  else if(kind==='textSwap')yes=/^Text Swap Transitions \d+$/i.test(n)&&/Final Comps$/i.test(f);
  else if(kind==='vintage')yes=/^Title_\d+$/i.test(n)&&/Title Comp$/i.test(f);
  else if(kind==='chat')yes=/^CHAT - \d+$/i.test(n)&&/Main Comp$/i.test(f);
  else if(kind==='phone')yes=/^Notif \d+$/i.test(n)&&/TEMPLATES\/\d+$/i.test(f);
  else yes=!r.usedBy&&!/(?:^|\W)(?:edit|controls?|placeholders?|assets?|audio|sfx|music|solids?|backgrounds?|previews?|logo)(?:\W|$)/i.test(n)&&!/(?:^|\/)(?:.*Technical.*|.*Assets.*|Media|Images?|Footage|Placeholders?)(?:\/|$)/i.test(f)&&r.duration>0;
  if(yes)out.push(r);
 }out.sort(function(a,b){return natural(a.folder,b.folder)||natural(a.name,b.name)||Number(a.id)-Number(b.id);});return out;}
 return {base:base,profile:profile,shortName:shortName,select:select,cover:cover,natural:natural};
});
