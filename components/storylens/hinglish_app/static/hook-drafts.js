(() => {
  const $ = id => document.getElementById(id);
  const token = document.documentElement.dataset.token;
  if (token === '__APP_TOKEN__' && location.hostname === '127.0.0.1' && location.port !== '8896') {
    const query = new URLSearchParams(location.search);
    query.set('timing', '5');
    location.replace('http://127.0.0.1:8896/hook-drafts.html?' + query);
    return;
  }
  const view = $('hook-view'), status = $('hook-status');
  const introType = $('hook-intro-type'), timingStatus = $('hook-timing-status');
  const play = $('hook-play'), stop = $('hook-stop');
  const clock = $('hook-clock'), storage = 'storylens.hook-draft.v2.';
  let project, draft, videos = [], sources = [], context, frame, generation = 0;
  const transfers = new Map();
  const preview = $('hook-preview');
  const buffers = new Map();
  const url = asset => '/api/workbench/hook-media?' + new URLSearchParams({asset,token});

  function waitFor(element, event, trigger) {
    return new Promise((resolve,reject) => {
      const timeout = setTimeout(() => finish(new Error('A source did not become ready. Try playback again.')),18000);
      const ready = () => finish();
      const failed = () => finish(new Error('A source could not be opened.'));
      function finish(error) {
        clearTimeout(timeout);
        element.removeEventListener(event,ready);
        element.removeEventListener('error',failed);
        if (error) reject(error); else resolve();
      }
      element.addEventListener(event,ready,{once:true});
      element.addEventListener('error',failed,{once:true});
      trigger();
    });
  }
  function halt() {
    ++generation;
    cancelAnimationFrame(frame);
    for (const video of videos) {
      video.pause();
      video.removeAttribute('src');
      video.load();
    }
    for (const source of sources) {
      try { source.stop(); } catch (_) {}
    }
    videos = [];
    sources = [];
    view.replaceChildren();
    play.disabled = false;
    stop.disabled = true;
  }
  function table(container, headings) {
    const table = document.createElement('table');
    const head = table.createTHead().insertRow();
    for (const text of headings) {
      const th = document.createElement('th');
      th.textContent = text;
      head.append(th);
    }
    container.replaceChildren(table);
    return table.createTBody();
  }
  function cell(row,value) { row.insertCell().textContent = value; }
  function number(row,label,value,step,min,max,apply) {
    const field = document.createElement('input');
    Object.assign(field,{type:'number',step,min,max,value});
    field.setAttribute('aria-label',label);
    field.onchange = () => {
      const next = field.valueAsNumber;
      if (!Number.isFinite(next) || next < min || next > max) {
        field.value = value;
        status.textContent = 'Enter a value within the displayed source range.';
        return;
      }
      halt();
      apply(next);
      value = next;
      clock.value = '0.00 s';
      try { remember(draft); status.textContent = 'Saved to History.'; }
      catch (_) { status.textContent = 'Browser storage is full. You can still export this draft.'; }
    };
    row.insertCell().append(field);
  }
  function select(id, override, past = true) {
    halt();
    const base = project.drafts.find(item => item.id === id) || project.drafts[0];
    try {
      const saved = base.id.startsWith('my-') ? null : JSON.parse(localStorage.getItem(storage+base.id));
      draft = override || saved || structuredClone(base);
    }
    catch (_) { draft = structuredClone(base); }
    $(past?'hook-past':'hook-current').append(preview);
    preview.hidden = false;
    view.dataset.vertical = String(!draft.original_audio);
    const seconds = draft.frames/project.fps;
    $('hook-title').textContent = draft.title + ' · ' + Number(seconds.toFixed(2)) + ' seconds';
    introType.value = draft.original_audio ? 'youtube' : 'reel';
    toggleGaming();
    $('hook-total-seconds').value = Number(seconds.toFixed(3));
    $('hook-clip-seconds').value = Number(((draft.clipFrames ?? draft.shots[0].frames)/project.fps).toFixed(3));
    timingStatus.textContent = '';
    $('hook-apply-timing').disabled = false;
    for (const button of $('hook-options').children) button.setAttribute('aria-pressed',String(button.dataset.draft===base.id));
    clock.value = '0.00 s';
    status.textContent = 'Ready to preview.';
    window.storylensEditors.exportRow($('hook-exports'), exportDraft);
    const shots = table($('hook-shots'),['Timeline','Scene','Source in (s)','Length (s)']);
    let position = 0;
    draft.shots.forEach((shot,index) => {
      const row = shots.insertRow(), length = shot.frames/project.fps;
      cell(row,(position/project.fps).toFixed(2)+' s');
      cell(row,shot.label);
      number(row,'Shot '+(index+1)+' source in',shot.in,0.01,0,
             Math.floor((project.assets[shot.asset].duration-length)*100)/100,
             value => shot.in = value);
      cell(row,length.toFixed(2));
      position += shot.frames;
    });
    const audio = table($('hook-audio'),['Sound','Timeline (s)','Source in (s)','Length (s)','Gain (dB)']);
    draft.audio.forEach((cue,index) => {
      const row = audio.insertRow(), name = project.assets[cue.asset].name;
      cell(row,name);
      number(row,'Cue '+(index+1)+' timeline start',cue.at,0.01,0,
             Math.max(0,Math.floor((draft.frames/project.fps-cue.length+1e-8)*100)/100), value => cue.at=value);
      number(row,'Cue '+(index+1)+' source in',cue.in,0.01,0,
             Math.floor((project.assets[cue.asset].duration-cue.length)*100)/100, value => cue.in=value);
      cell(row,cue.length.toFixed(2));
      number(row,'Cue '+(index+1)+' gain',cue.db,1,-48,0,value => cue.db = value);
    });
    $('hook-credits').textContent = draft.original_audio ? project.credits : 'Sound effects by Mixkit.';
  }
  function addDraftButton(entry) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.draft = entry.id;
    button.textContent = entry.id.startsWith('my-') ? entry.title+' · '+Number((entry.frames/project.fps).toFixed(2))+' s · '+entry.shots.length+' cuts' : entry.title;
    button.onclick = () => select(entry.id);
    $('hook-options').append(button);
  }
  function setTimingDefaults() {
    const youtube = introType.value === 'youtube';
    $('hook-total-seconds').value = youtube ? 30 : 3;
    $('hook-clip-seconds').value = youtube ? 3 : 0.5;
    timingStatus.textContent = '';
  }
  function toggleGaming() {
    const gaming = introType.value === 'gaming';
    $('gaming-intro').hidden = !gaming;
    for (const id of ['hook-total-seconds', 'hook-clip-seconds']) {
      const input = $(id);
      input.disabled = gaming;
      input.closest('label').hidden = gaming;
    }
    $('hook-apply-timing').hidden = gaming;
    timingStatus.hidden = gaming;
    $('hook-current').hidden = gaming;
    $('hook-history').hidden = gaming;
  }
  introType.onchange = () => {
    halt();
    toggleGaming();
    if (introType.value !== 'gaming') setTimingDefaults();
  };
  $('hook-custom').onsubmit = event => {
    event.preventDefault();
    if (introType.value === 'gaming') {
      window.storylensGamingIntro.create();
      return;
    }
    if (!project) return;
    const fps = project.fps;
    const frames = Math.round($('hook-total-seconds').valueAsNumber*fps);
    const perClip = Math.round($('hook-clip-seconds').valueAsNumber*fps);
    const count = Math.ceil(frames/perClip);
    if (!Number.isInteger(frames) || !Number.isInteger(perClip) || perClip<1 || frames<1 || count>40) {
      timingStatus.textContent = 'Choose timing that gives between 1 and 40 cuts.';
      return;
    }
    const originalAudio = introType.value === 'youtube';
    const id = 'my-' + crypto.randomUUID();
    const title = originalAudio ? 'My custom YouTube intro' : 'My custom reel';
    const lengths = Array.from({length:count},(_,i) => Math.min(perClip,frames-i*perClip));
    let shots, audio;
    if (originalAudio) {
      const reference = project.drafts.find(item => item.approved);
      const first = reference.shots[0].in, last = reference.shots[reference.shots.length-1].in;
      const asset = reference.shots[0].asset;
      shots = lengths.map((length,i) => {
        const position = first+(last-first)*i/Math.max(1,count-1);
        return {asset,frames:length,label:'Documentary excerpt '+(i+1),
                in:Math.min(Math.round(position*fps)/fps,project.assets[asset].duration-length/fps)};
      });
      const seconds = frames/fps;
      audio = reference.audio.filter((cue,i) => i===0 || cue.at+cue.length<=seconds)
        .map((cue,i) => i===0 ? {...cue,length:seconds} : {...cue});
    } else {
      const unique = new Map();
      for (const shot of [...(draft?.shots||[]),...project.drafts.filter(d => /^instagram-[abc]$/.test(d.id)).flatMap(d=>d.shots)]) {
        if (!unique.has(shot.asset) && project.assets[shot.asset].duration>=lengths[0]/fps) unique.set(shot.asset,shot);
      }
      if (unique.size<count) {
        timingStatus.textContent = 'Only '+unique.size+' different reel sources are long enough for this setting.';
        return;
      }
      const options = [...unique.values()];
      shots = lengths.map((length,i) => {
        const shot = options[i];
        return {...shot,frames:length,in:Math.min(shot.in,project.assets[shot.asset].duration-length/fps)};
      });
      const seconds = frames/fps, peak = 6.35, length = Math.min(seconds,peak+.05);
      audio = [{asset:'ridge-rise',at:seconds-length,in:peak+.05-length,length,db:-6,fade_out:.008}];
    }
    const created = {id,title,frames,clipFrames:perClip,shots,audio,original_audio:originalAudio};
    project.drafts.push(created);
    addDraftButton(created);
    let saved = true;
    try { remember(created); } catch (_) { saved = false; }
    $('hook-history').open = false;
    select(id,created,false);
    timingStatus.textContent = (frames/fps).toFixed(2)+' seconds · '+count+' cuts. '+(originalAudio ? 'Review the manual cut points for complete speech. ' : '')+
      (frames%perClip ? 'The final cut is shorter to fit the total length. ' : '')+(saved?'Saved to History.':'Browser storage is full. You can still export this draft.');
  };
  function sound(asset) {
    if (!buffers.has(asset)) {
      const promise = fetch(url(asset)).then(response => {
        if (!response.ok) throw new Error('A sound recording could not be opened.');
        return response.arrayBuffer();
      }).then(bytes => context.decodeAudioData(bytes));
      buffers.set(asset,promise);
      promise.catch(() => buffers.delete(asset));
    }
    return buffers.get(asset);
  }
  async function prepareShot(shot, originalAudio) {
    const video = document.createElement('video');
    video.muted = !originalAudio;
    video.playsInline = true;
    video.preload = 'auto';
    video.style.visibility = 'hidden';
    video.style.objectPosition = (shot.x ?? 50) + '% center';
    videos.push(video);
    view.append(video);
    await waitFor(video,'loadeddata',() => { video.src = url(shot.asset); });
    if (shot.in > 0.01) await waitFor(video,'seeked',() => { video.currentTime = shot.in; });
    return video;
  }
  function cueSource(cue, buffer, start) {
    const source = context.createBufferSource(), gain = context.createGain();
    const level = 10 ** (cue.db/20), end = start+cue.length;
    source.buffer = buffer;
    source.connect(gain).connect(context.destination);
    gain.gain.setValueAtTime(0,start);
    gain.gain.linearRampToValueAtTime(level,start+0.012);
    gain.gain.setValueAtTime(level,end-Math.min(cue.fade_out ?? .12,cue.length/3));
    gain.gain.linearRampToValueAtTime(0,end);
    source.start(start,cue.in,cue.length);
    sources.push(source);
  }
  play.onclick = async () => {
    halt();
    const run = generation, selected = draft;
    const duration = selected.frames/project.fps;
    play.disabled = true;
    stop.disabled = false;
    status.textContent = 'Loading picture and sound…';
    clock.value = '0.00 s';
    try {
      context ??= new AudioContext();
      await context.resume();
      const [clips, audio] = await Promise.all([
        Promise.all(selected.shots.map(shot => prepareShot(shot,selected.original_audio))),
        Promise.all(selected.audio.map(cue => sound(cue.asset)))
      ]);
      if (run !== generation) return;
      const start = context.currentTime+.12;
      selected.audio.forEach((cue,index) => cueSource(cue,audio[index],start+cue.at));
      let active = -1;
      const cutEnds = [];
      selected.shots.reduce((end,shot) => {cutEnds.push(end+shot.frames); return end+shot.frames;},0);
      function update() {
        const position = Math.max(0,context.currentTime-start);
        if (position >= duration) {
          for (const video of clips) video.pause();
          play.disabled = false;
          stop.disabled = false;
          clock.value = duration.toFixed(2)+' s';
          status.textContent = 'Intro preview finished.';
          return;
        }
        if (context.currentTime >= start) {
          const next = cutEnds.findIndex(end => position*project.fps < end);
          if (next !== active) {
            if (active >= 0) { clips[active].pause(); clips[active].style.visibility='hidden'; }
            active = next;
            clips[active].style.visibility='visible';
            clips[active].play().catch(error => {
              if (run !== generation) return;
              halt();
              status.textContent = error.message;
            });
            status.textContent = 'Shot '+(next+1)+' of '+clips.length+' · '+selected.shots[next].label;
          }
          clock.value = position.toFixed(2)+' s';
        }
        frame = requestAnimationFrame(update);
      }
      update();
    } catch (error) {
      if (run !== generation) return;
      halt();
      status.textContent = error.message;
    }
  };
  stop.onclick = () => { halt(); clock.value = '0.00 s'; status.textContent = 'Stopped.'; };
  function remember(value) {
    localStorage.setItem(storage+value.id,JSON.stringify(value));
    const index = project.drafts.findIndex(item => item.id === value.id);
    if (index >= 0 && value.id.startsWith('my-')) project.drafts[index] = structuredClone(value);
  }
  async function post(url, value) {
    const reply = await window.storylensFetch(url,{
      method:'POST',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},
      body:JSON.stringify(value)
    });
    return window.storylensResponse(reply);
  }
  async function exportDraft(editor, button) {
    button.disabled = true;
    const selected = structuredClone(draft);
    const key = editor + JSON.stringify(selected);
    try {
      remember(selected);
      status.textContent = 'Preparing editable intro…';
      let transfer = transfers.get(key);
      if (!transfer) {
        transfer = await post('/api/workbench/hook-export',{editor,draft:selected});
        transfers.set(key,transfer);
      }
      await window.storylensEditors.confirmTransfer(()=>post('/api/editor-link/apply',{id:transfer.id}),
        message=>status.textContent=message,()=>draft.id===selected.id&&button.isConnected);
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  }
  fetch('/api/workbench/hook-drafts',{headers:{'X-Hinglish-Token':token}})
    .then(window.storylensResponse).then(result => {
      project = result;
      const custom = Object.keys(localStorage).filter(key=>key.startsWith(storage+'my-')).map(key=>key.slice(storage.length));
      for (const id of custom) {
        try { const saved=JSON.parse(localStorage.getItem(storage+id)); if(saved) project.drafts.push(saved); } catch (_) {}
      }
      for (const entry of project.drafts) addDraftButton(entry);
      const savedId=new URLSearchParams(location.search).get('draft');
      if (savedId && project.drafts.some(item=>item.id===savedId)) { $('hook-history').open=true; select(savedId); }
      else setTimingDefaults();
      $('hook-apply-timing').disabled=false;
    }).catch(error => timingStatus.textContent=error.message);
})();
