(() => {
  const trigger = document.querySelector('[data-support-call]');
  if (!trigger) return;

  const svg = path => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + path + '</svg>';
  const pauseIcon = svg('<path d="M9 5v14m6-14v14"/>');
  const micIcon = svg('<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M6 11v1a6 6 0 0 0 12 0v-1m-6 7v3m-3 0h6"/>');
  const endIcon = svg('<path d="M3 15v-3c5-5 13-5 18 0v3h-5v-3a11 11 0 0 0-8 0v3z"/>');
  const minimizeIcon = svg('<path d="M5 12h14"/>');
  const closeIcon = svg('<path d="m6 6 12 12M18 6 6 18"/>');
  const expandIcon = svg('<path d="M8 4H4v4m12-4h4v4M4 16v4h4m12-4v4h-4"/>');
  const resizeIcon = svg('<path d="M4 15V4h11M4 4l9 9"/>');
  const dialog = document.createElement('dialog');
  dialog.id = 'storylens-call-panel';
  dialog.className = 'support-call';
  dialog.setAttribute('aria-labelledby', 'support-call-title');
  trigger.setAttribute('aria-haspopup', 'dialog');
  trigger.setAttribute('aria-controls', dialog.id);
  trigger.setAttribute('aria-expanded', 'false');
  dialog.innerHTML = '<header class="support-call-header"><span class="support-call-name-mark" aria-hidden="true"></span>' +
    '<div><h2 id="support-call-title">Cortana AI</h2><span class="support-call-kind">Voice assistant</span></div>' +
    '<button type="button" class="support-call-icon" data-call-expand aria-label="Expand call to fill screen" aria-pressed="false" title="Expand call to fill screen">' + expandIcon + '</button>' +
    '<button type="button" class="support-call-icon" data-call-minimize aria-label="Minimize call" title="Minimize call">' + minimizeIcon + '</button>' +
    '<button type="button" class="support-call-icon" data-call-close aria-label="Close voice assistant" title="Close and end call">' + closeIcon + '</button></header>' +
    '<label class="support-call-language" hidden><span>Voice language</span><select data-call-language>' +
    '<option value="auto">Auto</option><option value="hi">Hindi</option><option value="en">English</option></select></label>' +
    '<div class="support-call-stage" data-call-stage role="region" tabindex="0" aria-label="Cortana 3D view. Drag or use the arrow keys to orbit. Home resets the camera."><span data-call-visual-note>Loading 3D hologram…</span></div>' +
    '<button type="button" data-call-closeup aria-pressed="false">Close-up</button>' +
    '<p data-call-status role="status"></p><p data-call-detail></p>' +
    '<div class="support-call-controls">' +
    '<button type="button" data-call-pause hidden>' + pauseIcon + '<span>Pause</span></button>' +
    '<button type="button" data-call-retry hidden>' + micIcon + '<span>Try again</span></button>' +
    '<button type="button" data-call-end>' + endIcon + '<span>End call</span></button></div>' +
    '<button type="button" class="support-call-icon" data-call-resize aria-label="Resize call panel" title="Drag or use arrow keys to resize">' + resizeIcon + '</button>';
  const dock = document.createElement('aside');
  dock.className = 'support-call-dock';
  dock.setAttribute('aria-label', 'Minimized Cortana AI call');
  dock.hidden = true;
  dock.innerHTML = '<button type="button" data-call-restore aria-label="Restore Cortana AI call" aria-controls="' + dialog.id + '">' +
    '<span class="support-call-avatar-mini" aria-hidden="true"></span><span data-call-dock-status role="status"></span></button>' +
    '<button type="button" class="support-call-icon" data-call-dock-pause aria-label="Pause call" title="Pause call" hidden>' + pauseIcon + '</button>';
  document.body.append(dialog, dock);

  const status = dialog.querySelector('[data-call-status]');
  const detail = dialog.querySelector('[data-call-detail]');
  const pause = dialog.querySelector('[data-call-pause]');
  const retry = dialog.querySelector('[data-call-retry]');
  const stage = dialog.querySelector('[data-call-stage]');
  const visualNote = dialog.querySelector('[data-call-visual-note]');
  const dockStage = dock.querySelector('.support-call-avatar-mini');
  const expand = dialog.querySelector('[data-call-expand]');
  const closeup = dialog.querySelector('[data-call-closeup]');
  let avatar, avatarModule;
  const provider = dialog.querySelector('.support-call-kind');
  const language = dialog.querySelector('[data-call-language]');
  const minimize = dialog.querySelector('[data-call-minimize]');
  const resize = dialog.querySelector('[data-call-resize]');
  const restore = dock.querySelector('[data-call-restore]');
  const dockStatus = dock.querySelector('[data-call-dock-status]');
  const dockPause = dock.querySelector('[data-call-dock-pause]');
  try {
    const saved = localStorage.getItem('storylens-call-language');
    if (['auto', 'hi', 'en'].includes(saved)) language.value = saved;
  } catch (_) {}
  language.addEventListener('change', () => {
    try { localStorage.setItem('storylens-call-language', language.value); } catch (_) {}
  });
  const audio = document.createElement('audio');
  audio.autoplay = true;
  dialog.append(audio);

  const labels = {
    connecting: 'Connecting…',
    ready: 'Listening',
    listening: 'Listening',
    thinking: 'Thinking…',
    speaking: 'Speaking',
    paused: 'Paused',
    error: 'Voice unavailable',
  };
  const token = document.documentElement.dataset.token;
  let call;
  function show(next, hint = '') {
    dialog.dataset.phase = dock.dataset.phase = next;
    if (status.textContent !== labels[next]) status.textContent = labels[next];
    if (detail.textContent !== hint) detail.textContent = hint;
    const compactLabel = next === 'error' ? 'Check call' : labels[next];
    if (dockStatus.textContent !== compactLabel) dockStatus.textContent = compactLabel;
    restore.title = hint ? 'Restore Cortana AI call · ' + hint : 'Restore Cortana AI call';
    dockPause.hidden = pause.hidden;
  }

  const current = session => call === session;
  async function request(path, session, options = {}) {
    const { timeoutMs = ({ 'local-turn': 15000, 'local-step': 15000, 'local-speech': 6000,
      'local-result': 1500, 'local-end': 1500 })[path] || 90000, ...fetchOptions } = options;
    const parent = Object.hasOwn(fetchOptions, 'signal') ? fetchOptions.signal : session.abort.signal;
    const bounded = new AbortController();
    let timedOut = false;
    const cancel = () => bounded.abort(parent?.reason);
    if (parent?.aborted) cancel();
    else parent?.addEventListener('abort', cancel, { once: true });
    const timer = setTimeout(() => { timedOut = true; bounded.abort(); }, timeoutMs);
    try {
      const response = await fetch('/api/support-call/' + path, {
        cache: 'no-store', ...fetchOptions, signal: bounded.signal,
        headers: { 'X-Hinglish-Token': token, ...fetchOptions.headers },
      });
      if (!response.headers.get('content-type')?.includes('application/json')) {
        throw new Error('Storylens could not reach its voice service.');
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Storylens could not connect.');
      return data;
    } catch (error) {
      if (timedOut) throw new Error('The voice service took too long. Please try again; check the screen before repeating an action.');
      throw error;
    } finally {
      clearTimeout(timer);
      parent?.removeEventListener('abort', cancel);
    }
  }

  function release() {
    const session = call;
    if (!session) return;
    call = null;
    session.abort.abort();
    session.turnAbort?.abort();
    if (session.local) {
      session.capture?.port.close();
      session.capture?.disconnect();
      stopLocalOutput(session);
      request('local-end', session, {
        method: 'POST', signal: undefined, keepalive: true,
        headers: { 'X-Storylens-Call': session.id },
      }).catch(() => {});
    }
    clearTimeout(session.connectTimer);
    clearTimeout(session.callTimer);
    clearTimeout(session.disconnectTimer);
    session.stream?.getTracks().forEach(track => track.stop());
    session.events?.close();
    session.peer?.close();
    session.context?.close().catch(() => {});
    audio.pause();
    audio.srcObject = null;
    audio.muted = false;
  }

  function fail(session, message) {
    if (!current(session)) return;
    release();
    pause.hidden = true;
    retry.hidden = false;
    show('error', message);
  }

  function send(session, type, fields = {}) {
    if (session.events?.readyState === 'open') session.events.send(JSON.stringify({ type, ...fields }));
  }

  function stopReply(session) {
    if (session.responseActive) send(session, 'response.cancel');
    if (session.playing) send(session, 'output_audio_buffer.clear');
  }

  function updatePhase(session) {
    if (session.paused) show('paused', 'Resume when you’re ready to talk.');
    else if (session.userSpeaking) show('listening');
    else if (session.playing) show('speaking');
    else if (session.responseActive || session.waiting) show('thinking');
    else show('ready', session.notice || 'Speak naturally.');
  }

  function handleEvent(session, payload) {
    if (!current(session)) return;
    let event;
    try { event = JSON.parse(payload); } catch (_) { return; }
    switch (event.type) {
      case 'input_audio_buffer.speech_started': session.userSpeaking = !session.paused; break;
      case 'input_audio_buffer.speech_stopped':
        session.userSpeaking = false;
        session.waiting = !session.paused;
        break;
      case 'response.created':
        session.waiting = false;
        session.responseActive = true;
        if (session.paused) stopReply(session);
        break;
      case 'response.done':
        session.responseActive = session.waiting = false;
        if (event.response?.status === 'failed') {
          fail(session, 'Storylens could not finish the reply. Try calling again.');
          return;
        }
        break;
      case 'output_audio_buffer.started':
        session.playing = true;
        if (session.paused) stopReply(session);
        break;
      case 'output_audio_buffer.stopped':
      case 'output_audio_buffer.cleared': session.playing = false; break;
      case 'error':
        if (['response_cancel_not_active', 'input_audio_buffer_clear_empty'].includes(event.error?.code)) return;
        fail(session, 'OpenAI ended the voice session. Try calling again.');
        return;
      default: return;
    }
    updatePhase(session);
  }

  async function openMicrophone(session) {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Open Storylens in Chrome or Edge with microphone access.');
    }
    let timer;
    let expired = false;
    const microphone = navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    }).then(stream => {
      if (!expired && current(session)) return stream;
      stream.getTracks().forEach(track => track.stop());
      return null;
    });
    const deadline = new Promise((_, reject) => {
      timer = setTimeout(() => {
        expired = true;
        reject(new Error('Microphone permission timed out. Allow access in the browser, then click Try again.'));
      }, 20000);
    });
    let stream;
    try {
      stream = await Promise.race([microphone, deadline]);
    } finally {
      clearTimeout(timer);
    }
    if (!stream) return null;
    session.stream = stream;
    const track = stream.getAudioTracks()[0];
    if (!track) throw new Error('Chrome did not provide a microphone track.');
    track.addEventListener('ended', () => fail(session, 'The microphone disconnected. Check it and try again.'));
    return track;
  }

  async function connect(session) {
    const config = await request('status', session);
    if (!current(session)) return;
    if (config.local) {
      await connectLocal(session);
      return;
    }
    if (!config.realtime || !window.RTCPeerConnection) {
      fail(session, 'The voice engine is unavailable on this device.');
      return;
    }
    show('connecting', 'Allow microphone access if Chrome asks.');
    const track = await openMicrophone(session);
    if (!track) return;
    const stream = session.stream;
    track.enabled = false;
    show('connecting', 'Opening the voice channel.');
    const peer = session.peer = new RTCPeerConnection();
    peer.addTrack(track, stream);
    peer.ontrack = event => {
      if (!current(session)) return;
      const incoming = event.streams[0] || new MediaStream([event.track]);
      audio.srcObject = incoming;
      audio.play().catch(() => fail(session, 'Chrome blocked call audio. Allow sound and try again.'));
    };
    peer.onconnectionstatechange = () => {
      if (!current(session)) return;
      clearTimeout(session.disconnectTimer);
      if (peer.connectionState === 'failed') fail(session, 'The voice connection dropped. Try again.');
      if (peer.connectionState === 'disconnected') {
        session.disconnectTimer = setTimeout(() => fail(session, 'The voice connection dropped. Try again.'), 5000);
      }
    };
    const events = session.events = peer.createDataChannel('oai-events');
    events.onopen = () => {
      if (!current(session)) return;
      clearTimeout(session.connectTimer);
      session.waiting = true;
      send(session, 'response.create', { response: { instructions: 'Greet briefly as Cortana AI and ask how you can help.' } });
      track.enabled = true;
      pause.hidden = false;
      updatePhase(session);
    };
    events.onmessage = event => handleEvent(session, event.data);
    events.onclose = () => fail(session, 'The voice channel closed. Try again to reconnect.');

    session.connectTimer = setTimeout(() => fail(session, 'The voice connection timed out. Try again.'), 25000);
    await peer.setLocalDescription(await peer.createOffer());
    if (!current(session)) return;
    const data = await request('connect', session, {
      method: 'POST', body: peer.localDescription.sdp, headers: { 'Content-Type': 'application/sdp' },
    });
    if (current(session)) await peer.setRemoteDescription({ type: 'answer', sdp: data.sdp });
  }

  function activeTool() {
    const tool = window.storylensVoiceTool?.();
    if (tool) return tool;
    if (document.querySelector('.scheduled-dialog[open]')) return 'scheduledPosts';
    const frame = [...document.querySelectorAll('.storylens-voice-workspace[open] iframe')].at(-1);
    const workspace = frame?.contentDocument || document;
    if (workspace.querySelector('.scheduled-dialog[open]')) return 'scheduledPosts';
    const routes = {
      '/prepare-post.html': 'preparePost', '/call-qa.html': 'callQA', '/ai-agents.html': 'aiAgents',
      '/activation.html': 'activation', '/workflow.html': 'workflow', '/chrome.html': 'chromePublisher',
      '/stock-browser.html': 'stockBrowser', '/documentary-intro.html': 'documentaryIntro',
      '/native-curation.html': 'nativeCuration', '/cinematic.html': 'cinematicReels',
    };
    const mode = workspace.querySelector('.panel[data-mode]')?.dataset.mode;
    const caption = mode === 'captions' && workspace.querySelector('#autoCaptionPanel button[aria-pressed="true"][data-extra]')?.dataset.extra;
    if (caption === 'important') return 'importantCaptions';
    if (caption === 'cinematic') return 'textEffects';
    return mode || routes[workspace.location.pathname] || '';
  }

  function encodeWave(frames, rate) {
    const sampleRate = 16000;
    const samples = new Float32Array(frames.reduce((total, frame) => total + frame.length, 0));
    let offset = 0;
    for (const chunk of frames) {
      samples.set(chunk, offset);
      offset += chunk.length;
    }
    const sampleCount = Math.floor(samples.length * sampleRate / rate);
    const buffer = new ArrayBuffer(44 + 2 * sampleCount);
    const header = new DataView(buffer);
    function tag(offset, name) {
      for (let i = 0; i < name.length; i++) header.setUint8(offset + i, name.charCodeAt(i));
    }
    tag(0, 'RIFF');
    header.setUint32(4, buffer.byteLength - 8, true);
    tag(8, 'WAVE');
    tag(12, 'fmt ');
    header.setUint32(16, 16, true);
    header.setUint16(20, 1, true);
    header.setUint16(22, 1, true);
    header.setUint32(24, sampleRate, true);
    header.setUint32(28, sampleRate * 2, true);
    header.setUint16(32, 2, true);
    header.setUint16(34, 16, true);
    tag(36, 'data');
    header.setUint32(40, sampleCount * 2, true);
    for (let i = 0; i < sampleCount; i++) {
      const begin = Math.floor(i * rate / sampleRate);
      const end = Math.max(begin + 1, Math.floor((i + 1) * rate / sampleRate));
      let sum = 0;
      for (let j = begin; j < end; j++) sum += samples[j];
      const value = Math.max(-1, Math.min(1, sum / (end - begin)));
      header.setInt16(44 + 2 * i, value * (value < 0 ? 32768 : 32767), true);
    }
    return buffer;
  }

  function showAvatar(host) {
    if (avatar) {
      avatar.move(host);
      return;
    }
    avatarModule ||= import('/cortana-3d-portrait.js?v=20261109-avatar-finish').then(({mountCortana}) => {
      avatar = mountCortana(stage, () => dialog.dataset.phase);
      avatar.closer(closeup.getAttribute('aria-pressed') === 'true');
      avatar.move(dialog.open ? stage : dockStage);
      const speech = call?.visualSpeech;
      if (speech) avatar.voice(...speech);
      return avatar.ready;
    }).then(() => {
      stage.dataset.model = 'ready';
      visualNote.hidden = true;
    }).catch(error => {
      stage.dataset.model = 'unavailable';
      visualNote.textContent = '3D view unavailable. Voice is still active.';
      console.warn('StoryLens Cortana 3D view:', error);
    });
  }

  function stopLocalOutput(session) {
    avatar?.quiet();
    session.visualSpeech = null;
    session.playback++;
    const output = session.output;
    if (output) {
      output.onended = null;
      output.stop();
      output.disconnect();
      session.output = null;
    }
    session.playing = false;
  }

  async function playLocal(session, wav, turn = null) {
    stopLocalOutput(session);
    if (!wav || !current(session) || session.paused || session.userSpeaking) return;
    const playback = session.playback;
    const bytes = Uint8Array.from(atob(wav), char => char.charCodeAt(0));
    const decoded = await session.context.decodeAudioData(bytes.buffer);
    if (!current(session) || playback !== session.playback || session.paused || session.userSpeaking) return;
    const source = session.context.createBufferSource();
    source.buffer = decoded;
    source.connect(session.context.destination);
    session.output = source;
    source.onended = () => {
      source.disconnect();
      if (!current(session) || session.output !== source) return;
      avatar?.quiet();
      session.visualSpeech = null;
      session.output = null;
      session.playing = false;
      updatePhase(session);
    };
    const startedAt = session.context.currentTime;
    source.start(startedAt);
    if (turn?.id) recordAudibleStart(session, turn, decoded);
    session.playing = true;
    updatePhase(session);
    session.visualSpeech = [session.context, decoded, startedAt];
    avatar?.voice(...session.visualSpeech);
  }


  function recordAudibleStart(session, turn, decoded) {
    // This estimates speaker onset from the first non-silent sample plus WebAudio
    // device latency. It is not a microphone loopback measurement of hardware.
    let first = decoded.length;
    for (let channel = 0; channel < decoded.numberOfChannels; channel += 1) {
      const samples = decoded.getChannelData(channel);
      for (let index = 0; index < first; index += 1) {
        if (Math.abs(samples[index]) > 0.001) { first = index; break; }
      }
    }
    if (first === decoded.length) return;
    const outputMs = 1000 * ((session.context.baseLatency || 0) + (session.context.outputLatency || 0));
    const timings = { endpoint_ms: Math.round(turn.sentAt - turn.speechEndedAt),
      response_ms: Math.round(turn.responseAt - turn.sentAt),
      action_ms: Math.round(turn.actionMs || 0),
      audio_start_ms: Math.round(performance.now() - turn.speechEndedAt + first / decoded.sampleRate * 1000 + outputMs),
      audio_output_latency_ms: Math.round(outputMs) };
    const rows = window.storylensVoiceLatency ||= [];
    rows.push({ id: turn.id, at: new Date().toISOString(), ...timings, measurement: 'WebAudio speaker-onset estimate' });
    if (rows.length > 30) rows.shift();
    request('local-result', session, {
      method: 'POST', body: JSON.stringify({ id: turn.id, audio_started: true, client_timings: timings }),
      headers: { 'Content-Type': 'application/json', 'X-Storylens-Call': session.id },
    }).catch(() => {});
  }


  function renewLocalCall(session) {
    clearTimeout(session.callTimer);
    session.callTimer = setTimeout(() => fail(session, 'This call ended after an hour of inactivity. You can start another.'), 3600000);
  }

  async function applyTurnAction(session, data, signal, turn = null) {
    if (data.action) {
      const started = performance.now();
      let notice = '';
      try {
        if (typeof window.storylensApplyVoiceAction !== 'function') throw new Error('Refresh Storylens once to load the voice controls.');
        notice = await window.storylensApplyVoiceAction(data.action, { signal, callId: session.id });
        signal.throwIfAborted();
        if (typeof notice === 'string') session.notice = notice;
        if (data.action.tool === 'storylensCall' ||
            /^(?:expand call to fill screen|restore call size|restore cortana ai call|full body|close-up|pause|resume|pause call|resume call|voice language)$/i.test(data.action.label || '')) {
          placeCallSurfaces();
        } else {
          minimizeCall(false);
        }
      } catch (error) {
        reportTurn(session, data.turn_id, false, error.message, started);
        throw error;
      }
      if (turn) turn.actionMs = (turn.actionMs || 0) + performance.now() - started;
      reportTurn(session, data.turn_id, true, notice, started);
      if (typeof data.confirmation_audio === 'string' && data.confirmation_audio &&
          ['open_tool', 'open_publishing', 'open_schedule', 'schedule_platform', 'set_control'].includes(data.action.type)) {
        // A warm acknowledgement is valid only after the receiving UI verifies success.
        data.audio = data.confirmation_audio;
        return;
      }
    } else if (data.minimize === true) {
      session.notice = typeof data.text === 'string' ? data.text : '';
      minimizeCall(false);
    }
    if (data.speech_id) {
      const reply = await request('local-speech', session, {
        method: 'POST', signal, body: JSON.stringify({ id: data.speech_id }),
        headers: { 'Content-Type': 'application/json', 'X-Storylens-Call': session.id },
      });
      data.audio = reply.audio;
    }
  }

  function reportTurn(session, id, ok, note, started) {
    if (!id) return;
    // Receipts have their own backend lock; telemetry must never delay the reply.
    session.receipt = request('local-result', session, {
      method: 'POST', body: JSON.stringify({ id, ok, note: String(note || '').slice(0, 400),
        browser_ms: Math.round(performance.now() - started) }),
      headers: { 'Content-Type': 'application/json', 'X-Storylens-Call': session.id },
    }).catch(() => {});
    return session.receipt;
  }

  async function executeChain(session, chain, signal, turn = null) {
    let data;
    for (let index = 0; index < chain.count; index += 1) {
      signal.throwIfAborted();
      show('thinking', 'Step ' + (index + 1) + ' of ' + chain.count);
      try {
        data = await request('local-step', session, {
          method: 'POST', signal, body: JSON.stringify({ id: chain.id, index }),
          headers: {
            'Content-Type': 'application/json',
            'X-Storylens-Call': session.id,
            'X-Storylens-Protocol': '2',
            'X-Storylens-Tool': activeTool(),
            'X-Storylens-Controls': window.storylensVoiceControls?.() || '',
            'X-Storylens-Fields': window.storylensVoiceFields?.() || '',
          },
        });
        if (!data.ok) {
          session.notice = 'Step ' + (index + 1) + ' stopped. ' + data.text;
          return data;
        }
        await applyTurnAction(session, data, signal, turn);
      } catch (error) {
        if (signal.aborted) throw error;
        throw new Error('Step ' + (index + 1) + ' stopped. ' + error.message);
      }
    }
    session.notice = 'Completed ' + chain.count + ' steps. ' + session.notice;
    return data;
  }

  async function localTurn(session, frames, speechEndedAt = performance.now()) {
    const turn = { speechEndedAt, sentAt: performance.now(), actionMs: 0 };
    const abort = new AbortController();
    session.turnAbort = abort;
    renewLocalCall(session);
    session.notice = '';
    session.waiting = true;
    updatePhase(session);
    try {
      let data = await request('local-turn', session, {
        method: 'POST', signal: abort.signal,
        body: encodeWave(frames, session.context.sampleRate),
        headers: {
          'Content-Type': 'audio/wav',
          'X-Storylens-Call': session.id,
            'X-Storylens-Protocol': '2',
          'X-Storylens-Tool': activeTool(),
          'X-Storylens-Language': language.value,
          'X-Storylens-Controls': window.storylensVoiceControls?.() || '',
            'X-Storylens-Fields': window.storylensVoiceFields?.() || '',
          'X-Storylens-Foreground': dialog.open ? '1' : '0',
        },
      });
      if (!current(session) || abort.signal.aborted) return;
      turn.responseAt = performance.now();
      if (data.chain) data = await executeChain(session, data.chain, abort.signal, turn);
      else await applyTurnAction(session, data, abort.signal, turn);
      turn.id = data.turn_id;
      if (!current(session) || abort.signal.aborted) return;
      session.waiting = false;
      if (!data.audio && !session.notice) session.notice = data.text || 'I didn’t catch that. Try speaking again.';
      await playLocal(session, data.audio, turn);
    } catch (error) {
      if (current(session) && !abort.signal.aborted) {
        session.notice = error.message || 'The voice engine missed that turn. Try again.';
      }
    } finally {
      if (current(session) && session.turnAbort === abort) {
        session.turnAbort = null;
        session.waiting = false;
        updatePhase(session);
      }
    }
  }

  function resetLocalInput(session) {
    session.preroll = [];
    session.utterance = null;
    session.voiceFrames = session.quietFrames = 0;
    session.userSpeaking = false;
  }

  function captureFrame(session, samples) {
    if (!current(session) || !session.localReady || session.paused || session.waiting) return;
    let energy = 0;
    for (const sample of samples) energy += sample * sample;
    const rms = Math.sqrt(energy / samples.length);
    const threshold = Math.max(session.playing ? 0.035 : 0.009, Math.min(session.noise * 2.8, 0.025));
    const voiced = rms > threshold;
    if (voiced) session.lastVoicedAt = performance.now();
    if (!voiced && !session.playing && !session.userSpeaking) {
      session.noise += (rms - session.noise) * 0.04;
    }

    // Each chunk is 32 ms. Keep a little audio from before the trigger, then
    // send automatically after 320 ms of quiet or 22 seconds of speech.
    if (!session.utterance) {
      session.preroll.push(samples);
      if (session.preroll.length > 10) session.preroll.shift();
      session.voiceFrames = voiced ? session.voiceFrames + 1 : 0;
      if (session.voiceFrames < (session.playing ? 5 : 3)) return;
      session.notice = '';
      session.utterance = session.preroll;
      session.preroll = [];
      session.userSpeaking = true;
      stopLocalOutput(session);
      updatePhase(session);
      return;
    }
    session.utterance.push(samples);
    session.quietFrames = voiced ? 0 : session.quietFrames + 1;
    if (session.quietFrames < 10 && session.utterance.length < 688) return;
    const utterance = session.utterance;
    const speechFrames = utterance.length - session.quietFrames;
    resetLocalInput(session);
    if (speechFrames < 11) {
      updatePhase(session);
      return;
    }
    localTurn(session, utterance, session.lastVoicedAt || performance.now());
  }

  async function connectLocal(session) {
    if (!session.context?.audioWorklet) {
      fail(session, 'Local voice requires a recent version of Chrome or Edge.');
      return;
    }
    session.local = true;
    session.id = crypto.randomUUID();
    renewLocalCall(session);
    language.parentElement.hidden = false;
    session.playback = 0;
    session.noise = 0.003;
    provider.textContent = 'On this device';
    resetLocalInput(session);
    show('connecting', 'Waiting for microphone access. Choose Allow if the browser asks.');
    const [ready, track] = await Promise.all([
      request('local-warm', session, {
        method: 'POST', headers: { 'X-Storylens-Call': session.id },
      }),
      openMicrophone(session).then(track => {
        if (track && current(session)) {
          show('connecting', 'Microphone connected. Starting the local voice models…');
        }
        return track;
      }),
      session.context.audioWorklet.addModule('/support-call-audio.js?v=1'),
    ]);
    if (!current(session) || !track) return;
    if (!ready.ready) throw new Error('The local voice engine did not finish starting.');
    await session.context.resume();
    if (!current(session)) return;
    const input = session.context.createMediaStreamSource(session.stream);
    const capture = new AudioWorkletNode(session.context, 'storylens-voice-capture');
    capture.port.onmessage = event => captureFrame(session, event.data);
    input.connect(capture);
    // Keep the capture graph active without sending the microphone to speakers.
    const silent = session.context.createGain();
    silent.gain.value = 0;
    capture.connect(silent).connect(session.context.destination);
    session.capture = capture;
    session.localReady = true;
    pause.hidden = false;
    updatePhase(session);
    await playLocal(session, ready.greeting_audio);
  }

  function start() {
    release();
    const session = { abort: new AbortController() };
    call = session;
    retry.hidden = pause.hidden = true;
    provider.textContent = 'Voice assistant';
    language.parentElement.hidden = true;
    updatePauseButton(false);
    show('connecting', 'Opening a live voice call.');
    if (window.AudioContext) {
      try {
        session.context = new AudioContext();
        session.context.resume().catch(() => {});
      } catch (_) {}
    }
    session.callTimer = setTimeout(() => fail(session, 'This call ended after ten minutes. You can start another.'), 600000);
    connect(session).catch(error => {
      const microphoneError = {
        NotAllowedError: 'Allow microphone access in the browser, then click Try again.',
        NotFoundError: 'No microphone was found. Connect one, then click Try again.',
        NotReadableError: 'The browser could not open the microphone. Check the selected input, then click Try again.',
      };
      fail(session, microphoneError[error.name] || error.message);
    });
  }

  function placeCallSurfaces() {
    // Native app dialogs make their siblings inert. Keep the live call within
    // the topmost modal without recreating its microphone or playback nodes.
    const modal = document.activeElement?.closest('dialog:modal') ||
      [...document.querySelectorAll('dialog:modal')].at(-1);
    const host = modal || document.body;
    for (const surface of [dialog, dock]) {
      if (surface.parentElement === host) continue;
      if (host.moveBefore && surface.isConnected) host.moveBefore(surface, null);
      else host.append(surface);
    }
  }

  function showPanel() {
    placeCallSurfaces();
    dock.hidden = true;
    dialog.show();
    setCloseup(false);
    showAvatar(stage);
    trigger.setAttribute('aria-expanded', 'true');
    minimize.focus({ preventScroll: true });
  }

  function openCall() {
    if (dialog.open) return;
    const needsConnection = dock.hidden;
    if (needsConnection) {
      dialog.style.removeProperty('--call-width');
      dialog.style.removeProperty('--call-height');
      setExpanded(false);
    }
    showPanel();
    if (needsConnection) start();
  }

  function minimizeCall(focusDock = true) {
    if (!dialog.open) {
      if (!dock.hidden) placeCallSurfaces();
      return;
    }
    const focusedInside = dialog.contains(document.activeElement);
    dialog.close();
    trigger.setAttribute('aria-expanded', 'false');
    dock.hidden = false;
    showAvatar(dockStage);
    placeCallSurfaces();
    if (focusDock || focusedInside) restore.focus({ preventScroll: true });
  }

  function hangup(restoreFocus = true) {
    const visible = dialog.open || !dock.hidden;
    release();
    if (dialog.open) dialog.close();
    dock.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    if (visible && restoreFocus) trigger.focus({ preventScroll: true });
  }

  function updatePauseButton(paused) {
    pause.innerHTML = paused ? micIcon + '<span>Resume</span>' : pauseIcon + '<span>Pause</span>';
    dockPause.innerHTML = paused ? micIcon : pauseIcon;
    const label = paused ? 'Resume call' : 'Pause call';
    dockPause.setAttribute('aria-label', label);
    dockPause.title = label;
  }

  function togglePause() {
    const session = call;
    if (!session?.stream) return;
    session.paused = !session.paused;
    session.stream.getAudioTracks().forEach(track => { track.enabled = !session.paused; });
    audio.muted = session.paused;
    if (session.paused) {
      session.userSpeaking = session.waiting = false;
      if (session.local) {
        session.turnAbort?.abort();
        session.turnAbort = null;
        resetLocalInput(session);
        stopLocalOutput(session);
      } else {
        stopReply(session);
        send(session, 'input_audio_buffer.clear');
      }
    }
    updatePauseButton(session.paused);
    updatePhase(session);
  }

  function setPanelSize(width, height) {
    const maxWidth = window.innerWidth - 32;
    const maxHeight = window.innerHeight - 32;
    dialog.style.setProperty('--call-width', Math.min(maxWidth, Math.max(Math.min(300, maxWidth), width)) + 'px');
    dialog.style.setProperty('--call-height', Math.min(maxHeight, Math.max(Math.min(350, maxHeight), height)) + 'px');
  }

  let drag;
  resize.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const bounds = dialog.getBoundingClientRect();
    drag = { x: event.clientX, y: event.clientY, width: bounds.width, height: bounds.height };
    resize.setPointerCapture(event.pointerId);
  });
  resize.addEventListener('pointermove', event => {
    if (drag) setPanelSize(drag.width + drag.x - event.clientX, drag.height + drag.y - event.clientY);
  });
  resize.addEventListener('lostpointercapture', () => { drag = null; });
  resize.addEventListener('keydown', event => {
    const delta = { ArrowLeft: [24, 0], ArrowRight: [-24, 0], ArrowUp: [0, 24], ArrowDown: [0, -24] }[event.key];
    if (!delta) return;
    event.preventDefault();
    setPanelSize(dialog.offsetWidth + delta[0], dialog.offsetHeight + delta[1]);
  });

  function setExpanded(expanded) {
    dialog.toggleAttribute('data-expanded', expanded);
    if (expanded) setCloseup(false);
    const label = expanded ? 'Restore call size' : 'Expand call to fill screen';
    expand.setAttribute('aria-pressed', String(expanded));
    expand.setAttribute('aria-label', label);
    expand.title = label;
  }
  expand.addEventListener('click', () => setExpanded(!dialog.hasAttribute('data-expanded')));
  function setCloseup(close) {
    closeup.setAttribute('aria-pressed', String(close));
    closeup.textContent = close ? 'Full body' : 'Close-up';
    avatar?.closer(close);
  }

  closeup.addEventListener('click', () => setCloseup(closeup.getAttribute('aria-pressed') !== 'true'));

  pause.addEventListener('click', togglePause);
  dockPause.addEventListener('click', togglePause);
  restore.addEventListener('click', openCall);
  minimize.addEventListener('click', () => minimizeCall());
  retry.addEventListener('click', start);
  for (const button of dialog.querySelectorAll('[data-call-end], [data-call-close]')) {
    button.addEventListener('click', () => hangup());
  }
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || event.defaultPrevented || event.target === language) return;
    event.preventDefault();
    minimizeCall();
  });
  new MutationObserver(() => {
    if (dialog.open || !dock.hidden) placeCallSurfaces();
  }).observe(document.body, { attributes: true, attributeFilter: ['open'], subtree: true });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && call?.local && !call.paused && call.context.state === 'suspended') {
      call.context.resume().catch(() => {});
    }
  });
  window.addEventListener('pagehide', () => hangup(false));
  window.openStorylensSupportCall = openCall;
  trigger.addEventListener('click', () => {
    if (window.parent !== window && window.frameElement?.dataset.tool === 'callQA' &&
        typeof window.parent.openStorylensSupportCall === 'function') {
      window.parent.openStorylensSupportCall();
    } else {
      openCall();
    }
  });
})();
