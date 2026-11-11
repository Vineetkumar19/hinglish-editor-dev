// Caption 2 keeps the measured row roles and motion clock shared with export.
(() => {
  const config=project.caption_two_profile;if(!config)return;
  const normalize=text=>String(text).toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]/gu,'');
  function originalPlan(words){
    const key=words.map(normalize).join(' ');let known=[...config.recipes,...config.demo_phrases].find(r=>r.text.split(/\s+/).map(normalize).join(' ')===key);
    if(storylensTemplateRebound(words))known=null;
    if(known)return known;
    if(!words.length)return {rows:[],motion:'out'};
    if(config.reference_grouping)return storylensTemplatePattern(words,config.recipes);
    const stops=new Set(['the','a','an','and','to','of','in','at','on','is','it','with','you','we','hai','ka','ki','ke','ko','se','aur']);
    let hero=0,score=-Infinity;
    words.forEach((w,i)=>{const s=[...normalize(w)].length-(stops.has(normalize(w))?100:0);if(s>score){score=s;hero=i}});
    const rows=[];
    if(hero)rows.push({words:words.slice(0,hero).map((_,i)=>i),role:'support',align:'top_left'});
    rows.push({words:[hero],role:'main'});
    if(hero+1<words.length)rows.push({words:words.slice(hero+1).map((_,i)=>i+hero+1),role:'support',align:'bottom'});
    return {rows,motion:'out'};
  }
  function planFor(words){
    if(config.reference_style){
      const plan=originalPlan(words);if(!words.length)return {...plan,rows:[],strike:false,record:false,plane:false};
      const stops=new Set(config.keyword_stop_words),eligible=words.map((_,i)=>i).filter(i=>normalize(words[i])&&!stops.has(normalize(words[i])));
      const original=plan.rows.find(r=>r.role==='main')||{};
      let rows=plan.rows.map(r=>({...r,words:[...r.words],green:(r.green||[]).filter(i=>eligible.includes(i))}));
      if(!eligible.length)rows=[{words:words.map((_,i)=>i),role:'support',align:'center'}];
      else if(!(original.words||[]).some(i=>eligible.includes(i))){
        const anchors=original.words?.length?original.words:[Math.floor(words.length/2)],distance=i=>Math.min(...anchors.map(j=>Math.abs(i-j)));
        const hero=eligible.reduce((a,b)=>distance(b)<distance(a)||(distance(b)===distance(a)&&b>a)?b:a);
        const pivot=Math.max(0,rows.findIndex(r=>r.role==='main')),before=rows.slice(0,pivot).filter(r=>r.role!=='main'),after=rows.slice(pivot+1).filter(r=>r.role!=='main');
        function rebindSupport(ids,prototypes,align){
          if(!ids.length)return [];
          if(!prototypes.length)prototypes=[{role:'support',align,words:[0]}];
          const weights=prototypes.map(r=>Math.max(1,r.words.length)),total=weights.reduce((s,w)=>s+w,0),assigned=prototypes.map(()=>[]);
          ids.forEach((i,k)=>{const target=(k+.5)*total/ids.length;let edge=0;for(let j=0;j<weights.length;j++){edge+=weights[j];if(target<edge){assigned[j].push(i);break}}});
          return prototypes.flatMap((row,j)=>assigned[j].length?[{...row,words:assigned[j],green:(row.green||[]).filter(i=>assigned[j].includes(i)&&eligible.includes(i))}]:[]);
        }
        rows=[];
        rows.push(...rebindSupport(words.slice(0,hero).map((_,i)=>i),before,'top_left'));
        rows.push({...original,role:'main',words:[hero],green:[]});
        rows.push(...rebindSupport(words.slice(hero+1).map((_,i)=>i+hero+1),after,'bottom'));
      }
      for(const row of rows)if(row.role==='card'){row.role='support';row.align='bottom'}
      return {...plan,rows,centered:true,reference_layout:false,balanced_reference:true,strike:false,record:false,plane:false};
    }
    if(config.centered_rows){
      const plan=originalPlan(words);if(!words.length)return plan;
      const stops=new Set(config.keyword_stop_words),eligible=words.map((_,i)=>i).filter(i=>normalize(words[i])&&!stops.has(normalize(words[i])));
      const preferred=plan.rows.filter(r=>r.role==='main').flatMap(r=>r.words).filter(i=>eligible.includes(i));
      const choices=preferred.length?preferred:eligible;
      const hero=choices.length?choices.reduce((a,b)=>[...normalize(words[b])].length>[...normalize(words[a])].length?b:a):null;
      const rows=[];
      if(hero===null)rows.push({words:words.map((_,i)=>i),role:'support',align:'center'});
      else{
        if(hero)rows.push({words:words.slice(0,hero).map((_,i)=>i),role:'support',align:'center'});
        rows.push({words:[hero],role:'main',align:'center'});
        if(hero+1<words.length)rows.push({words:words.slice(hero+1).map((_,i)=>hero+1+i),role:'support',align:'center'});
      }
      return {...plan,rows,centered:true,reference_layout:false,strike:false,record:false,plane:false,main_size:config.main_size,support_size:config.support_size,tracking:config.tracking};
    }
    if(config.reference_grouping)return originalPlan(words);
    const plan=originalPlan(words);if(!words.length)return plan;
    const original=plan.rows.find(r=>r.role==='main'),stops=new Set(['the','a','an','and','to','of','in','at','on','is','it','with','you','we','hai','ka','ki','ke','ko','se','aur']);
    const eligible=words.map((_,i)=>i).filter(i=>words.length<3||i>=2);
    let hero=eligible[0],score=-Infinity;
    eligible.forEach(i=>{const s=[...normalize(words[i])].length-(stops.has(normalize(words[i]))?100:0);if(s>score){score=s;hero=i}});
    if(original.words.length===1&&eligible.includes(original.words[0]))hero=original.words[0];
    const header=plan.rows.find(r=>r.role==='support'&&r.align!=='bottom')||{},footer=plan.rows.find(r=>r.align==='bottom')||{},rows=[];
    if(hero)rows.push({...header,words:words.slice(0,hero).map((_,i)=>i),role:'support',align:'top_left'});
    rows.push({...original,words:[hero]});
    if(hero+1<words.length)rows.push({...footer,words:words.slice(hero+1).map((_,i)=>i+hero+1),role:'support',align:'bottom'});
    return {...plan,rows};
  }
  function pageRanges(words){
    if(config.reference_style){
      const limit=Math.max(1,Math.min(5,config.max_words_per_frame??5)),count=Math.ceil(words.length/limit);if(!count)return [];
      const size=Math.floor(words.length/count),extra=words.length%count,result=[];let start=0;
      for(let i=0;i<count;i++){const end=start+size+(i<extra?1:0);result.push([start,end]);start=end}
      return result;
    }
    if(config.reference_grouping&&words.length<=7)return [[0,words.length]];
    if(config.reference_grouping)return words.flatMap((_,a)=>a%7===0?[[a,Math.min(a+7,words.length)]]:[]);
    const result=[];let start=0;
    while(start<words.length){
      const remaining=words.slice(start),main=planFor(remaining).rows.find(r=>r.role==='main'),stop=main.words.at(-1)+1,longMain=main.words.some(i=>[...normalize(remaining[i])].length>8);
      let count=Math.min(7,remaining.length);
      if((longMain||remaining.length>7)&&stop<=7)count=stop;
      while(true){
        const candidate=remaining.slice(0,count),hero=planFor(candidate).rows.find(r=>r.role==='main'),end=hero.words.at(-1)+1;
        if(hero.words.some(i=>[...normalize(candidate[i])].length>8)&&end<count)count=end;else break;
      }
      result.push([start,start+count]);start+=count;
    }
    return result;
  }
  function interpolate(keys,seconds,column=1){
    if(seconds<=keys[0][0])return keys[0][column];
    for(let i=1;i<keys.length;i++){const a=keys[i-1],b=keys[i];if(seconds<=b[0]){const p=(seconds-a[0])/(b[0]-a[0]);return a[column]+(b[column]-a[column])*p}}
    return keys.at(-1)[column];
  }
  function motionState(elapsed,main=false,slide=false){
    const m=config.motion,p=Math.max(0,Math.min(1,elapsed/m.text_seconds)),eased=1-(1-p)**3,fade=Math.max(0,Math.min(1,elapsed/m.fade_seconds));
    return [fade*fade*(3-2*fade),0,smoothTrack(m.word_y,elapsed),m.blur*(1-eased)];
  }
  function smoothTrack(keys,seconds){
    if(seconds<=keys[0][0])return keys[0][1];
    for(let i=1;i<keys.length;i++){const a=keys[i-1],b=keys[i];if(seconds<=b[0]){let p=(seconds-a[0])/(b[0]-a[0]);p=p*p*p*(p*(p*6-15)+10);return a[1]+(b[1]-a[1])*p}}
    return keys.at(-1)[1];
  }
  function wordScale(elapsed){return smoothTrack(config.motion.word_scale,elapsed)}
  function groupScale(plan,elapsed){if(plan.camera_keys?.length)return interpolate(plan.camera_keys,elapsed);return ['out','in'].includes(plan.motion)?interpolate(config.motion['scale_'+plan.motion],elapsed):1}
  function footerBaseline(baseline,mainExtents,footerExtents,gap=config.line_gap){return baseline+mainExtents[1]-footerExtents[0]+gap}
  const canvas=document.createElement('canvas');canvas.width=720;
  canvas.style.cssText='display:block;width:100%;height:auto;margin:0';canvas.setAttribute('role','img');
  const pen=canvas.getContext('2d'),measure=document.createElement('canvas').getContext('2d'),baseDraw=draw;
  let assetKey='';const assets=new Map();
  function paint(q,index,now){
    const W=canvas.width,unit=Math.min(W,W*stage.clientHeight/Math.max(1,stage.clientWidth)*.75),H=Math.round(unit*1.25);let ratio=unit/720;
    if(canvas.height!==H)canvas.height=H;
    pen.clearRect(0,0,W,H);
    const words=wordsAt(index),range=pageRanges(words).find(([a,b])=>(a?q.words[a].start:q.start)<=now&&now<(b<words.length?q.words[b].start:q.end));
    if(!range)return;
    const [a,b]=range,original=planFor(words.slice(a,b)),plan={...original,rows:original.rows.map(r=>({...r,words:r.words.map(i=>i+a),green:(r.green||[]).map(i=>i+a)}))},colors=wordColors[index]||[];

    let baseline=H/2+(plan.main_offset||0)*ratio;
    const chosen=$('#font').value,family=chosen==='template'?'"Inter Caption 1"':fonts[chosen].css,lightFamily=chosen==='template'?'"Inter Caption 2"':fonts[chosen].css;
    const weight=chosen==='template'||/(bd|uib|b)\.ttf$/i.test(fonts[chosen]?.file||'')?'700':'400';
    const key=JSON.stringify([index,W,H,words,colors,chosen]);if(key!==assetKey){assets.clear();assetKey=key}
    const mainRow=plan.rows.find(r=>r.role==='main'),mainOnset=mainRow&&plan.camera_anchor==='main'?Math.min(...mainRow.words.map(i=>q.words[i].start)):q.words[a].start,elapsed=now-mainOnset;
    let scale=groupScale(plan,elapsed);const ax=W/2,ay=plan.centered?H/2:baseline-32*ratio;
    pen.save();
    const shown=i=>q.words[i].start<=now&&(visibility!=='styled_spoken'||now<q.words[i].end);
    function makeRuns(row,size,card=false){
      size=Math.max(2,Math.round(size*ratio));
      const css=`${card&&chosen==='template'?'300':row.regular&&chosen==='template'?'400':weight} ${size}px ${card||row.regular?lightFamily:family}`,tracking=card?-.045:(row.tracking??(row.role==='main'?(plan.tracking??config.tracking):config.support_tracking));
      measure.font=css;let cursor=0;const runs=[];
      row.words.forEach(i=>{
        let text=words[i];if(!plan.reference_layout&&row.role==='main'&&i===row.words[0]&&text)text=text[0].toUpperCase()+text.slice(1);
        let left=Infinity,right=-Infinity,top=0,bottom=0;
        [...text].forEach((c,j)=>{const p=measure.measureText(text.slice(0,j)).width+j*size*tracking,m=measure.measureText(c);left=Math.min(left,p-m.actualBoundingBoxLeft);right=Math.max(right,p+m.actualBoundingBoxRight);top=Math.min(top,-m.actualBoundingBoxAscent);bottom=Math.max(bottom,m.actualBoundingBoxDescent)});
        runs.push({i,text,css,size,tracking,x:cursor,left,right,top,bottom,enterY:row.enter_y});
        cursor+=measure.measureText(text).width+Math.max(0,text.length-1)*size*tracking+size*(row.role==='main'?.17:.21);
      });
      const left=Math.min(0,...runs.map(r=>r.x+r.left)),right=Math.max(0,...runs.map(r=>r.x+r.right));
      return {runs,width:right-left,ink:left,extents:[Math.min(0,...runs.map(r=>r.top)),Math.max(0,...runs.map(r=>r.bottom))]};
    }
    if(plan.adapted&&!plan.centered){const widest=Math.max(1,...plan.rows.map(row=>makeRuns(row,row.size??(row.role==='main'?(plan.main_size??config.main_size):(plan.support_size??config.support_size))).width));ratio*=Math.min(1,unit*.88/Math.max(1,...config.motion.scale_out.map(k=>k[1]))/widest);baseline=H/2+(plan.main_offset||0)*ratio}
    let mainSize=plan.main_size??config.main_size,mainLine=mainRow?makeRuns(mainRow,mainRow.size??mainSize):{runs:[],width:0,ink:0};
    const peak=Math.max(1,...config.motion.scale_out.map(k=>k[1])),safeWidth=plan.balanced_reference?unit*(config.settled_width_fraction??.88):plan.reference_layout?unit*.98:unit*.88/peak;
    if(mainRow&&mainLine.width>safeWidth){mainSize=(mainRow.size??mainSize)*safeWidth/mainLine.width;mainLine=makeRuns(mainRow,mainSize)}
    const mainLeft=(W-mainLine.width)/2;
    const centeredLines=[];
    if(plan.balanced_reference){
      for(const row of plan.rows){
        let size=row.size??(row.role==='main'?(plan.main_size??config.main_size):(plan.support_size??config.support_size)),line=makeRuns(row,size);
        if(line.width>safeWidth){size*=safeWidth/line.width;line=makeRuns(row,size)}
        centeredLines.push({row,size,line,x:-line.width/2-line.ink,y:0});
      }
      const main=centeredLines.find(e=>e.row.role==='main'),upper=centeredLines.filter(e=>e!==main&&e.row.align!=='bottom'),lower=centeredLines.filter(e=>e.row.align==='bottom');
      const travel=Math.max(...config.motion.word_y.map(k=>k[1]))-Math.min(...config.motion.word_y.map(k=>k[1])),gap=(config.visible_ink_gap??((config.line_gap+travel+2)*(config.centered_gap_scale??.3)))*ratio;
      if(main){
        if(upper.length===2){
          const [a,b]=upper,headerGap=Math.max(gap,(config.split_header_gap??20)*ratio),fit=Math.min(1,Math.max(1,safeWidth-headerGap)/Math.max(1,a.line.width+b.line.width));
          if(fit<1)for(const e of upper){e.size*=fit;e.line=makeRuns(e.row,e.size)}
          const span=Math.min(safeWidth,Math.max(main.line.width*(1-(plan.header_fraction??.16)-(plan.right_fraction??0)),a.line.width+b.line.width+headerGap));
          const room=Math.max(0,(safeWidth-span)/2),center=Math.max(-room,Math.min(room,((plan.header_fraction??.16)-(plan.right_fraction??0))*main.line.width/2));
          a.x=center-span/2-a.line.ink;b.x=center+span/2-b.line.width-b.line.ink;
        }else for(const e of upper){
          const align=e.row.align,proposed=align==='center'?0:align==='top_right'?(main.line.width-e.line.width)/2-main.line.width*(plan.right_fraction??0):(e.line.width-main.line.width)/2+main.line.width*(plan.header_fraction??.16);
          const room=Math.max(0,(safeWidth-e.line.width)/2),center=Math.max(-room,Math.min(room,proposed));e.x=center-e.line.width/2-e.line.ink;
        }
        if(upper.length){const y=main.line.extents[0]-gap-Math.max(...upper.map(e=>e.line.extents[1]));for(const e of upper)e.y=y}
        let bottom=main.line.extents[1];
        for(const e of lower){
          const proposed=(main.line.width-e.line.width)/2+(e.row.dx??0)*ratio,room=Math.max(0,(safeWidth-e.line.width)/2),center=Math.max(-room,Math.min(room,proposed));
          e.x=center-e.line.width/2-e.line.ink;e.y=bottom+gap-e.line.extents[0];bottom=e.y+e.line.extents[1];
        }
      }
      const left=Math.min(0,...centeredLines.map(e=>e.x+e.line.ink)),right=Math.max(0,...centeredLines.map(e=>e.x+e.line.ink+e.line.width));
      const top=Math.min(0,...centeredLines.map(e=>e.y+e.line.extents[0])),bottom=Math.max(0,...centeredLines.map(e=>e.y+e.line.extents[1]));
      for(const e of centeredLines){e.row._x=e.x+W/2-(left+right)/2;e.y+=H/2-(top+bottom)/2}
    }else if(plan.centered){
      for(const row of plan.rows){
        let size=row.role==='main'?mainSize:config.support_size,line=makeRuns(row,size);
        if(line.width>safeWidth){size*=safeWidth/line.width;line=makeRuns(row,size)}
        centeredLines.push({row,line});
      }
      const travel=Math.max(...config.motion.word_y.map(k=>k[1]))-Math.min(...config.motion.word_y.map(k=>k[1]));
      const gap=(config.line_gap+travel+2)*(config.centered_gap_scale??.3)*ratio;
      const blockHeight=centeredLines.reduce((s,{line})=>s+line.extents[1]-line.extents[0],0)+gap*Math.max(0,centeredLines.length-1);
      let top=H/2-blockHeight/2;
      for(const entry of centeredLines){entry.y=top-entry.line.extents[0];top+=entry.line.extents[1]-entry.line.extents[0]+gap}
    }
    if(plan.balanced_reference&&centeredLines.length){
      const left=Math.min(...centeredLines.flatMap(e=>e.line.runs.map(r=>e.row._x+r.x+r.left))),right=Math.max(...centeredLines.flatMap(e=>e.line.runs.map(r=>e.row._x+r.x+r.right)));
      scale=Math.min(scale,unit*(config.camera_width_fraction??.94)/Math.max(1,right-left));
    }
    pen.translate(ax,ay);pen.scale(scale,scale);pen.translate(-ax,-ay);
    function paintWord(run,x,y,color,main=false,card=false){
      if(!shown(run.i))return;
      let [alpha,dx,dy,blur]=motionState(now-q.words[run.i].start,main,plan.motion==='out');
      if(run.enterY!==undefined)dy=smoothTrack([[0,run.enterY],[config.motion.text_seconds,0]],now-q.words[run.i].start);
      const colorValue=colors[run.i]||color;
      const token=JSON.stringify([run.i,run.css,run.text,x,y,colorValue,card]);
      let glyph=assets.get(token);
      if(!glyph){
        glyph=document.createElement('canvas');glyph.width=W;glyph.height=H;const gp=glyph.getContext('2d');
        gp.font=run.css;gp.textBaseline='alphabetic';gp.fillStyle=colorValue;
        const letters=()=>[...run.text].forEach((c,j)=>gp.fillText(c,x+gp.measureText(run.text.slice(0,j)).width+j*run.size*run.tracking,y));
        const appearance=config.appearance;
        if(appearance&&!card){
          const u=run.size/104;
          gp.save();gp.fillStyle='#000000';gp.globalAlpha=appearance.shadow_opacity;gp.filter=`blur(${appearance.shadow_blur*u}px)`;gp.translate(0,appearance.shadow_y*u);letters();gp.restore();
          for(const [radius,alpha] of appearance[main||color===config.green?'lime_glow':'white_glow']){
            gp.save();gp.filter=`blur(${radius*u}px)`;gp.globalAlpha=alpha;letters();gp.restore();
          }
        }else if(!card&&(main||color===config.green)){gp.shadowColor=colorValue+'40';gp.shadowBlur=12*ratio}
        letters();
        if(!card)assets.set(token,glyph);
      }
      pen.save();pen.globalAlpha=alpha;pen.filter=blur>.12?`blur(${blur*ratio}px)`:'none';
      pen.translate(dx*ratio,dy*ratio);
      const wordZoom=wordScale(now-q.words[run.i].start),wx=x+(run.left+run.right)/2,wy=y+(run.top+run.bottom)/2;
      pen.translate(wx,wy);pen.scale(wordZoom,wordZoom);pen.translate(-wx,-wy);
      pen.drawImage(glyph,0,0);pen.restore();
    }
    let cardIndex=0;
    const rowBounds=[];
    if(plan.centered){
      for(const {row,line,y} of centeredLines){
        const visible=line.runs.filter(r=>shown(r.i)&&motionState(now-q.words[r.i].start)[0]>.01);if(!visible.length)continue;
        // Reserve the complete row so each reveal keeps existing words fixed.
        const left=Math.min(...line.runs.map(r=>r.x+r.left)),right=Math.max(...line.runs.map(r=>r.x+r.right)),x=row._x??(W/2-(left+right)/2);
        rowBounds.push({role:row.role,left:x+left,right:x+right,top:y+line.extents[0],bottom:y+line.extents[1],words:row.words});
        visible.forEach(r=>{const content=normalize(words[r.i])&&!config.keyword_stop_words.includes(normalize(words[r.i])),highlight=content&&(row.role==='main'||(row.green||[]).includes(r.i));paintWord(r,x+r.x,y,highlight?config.green:config.white,highlight)});
      }
    }
    for(const row of plan.rows){
      if(plan.centered)continue;
      if(row.role==='card'){
        const age=now-q.words[row.words[0]].start;
        if(age<0){cardIndex++;continue}
        const bw=448*ratio,bh=82*ratio,x=(W-bw)/2,center=baseline+(-7+cardIndex*116+interpolate(config.motion.card_y,age))*ratio;
        pen.save();pen.globalAlpha=Math.max(0,Math.min(1,age/.15));
        pen.beginPath();pen.roundRect(x,center-bh/2,bw,bh,bh*.3);pen.clip();
        pen.fillStyle='#10060bf2';pen.fillRect(x,center-bh/2,bw,bh);
        const glow=pen.createRadialGradient(x+bw*.48,center+bh*.55,0,x+bw*.48,center+bh*.55,bw*.47);
        glow.addColorStop(0,'#780014bc');glow.addColorStop(1,'#78001400');pen.fillStyle=glow;pen.fillRect(x,center-bh/2,bw,bh);pen.restore();
        pen.beginPath();pen.roundRect(x,center-bh/2,bw,bh,bh*.3);pen.lineWidth=ratio;pen.strokeStyle='#79696396';pen.stroke();
        const cx=x+50*ratio,cy=center;
        pen.save();
        if(cardIndex===0){
          pen.beginPath();pen.moveTo(cx,cy-17*ratio);pen.lineTo(cx-17*ratio,cy+14*ratio);pen.lineTo(cx+17*ratio,cy+14*ratio);pen.closePath();pen.fillStyle=config.red;pen.fill();
          pen.strokeStyle='#230000';pen.lineWidth=3*ratio;pen.beginPath();pen.moveTo(cx,cy-7*ratio);pen.lineTo(cx,cy+3*ratio);pen.stroke();pen.fillStyle='#230000';pen.fillRect(cx-ratio,cy+8*ratio,2*ratio,2*ratio);
        }else{
          pen.font=`${36*ratio}px "Segoe UI Emoji"`;pen.textAlign='center';pen.textBaseline='middle';pen.fillStyle='#FAECCD';pen.fillText('💸',cx,cy);
        }pen.restore();
        const line=makeRuns(row,cardIndex===0?36:30,true),start=Math.max(x+90*ratio,W/2-line.width/2);
        line.runs.forEach(r=>paintWord(r,start+r.x-line.ink,center+12*ratio,config.white,false,true));cardIndex++;continue;
      }
      const main=row.role==='main',align=row.align??'main';
      let size=row.size??(main?mainSize:plan.support_size??config.support_size),line=main?mainLine:makeRuns(row,size);
      const available=mainLeft+mainLine.width-(W-safeWidth)/2;
      if(!main&&line.width>available){size*=available/line.width;line=makeRuns(row,size)}
      let x,y;
      if(main){x=mainLeft-line.ink;y=baseline}
      else if(align==='top_left'){x=plan.reference_layout?mainLeft+mainLine.width*(plan.header_fraction??.16)-line.ink:mainLeft-line.ink;y=plan.reference_layout?baseline-(plan.top_lift??70)*ratio:baseline+mainLine.extents[0]-line.extents[1]-config.line_gap*ratio}
      else if(align==='top_right'){x=mainLeft+mainLine.width-line.width-line.ink-mainLine.width*(plan.right_fraction??0);y=plan.reference_layout?baseline-(plan.top_lift??70)*ratio:baseline+mainLine.extents[0]-line.extents[1]-config.line_gap*ratio}
      else if(align==='bottom'){x=mainLeft+mainLine.width-line.width-line.ink;y=plan.reference_layout?baseline+size*.85*ratio:footerBaseline(baseline,mainLine.extents,line.extents,config.line_gap*ratio)}
      else{x=mainLeft+mainLine.width*(plan.header_fraction??.12)-line.ink;y=baseline-(plan.top_lift??(size>=75?78:size>=65?85:size>=58?66:70))*ratio}
      if(!(main&&plan.reference_layout))x=Math.max(W*.055,Math.min(x,W*.945-line.width));
      x+=(row.dx??0)*ratio;
      if(plan.adapted){const margin=(W-unit*.88/peak)/2;x=Math.max(margin-line.ink,Math.min(x,W-margin-line.width-line.ink))}
      line.runs.forEach(r=>paintWord(r,x+r.x,y,main||(row.green||[]).includes(r.i)?config.green:config.white,main));
    }
    pen.restore();
    const cursor=config.cursor,event=cursor?.times.find(start=>start<=now&&now<start+cursor.duration);
    if(!config.text_only&&(event!==undefined||(!cursor&&plan.plane&&elapsed>=.12))){
      const t=event!==undefined?now-event:elapsed-.12,cp=cursor?config.recipes[1]:plan;
      const anchor=cursor?H/2+(config.position-(plan.position??config.position))*W*stage.clientHeight/stage.clientWidth:baseline;
      const keys=config.motion.plane,cx=(interpolate(keys,t,1)+(cp.plane_dx??0))*ratio+(W-unit)/2,cy=anchor+(interpolate(keys,t,2)+(cp.plane_dy??0))*ratio,angle=(interpolate(keys,t,3)+(cp.plane_angle??0))*Math.PI/180;
      let size=(cp.plane_size??46)*ratio;const click=cursor?(t-cursor.click_at)/cursor.click_seconds:-1;
      if(click>=0&&click<=1)size*=1-.12*Math.sin(Math.PI*click);
      const points=[[-.55,.1],[.55,-.5],[.15,.65],[-.05,.15],[-.55,.1],[-.05,.15],[.55,-.5]].map(([a,b])=>[cx+(a*Math.cos(angle)-b*Math.sin(angle))*size,cy+(a*Math.sin(angle)+b*Math.cos(angle))*size]);
      pen.save();if(cursor)pen.globalAlpha=Math.max(0,Math.min(1,(cursor.duration-t)/(cursor.duration-cursor.fade_at)));
      pen.strokeStyle=config.green;pen.shadowColor=config.green;pen.shadowBlur=8*ratio;pen.lineWidth=4*ratio;pen.lineJoin='round';pen.beginPath();
      points.forEach(([x,y],i)=>i?pen.lineTo(x,y):pen.moveTo(x,y));pen.stroke();
      if(cursor&&t>=cursor.click_at&&t<cursor.click_at+.38){const pulse=(t-cursor.click_at)/.38;pen.shadowBlur=4*ratio;pen.globalAlpha*=(1-pulse)*.7;pen.lineWidth=2*ratio;pen.beginPath();pen.arc(points[1][0],points[1][1],(5+24*pulse)*ratio,0,Math.PI*2);pen.stroke()}
      pen.restore();
    }
    pen.save();pen.translate(ax,ay);pen.scale(scale,scale);pen.translate(-ax,-ay);
    if(!config.text_only&&plan.strike&&elapsed>.17){const p=Math.min(1,(elapsed-.17)/.55),x=mainLeft-10*ratio,y=baseline-90*ratio;
      if(config.appearance){const dx=mainLine.width+20*ratio,dy=mainSize*.8*ratio,length=Math.hypot(dx,dy),left=[],right=[];for(let k=0;k<=60;k++){const t=p*k/60,xx=x+dx*t,yy=y+dy*t,half=7*ratio*Math.sin(Math.PI*t)**.65;left.push([xx-dy/length*half,yy+dx/length*half]);right.push([xx+dy/length*half,yy-dx/length*half])}pen.beginPath();[...left,...right.reverse()].forEach(([xx,yy],i)=>i?pen.lineTo(xx,yy):pen.moveTo(xx,yy));pen.closePath();pen.fillStyle=config.red;pen.fill()}
      else{pen.beginPath();pen.moveTo(x,y);pen.lineTo(mainLeft+mainLine.width*p,y+76*ratio*p);pen.strokeStyle=config.red;pen.lineWidth=6*ratio;pen.stroke()}}
    if(!config.text_only&&plan.record&&elapsed>.5){const x=mainLeft+mainLine.width+16*ratio,y=baseline-67*ratio;pen.beginPath();pen.arc(x,y,5*ratio,0,Math.PI*2);pen.fillStyle=config.red;pen.fill()}
    pen.restore();
    const visible=words.map((_,i)=>i).filter(i=>i>=a&&i<b&&shown(i));canvas.setAttribute('aria-label',visible.map(i=>words[i]).join(' '));canvas.textContent=visible.map(i=>words[i]).join(' ');
    canvas.dataset.style='caption_2';canvas.dataset.mode=plan.motion;canvas.dataset.wordIndices=visible.join(',');
    canvas.dataset.rowBounds=JSON.stringify(rowBounds);
  }
  draw=function(){
    baseDraw();if(currentStyle!=='caption_2'||visibility==='spoken')return;
    const now=video.currentTime,index=cues.findIndex(q=>q.start<=now&&now<q.end);
    if(index<0){caption.replaceChildren();return}
    caption.replaceChildren(canvas);caption.className='caption-two-reference';
    Object.assign(caption.style,{left:'0',right:'0',top:templates.caption_2.default_position*100+'%',width:'100%',maxWidth:'none',transform:'translateY(-50%)',filter:'none',opacity:'1',background:'transparent',visibility:'visible',padding:'0',textShadow:'none'});
    paint(cues[index],index,now);updateSelection();
  };
  video.addEventListener('seeked',draw);video.addEventListener('pause',draw);window.addEventListener('resize',draw);
  Promise.all([document.fonts.load('700 114px "Inter Caption 1"'),document.fonts.load('300 36px "Inter Caption 2"')]).then(()=>{assets.clear();assetKey='';draw()});
})();
