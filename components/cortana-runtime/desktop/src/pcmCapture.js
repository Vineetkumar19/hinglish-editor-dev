// Record standalone PCM WAVs, so a released/short recording never depends on
// asynchronous WebM headers or a final encoder chunk.
export function wavBlob(chunks, rate) {
  const length = chunks.reduce((n, chunk) => n + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(buffer);
  const word = (at, text) => [...text].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
  word(0, "RIFF"); view.setUint32(4, buffer.byteLength - 8, true); word(8, "WAVE");
  word(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  word(36, "data"); view.setUint32(40, length * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const value of chunk) {
    view.setInt16(offset, Math.max(-32768, Math.min(32767, Math.round(value * 32767))), true);
    offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export function recordPcmClip(stream, context, { signal, milliseconds = 30000, endOnSilence = false } = {}) {
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(2048, 1, 1);
  const mute = context.createGain();
  mute.gain.value = 0;
  source.connect(processor); processor.connect(mute); mute.connect(context.destination);
  let resolve, reject, timer, finishTimer, settled = false, length = 0, voiced = 0, quiet = 0;
  const chunks = [];
  const started = Date.now();
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  promise.catch(() => {});
  const cleanup = () => {
    clearTimeout(timer); clearTimeout(finishTimer); signal?.removeEventListener("abort", cancel);
    processor.onaudioprocess = null; source.disconnect(); processor.disconnect(); mute.disconnect();
  };
  function finish() {
    if (settled) return;
    // Pointer release while device startup is pending must still yield audio.
    if (length < context.sampleRate * .3) {
      if (Date.now() - started > milliseconds + 1500) {
        settled = true; cleanup(); reject(new Error("The microphone returned no audio. Select a working input device."));
        return;
      }
      finishTimer ||= setTimeout(() => { finishTimer = null; finish(); }, 100);
      return;
    }
    settled = true; cleanup(); resolve(wavBlob(chunks, context.sampleRate));
  }
  function cancel() {
    if (settled) return;
    settled = true; cleanup(); reject(new DOMException("Stopped", "AbortError"));
  }
  processor.onaudioprocess = (event) => {
    const samples = new Float32Array(event.inputBuffer.getChannelData(0));
    chunks.push(samples); length += samples.length;
    const rms = Math.sqrt(samples.reduce((total, x) => total + x * x, 0) / samples.length);
    if (rms > .012) { voiced += samples.length; quiet = 0; }
    else quiet += samples.length;
    if (endOnSilence && voiced > context.sampleRate * .2 && quiet > context.sampleRate * .85) finish();
  };
  if (signal?.aborted) cancel();
  else {
    signal?.addEventListener("abort", cancel, { once: true });
    timer = setTimeout(finish, milliseconds);
  }
  return { promise, finish, cancel,
    snapshot: () => !settled && length > context.sampleRate * .4 ? wavBlob(chunks, context.sampleRate) : null,
  };
}

export function spokenSummary(text) {
  const clean = text.replace(/```[\s\S]*?```/g, "Code is shown on screen.").replace(/[*#`]/g, "").trim();
  const indexed = clean.match(/^Indexed (\d+) pages\/sections from /);
  if (indexed) return `Indexed ${indexed[1]} ${indexed[1] === '1' ? 'page or section' : 'pages or sections'}. The source details are on screen.`;
  if (clean.length <= 300) return clean;
  const sentences = clean.match(/[^.!?।]+[.!?।]+(?:\s|$)/g) || [];
  const short = sentences.slice(0, 2).join(" ").trim();
  if (short && short.length <= 340) return short;
  return clean.slice(0, 280).replace(/\s+\S*$/, "") + ". The full answer is on screen.";
}

// Keep collecting complete utterances while the recognizer/model is busy.
// The old record -> stop -> decode loop lost speech during every decode gap.
export function speechQueue(stream, context) {
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(2048, 1, 1);
  const mute = context.createGain(); mute.gain.value = 0;
  source.connect(processor); processor.connect(mute); mute.connect(context.destination);
  const queue = [];
  let waiter = null, chunks = [], pre = [], size = 0, quiet = 0, voiced = 0, paused = false, closed = false, utterance = 0;
  const reset = () => { chunks = []; size = quiet = voiced = 0; pre = []; };
  const deliver = (blob) => {
    if (waiter) { const current = waiter; waiter = null; current.done(blob); }
    else { if (queue.length >= 3) queue.shift(); queue.push(blob); }
  };
  processor.onaudioprocess = (event) => {
    if (paused || closed) return;
    const samples = new Float32Array(event.inputBuffer.getChannelData(0));
    const rms = Math.sqrt(samples.reduce((total, x) => total + x * x, 0) / samples.length);
    const speech = rms > .009;
    if (!chunks.length) {
      if (!speech) { pre.push(samples); if (pre.length > 7) pre.shift(); return; }
      chunks = [...pre]; pre = []; size = chunks.reduce((total, x) => total + x.length, 0);
      utterance += 1;
    }
    chunks.push(samples); size += samples.length;
    if (speech) { voiced += samples.length; quiet = 0; } else quiet += samples.length;
    if (quiet > context.sampleRate * .85 || size > context.sampleRate * 25) {
      if (voiced > context.sampleRate * .18) deliver(wavBlob(chunks, context.sampleRate));
      reset();
    }
  };
  return {
    snapshot() {
      return !closed && !paused && voiced > context.sampleRate * .35
        ? { id: utterance, blob: wavBlob(chunks, context.sampleRate) } : null;
    },
    pause(value) { paused = value; reset(); if (value) queue.splice(0); },
    close() {
      closed = true; processor.onaudioprocess = null;
      source.disconnect(); processor.disconnect(); mute.disconnect();
      queue.splice(0); waiter?.cancel(); waiter = null;
    },
    next(signal, timeout = 7000) {
      if (signal.aborted || closed) return Promise.reject(new DOMException("Stopped", "AbortError"));
      if (queue.length) return Promise.resolve(queue.shift());
      return new Promise((resolve, reject) => {
        let timer;
        const clean = () => { clearTimeout(timer); signal.removeEventListener("abort", cancel); if (waiter?.cancel === cancel) waiter = null; };
        const done = (blob) => { clean(); resolve(blob); };
        const cancel = () => { clean(); reject(new DOMException("Stopped", "AbortError")); };
        const expire = () => { if (chunks.length) timer = setTimeout(expire, 1000); else done(null); };
        waiter = { done, cancel };
        signal.addEventListener("abort", cancel, { once: true });
        timer = setTimeout(expire, timeout);
      });
    },
  };
}
