(()=>{
  if(window.__storylensYoutubeInstalled)return;window.__storylensYoutubeInstalled=true;
  let prepared=null;
  const visible=e=>!!e&&!!e.getBoundingClientRect().width&&!!e.getBoundingClientRect().height;
  const all=(selector,root=document)=>Array.from(root.querySelectorAll(selector)).filter(visible);
  const text=e=>(e?.innerText||'').trim();
  const button=(name,root=document)=>{let found=all('button,[role="button"]',root).filter(b=>text(b)===name||b.getAttribute('aria-label')===name);found=found.filter(b=>!found.some(child=>child!==b&&b.contains(child)));if(found.length!==1)throw Error('Studio '+name+' control is ambiguous or unavailable.');return found[0];};
  const wait=async(test,label='requested control')=>{for(let i=0;i<40;i++){const value=test();if(value)return value;await new Promise(r=>setTimeout(r,250));}throw Error('Studio did not finish loading '+label+'.');};
  function marked(element,job,kind){
    const token=job.video_id+'-'+kind;element.setAttribute('data-storylens-click',token);
    return {control:{selector:`[data-storylens-click="${token}"]`}};
  }
  function channel(){
    if(/Verify that it.s you|sign in to continue/i.test(document.body.innerText))throw Error('Complete the Studio identity verification yourself.');
    const home=all('a#home-button')[0];
    const id=home&&new URL(home.href).pathname.match(/^\/channel\/(UC[\w-]{22})$/)?.[1];
    if(!id||!location.pathname.startsWith('/channel/'+id))throw Error('Studio channel is still loading.');
    return id;
  }
  function account(job){
    const home=all('a#home-button')[0];
    if(!home)throw Error('Studio channel is still loading.');
    const base=`/channel/${job.channel_id}`;
    const details=job.action==='youtube_metadata'&&location.pathname===`/video/${job.video_id}/edit`;
    if(!(details||location.pathname===base||location.pathname.startsWith(base+'/'))||new URL(home.href).pathname!==base)throw Error('Studio is showing a different channel; no changes were made.');
    const body=document.body.innerText;
    if(/Verify that it.s you|sign in to continue/i.test(body))throw Error('Complete the Studio identity verification yourself.');
  }
  function row(job){const link=all('a').find(a=>new URL(a.href,location.origin).pathname===`/video/${job.video_id}/edit`);return link?.closest('ytcp-video-row[role="row"]');}
  function root(){const boxes=Array.from(document.querySelectorAll('ytcp-video-visibility-edit-popup')).map(e=>e.querySelector('#dialog')).filter(e=>visible(e)&&e.querySelector('#first-container')&&e.querySelector('#second-container'));if(boxes.length!==1)throw Error('Studio privacy dialog is unavailable or ambiguous.');return boxes[0];}
  function dateTrigger(){const found=all('#datepicker-trigger',root());if(found.length!==1)throw Error('Studio date dropdown is unavailable or ambiguous.');return found[0];}
  function timeInput(){const found=all('input',root()).filter(e=>/^\d{1,2}:\d{2}(?:\s*[AP]M)?$/i.test(e.value.replace(/\s+/g,' ')));return found.length===1?found[0]:null;}
  function control(input,job,kind){const token=job.video_id+'-'+kind;input.setAttribute('data-storylens-input',token);return {control:{selector:`input[data-storylens-input="${token}"]`}};}
  function requested(job){const d=new Date(job.publish_at);const p=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(d).map(x=>[x.type,x.value]));return p;}
  function ready(job){
    account(job);const box=root(),p=requested(job);
    const date=dateTrigger();
    if(!date)throw Error('Studio release date is unavailable.');
    const actual=new Date(text(date));
    if(actual.getFullYear()!==Number(p.year)||actual.getMonth()+1!==Number(p.month)||actual.getDate()!==Number(p.day))throw Error('Studio release date differs from the reviewed date.');
    const input=timeInput();
    const m=input?.value.replace(/\s+/g,' ').match(/^(\d{1,2}):(\d{2})(?:\s*([AP]M))?$/i);
    if(!m)throw Error('Studio release time is unavailable.');
    let hour=Number(m[1]);if(m[3])hour=hour%12+(m[3].toUpperCase()==='PM'?12:0);
    if(hour!==Number(p.hour)||Number(m[2])!==Number(p.minute))throw Error('Studio release time differs from the reviewed time.');
    const evidence=[box.innerText,...Array.from(box.querySelectorAll('[aria-label],[title],tp-yt-paper-tooltip')).map(e=>[e.getAttribute('aria-label'),e.getAttribute('title'),e.textContent].join(' '))].join(' ');
    if(!/GMT\+0?5:?30/.test(evidence))throw Error('Set the Studio time zone to India (GMT+0530); its offset could not be verified.');
    const submit=button('Schedule',box);if(submit.disabled||submit.getAttribute('aria-disabled')==='true')throw Error('Studio has not enabled scheduling.');
    return {ready:true,driver_version:'0.4.7'};
  }
  function publicChoice(){
    const choices=all('[role="radio"],tp-yt-paper-radio-button',root()).filter(e=>
      e.getAttribute('name')==='PUBLIC'||e.getAttribute('id')==='PUBLIC'||/^Public(?:\n|$)/.test(text(e)));
    const found=choices.filter(e=>!choices.some(child=>child!==e&&e.contains(child)));
    if(found.length!==1)throw Error('Studio Public visibility control is unavailable or ambiguous.');
    return found[0];
  }
  function publicReady(job){
    account(job);
    if(job.publish_now!==true||job.publish_at||root().getAttribute('data-storylens-video')!==job.video_id)
      throw Error('Immediate publication was not authorized for this exact video.');
    const choice=publicChoice();
    if(choice.getAttribute('aria-checked')!=='true'&&!choice.hasAttribute('checked'))throw Error('Studio has not selected Public visibility.');
    const box=root();let submits=all('button,[role="button"]',box).filter(e=>['Save','Publish'].includes(text(e)));
    submits=submits.filter(e=>!submits.some(child=>child!==e&&e.contains(child)));
    if(submits.length!==1||submits[0].disabled||submits[0].getAttribute('aria-disabled')==='true')
      throw Error('Studio has not enabled the publication control.');
    return submits[0];
  }
  function privateChoice(){
    const choices=all('[role="radio"],tp-yt-paper-radio-button',root()).filter(e=>
      e.getAttribute('name')==='PRIVATE'||e.getAttribute('id')==='PRIVATE'||/^Private(?:\n|$)/.test(text(e)));
    const found=choices.filter(e=>!choices.some(child=>child!==e&&e.contains(child)));
    if(found.length!==1)throw Error('Studio Private visibility control is unavailable or ambiguous.');
    return found[0];
  }
  function privateReady(job){
    account(job);
    if(job.action!=='youtube_private'||job.publish_at||job.publish_now||root().getAttribute('data-storylens-video')!==job.video_id)
      throw Error('Private-only cleanup was not authorized for this exact video.');
    const choice=privateChoice();
    if(choice.getAttribute('aria-checked')!=='true'&&!choice.hasAttribute('checked'))throw Error('Studio has not selected Private visibility.');
    const save=button('Save',root());
    if(save.disabled||save.getAttribute('aria-disabled')==='true')throw Error('Studio has not enabled private-only Save.');
    return save;
  }
  chrome.runtime.onMessage.addListener((message,sender,reply)=>{
    if(sender.id!==chrome.runtime.id||message.source!=='storylens-youtube')return;
    (async()=>{
      const {action,job}=message;
      if(!/^UC[\w-]{22}$/.test(job?.channel_id)||! /^[\w-]{11}$/.test(job?.video_id))throw Error('Invalid reviewed Studio task.');
      if(action==='channel')return {channel_id:channel()};
      if(['accountMenu','switchMenu','switchChannel'].includes(action)){
        channel();
        if(all('ytcp-video-visibility-edit-popup #dialog').length)throw Error('Close the current Studio visibility dialog before switching channels.');
        if(action==='accountMenu')return marked(button('Account'),job,'account');
        if(action==='switchMenu'){
          const link=await wait(()=>all('a,[role="link"]').find(e=>text(e)==='Switch account'),'the Switch account menu');
          return marked(link,job,'switch');
        }
        const wanted=(job.channel_name||'').trim().toLocaleLowerCase();
        if(!wanted)throw Error('The reviewed channel name is missing; no channel was selected.');
        const matches=await wait(()=>{const rows=all('[role="option"]').filter(e=>text(e).split('\n')[0].trim().toLocaleLowerCase()===wanted);return rows.length?rows:null},'the requested channel in the account switcher');
        const withHandle=matches.filter(e=>text(e).split('\n').some(line=>/^@[A-Za-z0-9._-]+$/.test(line.trim())));
        const choices=withHandle.length===1?[...withHandle,...matches.filter(e=>!withHandle.includes(e))]:matches;
        const choice=job.channel_choice||0;
        if(!Number.isInteger(choice)||choice<0||choice>=choices.length||choices.length>5)throw Error('The requested channel name is ambiguous in Studio. No channel was selected.');
        // Selection is tentative: the worker must confirm the exact channel ID
        // before it can open or change any video's visibility.
        return {...marked(choices[choice],job,'channel'),candidate_count:choices.length};
      }
      account(job);
      if(action==='editLink'){
        if(job.action!=='youtube_metadata')throw Error('No copy repair was requested.');
        const link=all('a',row(job)).filter(a=>new URL(a.href,location.origin).pathname===`/video/${job.video_id}/edit`)[0];
        if(!link)throw Error('The exact video details link is unavailable.');
        return marked(link,job,'details');
      }
      if(['copyInspect','copyField','copyReady','copyCommit'].includes(action)){
        if(job.action!=='youtube_metadata'||location.pathname!==`/video/${job.video_id}/edit`)throw Error('The exact video details page is not open.');
        const fields={title:all('#title-textarea [contenteditable="true"]'),description:all('#description-textarea [contenteditable="true"]')};
        if(Object.values(fields).some(v=>v.length!==1))throw Error('The video title and description fields are unavailable or ambiguous.');
        const matches=copy=>Object.keys(fields).every(k=>text(fields[k][0])===copy[k].trim());
        if(action==='copyInspect'){
          if(matches(job.metadata))return {already_matches:true};
          if(!matches(job.expected_metadata))throw Error('The video copy changed since review. No text was overwritten.');
          return {already_matches:false};
        }
        if(action==='copyField'){
          if(!['title','description'].includes(job.copy_field))throw Error('Unsupported copy field.');
          const field=fields[job.copy_field][0],token=job.video_id+'-'+job.copy_field;
          field.setAttribute('data-storylens-input',token);
          return {control:{selector:`[contenteditable="true"][data-storylens-input="${token}"]`}};
        }
        if(!matches(job.metadata))throw Error('The entered copy differs from the reviewed title or description.');
        const save=button('Save');if(save.disabled||save.getAttribute('aria-disabled')==='true')throw Error('Studio has not enabled Save for this copy.');
        const stamp=JSON.stringify([job.video_id,job.channel_id,job.metadata]);
        if(action==='copyReady'){prepared=stamp;return {ready:true}}
        if(prepared!==stamp)throw Error('This copy was not prepared for the exact video.');
        prepared=null;save.click();return {};
      }
      if(action==='reset'){
        let box;try{box=root()}catch(_){return {}}
        const owner=box.getAttribute('data-storylens-video');
        const marks=all('[data-storylens-click$="-visibility"]');
        const priorOwned=job.recover_before_submit&&marks.length===1&&marks[0].getAttribute('data-storylens-click')===job.video_id+'-visibility';
        if(owner!==job.video_id&&!(owner===null&&priorOwned))throw Error('An unverified Studio dialog is open. No changes were made.');
        button('Cancel',box).click();
        await wait(()=>{try{root();return false}catch(_){return true}},'the previous unsaved schedule to close');return {};
      }
      if(action==='inspect')return {ready:!!row(job),driver_version:'0.4.7'};
      if(action==='privateInspect'){
        if(job.action!=='youtube_private')throw Error('No private-only cleanup was requested.');
        return {already_private:all('[role="cell"]',row(job)).some(e=>text(e)==='Private')};
      }
      if(action==='open'){
        // The row/link can arrive before its asynchronous visibility cell.
        // Read the exact row until the actual control and label are ready.
        let observation={row_found:false};
        let target;
        try{target=await wait(()=>{
          account(job);const r=row(job);if(!r){observation={row_found:false};return null;}
          const cells=all('[role="cell"]',r);
          observation={row_found:true,visible_cells:cells.length,visibility_states:[],editable_controls:0};
          const controls=new Map();
          for(const cell of cells){
            const states=[...new Set(text(cell).split(/\n+/).map(s=>s.trim()).filter(s=>['Private','Scheduled','Public','Unlisted'].includes(s)))];
            observation.visibility_states.push(...states);
            if(states.length!==1)continue;
            const state=states[0];
            if(!['Private','Scheduled',...(job.action==='youtube_private'?['Public']:[])].includes(state))throw Error('The reviewed video is '+state+'. Its visibility was not changed.');
            const matches=all('.icon-text-edit-triangle-wrap.editable',cell);
            observation.editable_controls+=matches.length;
            if(matches.length===1)controls.set(matches[0],{element:matches[0],state});
          }
          if(controls.size>1)throw Error('The reviewed video visibility dropdown is ambiguous.');
          return controls.size===1?[...controls.values()][0]:null;
        },'the reviewed video’s visibility label and dropdown');}
        catch(error){
          if(String(error.message).startsWith('Studio did not finish loading'))
            throw Error(error.message+' Observed control state: '+JSON.stringify(observation));
          throw error;
        }
        if(target.state==='Scheduled'&&job.allow_reschedule!==true&&job.action!=='youtube_private')throw Error('This video is already scheduled. An explicit date change is required to replace its schedule.');
        const clickable=[target.element];
        // Studio's current row needs a real pointer activation. A synthetic
        // HTMLElement.click() may do nothing, despite the target being visible.
        const token=job.video_id+'-visibility';
        const arrows=all('ytcp-icon-button.edit-triangle-icon[role="button"]',clickable[0]);
        if(arrows.length>1)throw Error('The reviewed visibility dropdown arrow is ambiguous.');
        // Scheduled text opens an informational tooltip; its arrow opens the editor.
        for(const old of document.querySelectorAll(`[data-storylens-click="${token}"]`))old.removeAttribute('data-storylens-click');
        // Private rows expose a stable label while the arrow is hover-only.
        // Moving the pointer onto the wrapper can reveal the arrow and change
        // its geometry between measurement and activation. The private label
        // opens the editor directly; Scheduled retains its arrow-only path.
        const labels=all('.label-span',clickable[0]).filter(e=>text(e)==='Private');
        if(target.state==='Private'&&labels.length>1)throw Error('The reviewed Private label is ambiguous.');
        // A saved pre-submission recovery takes the dropdown path instead of
        // repeating a Private-label activation that may have opened no dialog.
        const recovery=job.recover_before_submit===true;
        (target.state==='Private'&&labels.length===1&&!recovery?labels[0]:(arrows[0]||clickable[0])).setAttribute('data-storylens-click',token);
        return {control:{selector:`[data-storylens-click="${token}"]`}};
      }
      if(action==='opened'){const box=await wait(()=>{try{return root()}catch(_){return null}},'the video visibility dialog');box.setAttribute('data-storylens-video',job.video_id);return {};}
      if(action==='private'){
        if(job.action!=='youtube_private'||job.publish_at||job.publish_now)throw Error('No private-only cleanup was requested.');
        let choice;try{choice=privateChoice()}catch(_){
          const expand=all('#first-container-expand-button',root())[0];
          if(!expand)throw Error('Studio Save or publish section is unavailable.');
          expand.click();choice=await wait(()=>{try{return privateChoice()}catch(_){return null}},'the Private visibility option');
        }
        return marked(choice,job,'private');
      }
      if(action==='privateReady'){
        await wait(()=>{try{privateReady(job);return true}catch(_){return false}},'Private visibility and its Save control');
        prepared=[job.video_id,job.channel_id,'private'].join('|');return {ready:true};
      }
      if(action==='commitPrivate'){
        if(prepared!==[job.video_id,job.channel_id,'private'].join('|'))throw Error('This exact private-only video was not prepared.');
        const save=privateReady(job);prepared=null;save.click();let stable=0;
        await wait(()=>{account(job);try{root();stable=0;return false}catch(_){}
          if(!all('[role="cell"]',row(job)).some(e=>text(e)==='Private')){stable=0;return false}
          return ++stable>=8;
        },'the private-only save to settle on this exact video');
        return {ui_commit_settled:true};
      }
      if(action==='public'){
        if(job.publish_now!==true||job.publish_at)throw Error('Public visibility requires an immediate publication request.');
        return marked(publicChoice(),job,'public');
      }
      if(action==='publicReady'){
        await wait(()=>{try{publicReady(job);return true}catch(_){return false}},'Public visibility and its Save control');
        prepared=[job.video_id,job.channel_id,'public'].join('|');return {ready:true};
      }
      if(action==='commitPublic'){
        if(prepared!==[job.video_id,job.channel_id,'public'].join('|'))throw Error('The exact public video was not prepared.');
        const submit=publicReady(job);prepared=null;submit.click();return {};
      }
      if(action==='expand'){
        const box=root();if(all('#datepicker-trigger',box).length===1)return {};
        const expand=all('#second-container-expand-button',box)[0];if(!expand)throw Error('Studio Schedule section is unavailable.');
        expand.click();await wait(()=>all('#datepicker-trigger',root())[0],'the Schedule section');return {};
      }
      if(action==='date'){
        const b=dateTrigger();(b.querySelector('.dropdown-trigger-text')||b).click();
        const input=await wait(()=>all('input').find(e=>/^(?:[A-Z][a-z]{2} \d{1,2}, \d{4}|\d{1,2} [A-Z][a-z]{2} \d{4})$/.test(e.value)),'the calendar date input');
        return {...control(input,job,'date'),date_order:/^\d/.test(input.value)?'day_first':'month_first'};
      }
      if(action==='time'){
        await wait(()=>!all('input').some(e=>e.getAttribute('data-storylens-input')===job.video_id+'-date'),
          'the calendar to close after confirming its date');
        const input=await wait(()=>timeInput(),'the release time input');return control(input,job,'time');
      }
      if(action==='ready'){await wait(()=>timeInput(),'the release time input');const proof=ready(job);prepared=[job.video_id,job.channel_id,job.publish_at].join('|');return proof;}
      if(action==='cancel'){prepared=null;button('Cancel',root()).click();return {};}
      if(action==='commit'){
        if(job.action==='youtube_schedule_preview')throw Error('A scheduling preview cannot submit a schedule.');
        if(prepared!==[job.video_id,job.channel_id,job.publish_at].join('|'))throw Error('Studio task was not prepared for this exact video.');
        ready(job);prepared=null;button('Schedule',root()).click();
        // Do not navigate this shared Studio tab away while Save is pending.
        // Independent API readback still determines whether scheduling worked.
        let settled=0;
        await wait(()=>{
          account(job);
          try{root();settled=0;return false}catch(_){}
          const current=row(job);
          if(!(current&&all('[role="cell"]',current).some(e=>text(e)==='Scheduled'))){settled=0;return false}
          return ++settled>=8;
        },'the saved schedule to appear on this exact video');
        return {ui_commit_settled:true};
      }
      throw Error('Unsupported Studio action.');
    })().then(result=>reply({ok:true,...result}),error=>reply({ok:false,error:error.message}));return true;
  });
})();
