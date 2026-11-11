import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { apiFetch } from "./api.js";
import { recordPcmClip, spokenSummary, speechQueue } from "./pcmCapture.js";
import { commandWindowOpen, addressedSpeech } from "./voiceAddressing.js";

const CHAT_TIMEOUT_MS = 180000;
const SPEECH_TIMEOUT_MS = 60000;
const WAKE_CHUNK_MS = 4000;
const COMMAND_RECORD_MS = 7000;
const MAX_PTT_MS = 30000;
const WAKE_STORAGE_KEY = "cortana.mic.enabled.v4";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const abortError = () => new DOMException("Stopped", "AbortError");

// Never discard short valid commands such as "yes", "no", "हाँ", "रुको".
// Silence suppression belongs to the acoustic model, not an English-only regex.
export function isUsableSpeech(text) {
  const value = (text || "").trim();
  return /[\p{L}\p{N}]/u.test(value);
}

/** Exactly one recorder, with a single settlement path for stop/error/abort. */
export function recordClip(stream, { signal, milliseconds = MAX_PTT_MS, Recorder = MediaRecorder } = {}) {
  const recorder = new Recorder(stream);
  let timer;
  let settled = false;
  let resolveResult;
  let rejectResult;
  const chunks = [];
  const promise = new Promise((resolve, reject) => { resolveResult = resolve; rejectResult = reject; });
  // Cancellation can happen during a pointer event before the consumer awaits.
  promise.catch(() => {});
  function settle(error) {
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
    recorder.ondataavailable = null;
    recorder.onstop = null;
    recorder.onerror = null;
    if (error) rejectResult(error);
    else resolveResult(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
  }
  function finish() {
    if (settled) return;
    try {
      if (recorder.state !== "inactive") recorder.stop();
      else settle();
    } catch (error) { settle(error); }
  }
  function cancel() {
    if (settled) return;
    // Detach handlers before stop: its eventual event must never submit stale audio.
    settle(abortError());
    try { if (recorder.state !== "inactive") recorder.stop(); } catch { /* already cancelled */ }
  }
  recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
  recorder.onstop = () => settle(signal?.aborted ? abortError() : undefined);
  recorder.onerror = (event) => {
    settle(event.error || new Error("The microphone recording failed."));
    if (recorder.state !== "inactive") recorder.stop();
  };
  if (signal?.aborted) cancel();
  else {
    signal?.addEventListener("abort", cancel, { once: true });
    try {
      recorder.start();
      timer = setTimeout(finish, milliseconds);
    } catch (error) { settle(error); }
  }
  return { recorder, promise, finish, cancel };
}

export function useVoicePipeline({ sessionId, onTranscript, onReply, onError, onStatus, getRequestContext, enabled = true }) {
  const [state, setState] = useState("idle");
  const [wakeWordEnabled, setWakeState] = useState(() => {
    if (window.cortana?.startMuted) {
      try { localStorage.setItem(WAKE_STORAGE_KEY, "false"); } catch { /* unavailable */ }
      return false;
    }
    try { return localStorage.getItem(WAKE_STORAGE_KEY) !== "false"; } catch { return true; }
  });
  const [speechLanguage, setSpeechLanguageState] = useState(() => {
    // Migrate the old English-only default once; the owner's speech is Hinglish.
    if (!localStorage.getItem("cortana.speech.language.v2")) {
      localStorage.setItem("cortana.speech.language", "auto");
      localStorage.setItem("cortana.speech.language.v2", "1");
    }
    return localStorage.getItem("cortana.speech.language") || "auto";
  });
  const [conversationOpen, setConversationOpen] = useState(wakeWordEnabled);
  const [pttRecording, setPttRecording] = useState(false);
  const [micError, setMicError] = useState(null);
  const [micAnalyser, setMicAnalyser] = useState(null);
  const [speechAnalyser, setSpeechAnalyser] = useState(null);
  const [micActive, setMicActive] = useState(false);
  const [micLabel, setMicLabel] = useState("");
  const [heardText, setHeardText] = useState("");
  const [partialTranscript, setPartialTranscript] = useState("");
  const optionsRef = useRef({});
  useLayoutEffect(() => {
    optionsRef.current = { sessionId, onTranscript, onReply, onError, onStatus, getRequestContext, enabled, wakeWordEnabled, speechLanguage };
  });
  const mountedRef = useRef(true);
  const operationRef = useRef(null);
  const recorderRef = useRef(null);
  const speechQueueRef = useRef(null);
  const pttRef = useRef(null);
  const streamRef = useRef(null);
  const streamPromiseRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micSourceRef = useRef(null);
  const micAnalyserRef = useRef(null);
  const analyserRef = useRef(null);
  const playbackRef = useRef(null);
  const conversationRef = useRef({ open: wakeWordEnabled, continuous: true, expiresAt: Infinity });
  const announcementsRef = useRef([]);
  const previewRef = useRef(null);
  const methodsRef = useRef({});

  const updateState = useCallback((next) => {
    if (!mountedRef.current) return;
    setState(next);
    optionsRef.current.onStatus?.(next);
  }, []);
  const reportError = useCallback((error) => {
    if (mountedRef.current && error?.name !== "AbortError") {
      optionsRef.current.onError?.(error?.message || String(error));
    }
  }, []);
  const closeConversation = useCallback(() => {
    conversationRef.current = { open: false, expiresAt: 0 };
    if (mountedRef.current) setConversationOpen(false);
  }, []);
  const openConversation = useCallback(() => {
    conversationRef.current = { open: true, continuous: true, expiresAt: Infinity };
    if (mountedRef.current) setConversationOpen(true);
  }, []);
  const releaseStream = useCallback(() => {
    previewRef.current?.abort();
    previewRef.current = null;
    if (mountedRef.current) setPartialTranscript("");
    speechQueueRef.current?.close();
    speechQueueRef.current = null;
    recorderRef.current?.clip.cancel();
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    micSourceRef.current?.disconnect();
    micSourceRef.current = null;
    micAnalyserRef.current = null;
    if (mountedRef.current) setMicAnalyser(null);
    if (mountedRef.current) setMicActive(false);
  }, []);
  const isCurrent = useCallback((operation) => (
    mountedRef.current && operationRef.current === operation && !operation.controller.signal.aborted
  ), []);
  const cancelBackend = useCallback((operation) => {
    if (operation?.requestId) {
      apiFetch(`/api/tasks/${operation.requestId}/cancel`, { method: "POST" }).catch(() => {});
    }
  }, []);
  const cancelOperation = useCallback((operation) => {
    if (!operation) return;
    operation.controller.abort();
    cancelBackend(operation);
    if (recorderRef.current?.operation === operation) {
      recorderRef.current.clip.cancel();
      recorderRef.current = null;
    }
    if (playbackRef.current?.operation === operation) playbackRef.current.stop();
    if (operationRef.current === operation) operationRef.current = null;
    if (pttRef.current?.operation === operation) { pttRef.current = null; setPttRecording(false); }
  }, [cancelBackend]);
  const finishOperation = useCallback((operation) => {
    if (operationRef.current !== operation) return;
    operationRef.current = null;
    if (pttRef.current?.operation === operation) { pttRef.current = null; setPttRecording(false); }
    if (optionsRef.current.wakeWordEnabled) openConversation();
    updateState("idle");
    if (!optionsRef.current.wakeWordEnabled) releaseStream();
  }, [releaseStream, updateState, openConversation]);
  const beginOperation = useCallback((kind) => {
    if (!optionsRef.current.enabled) throw new Error("Cortana is still starting. Wait for the agent to be ready.");
    const previous = operationRef.current;
    if (previous) {
      if (previous.kind === "wake" && kind !== "wake") cancelOperation(previous);
      else return null;
    }
    const operation = { kind, controller: new AbortController(), requestId: null };
    operationRef.current = operation;
    return operation;
  }, [cancelOperation]);

  async function ensureStream(operation) {
    if (!streamRef.current?.getTracks().some((track) => track.readyState === "live")) {
      releaseStream();
      if (!streamPromiseRef.current) {
        streamPromiseRef.current = navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }).then((stream) => {
          // A user can mute while the OS is still granting microphone access.
          if (!isCurrent(operation)) {
            stream.getTracks().forEach((track) => track.stop());
            throw abortError();
          }
          streamRef.current = stream;
          return stream;
        }).finally(() => { streamPromiseRef.current = null; });
      }
      await streamPromiseRef.current;
    }
    if (!isCurrent(operation)) {
      if (!operationRef.current) releaseStream();
      throw abortError();
    }
    if (!micAnalyserRef.current) {
      const context = audioCtxRef.current ||= new (window.AudioContext || window.webkitAudioContext)();
      await context.resume();
      if (!isCurrent(operation)) throw abortError();
      const source = context.createMediaStreamSource(streamRef.current);
      const analyser = context.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      micSourceRef.current = source;
      micAnalyserRef.current = analyser;
      setMicAnalyser(analyser);
    }
    setMicError(null);
    setMicActive(true);
    setMicLabel(streamRef.current.getAudioTracks()[0]?.label || "Default microphone");
    return streamRef.current;
  }

  async function capture(operation, milliseconds) {
    const stream = await ensureStream(operation);
    if (!isCurrent(operation)) throw abortError();
    if (operation.kind === "wake") {
      speechQueueRef.current ||= speechQueue(stream, audioCtxRef.current);
      return speechQueueRef.current.next(operation.controller.signal, milliseconds);
    }
    recorderRef.current?.clip.cancel();
    const clip = recordPcmClip(stream, audioCtxRef.current, {
      signal: operation.controller.signal, milliseconds, endOnSilence: operation.kind === "wake",
    });
    recorderRef.current = { operation, clip };
    if (pttRef.current?.operation === operation) {
      pttRef.current.clip = clip;
      if (pttRef.current.released) clip.finish();
    }
    try { return await clip.promise; }
    finally {
      if (recorderRef.current?.clip === clip) recorderRef.current = null;
    }
  }

  async function requestJson(path, init, operation, timeout = SPEECH_TIMEOUT_MS) {
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      operation.controller.abort();
      cancelBackend(operation);
    }, timeout);
    try {
      const response = await apiFetch(path, { ...init, signal: operation.controller.signal });
      const data = await response.json().catch(() => ({}));
      if (!isCurrent(operation)) throw abortError();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Cortana returned ${response.status}.`);
      return data;
    } catch (error) {
      if (timedOut) throw new Error(`Cortana did not finish within ${timeout / 1000} seconds. Try again; the pending task was stopped.`);
      throw error;
    } finally { clearTimeout(timer); }
  }

  async function transcribe(blob, operation, wake = false) {
    if (!blob) return wake ? { detected: false, transcript: "", remainder: "" } : { text: "" };
    previewRef.current?.abort();
    const form = new FormData();
    form.append("audio", blob, blob.type === "audio/wav" ? "audio.wav" : "audio.webm");
    form.append("language", optionsRef.current.speechLanguage);
    const result = await requestJson(wake ? "/api/wake-check" : "/api/stt", { method: "POST", body: form }, operation)
      .finally(() => { if (isCurrent(operation)) setPartialTranscript(""); });
    if (mountedRef.current) setMicError(null);
    if (!wake && mountedRef.current && result.text) setHeardText(result.text);
    return result;
  }

  async function speakForOperation(text, operation) {
    operation.speechController = new AbortController();
    const speechSignal = AbortSignal.any([operation.controller.signal, operation.speechController.signal]);
    let objectUrl;
    let source;
    let analyser;
    let audio;
    let timer;
    let timedOut = false;
    try {
      updateState("speaking");
      timer = setTimeout(() => {
        timedOut = true;
        operation.controller.abort();
      }, SPEECH_TIMEOUT_MS);
      const response = await apiFetch("/api/tts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: spokenSummary(text) }), signal: speechSignal,
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Voice playback failed. The reply is available as text.");
      }
      const blob = await response.blob();
      clearTimeout(timer);
      if (!isCurrent(operation) || speechSignal.aborted) throw abortError();
      objectUrl = URL.createObjectURL(blob);
      audio = new Audio(objectUrl);
      const context = audioCtxRef.current ||= new (window.AudioContext || window.webkitAudioContext)();
      await context.resume();
      if (!isCurrent(operation) || speechSignal.aborted) throw abortError();
      source = context.createMediaElementSource(audio);
      analyser = context.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      analyser.connect(context.destination);
      analyserRef.current = analyser;
      setSpeechAnalyser(analyser);
      updateState("speaking");
      speechQueueRef.current?.pause(true);
      await new Promise((resolve, reject) => {
        const stopAudio = () => { audio.pause(); resolve(); };
        playbackRef.current = { operation, stop: stopAudio };
        audio.onended = resolve;
        audio.onerror = () => reject(new Error("Audio playback failed. The reply is available as text."));
        audio.play().catch(reject);
      });
    } catch (error) {
      if (timedOut && operationRef.current === operation) {
        reportError(new Error("Voice synthesis timed out. The reply is available as text."));
      } else if (isCurrent(operation) && !speechSignal.aborted) reportError(error);
    } finally {
      clearTimeout(timer);
      audio?.pause();
      speechQueueRef.current?.pause(false);
      source?.disconnect();
      analyser?.disconnect();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      if (analyserRef.current === analyser) analyserRef.current = null;
      if (mountedRef.current) setSpeechAnalyser(null);
      if (playbackRef.current?.operation === operation) playbackRef.current = null;
    }
  }

  async function chatWithOperation(text, operation, options = {}) {
    if (!isCurrent(operation)) return;
    operation.kind = "chat";
    operation.requestId = crypto.randomUUID();
    optionsRef.current.onTranscript?.(text, options.spoken);
    updateState("thinking");
    const context = await optionsRef.current.getRequestContext?.(text) || {};
    const screenshotId = options.screenshotId || context.screenshotId;
    if (!isCurrent(operation)) return;
    const data = await requestJson("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text, session_id: optionsRef.current.sessionId,
        input_mode: options.spoken ? 'voice' : 'text',
        request_id: operation.requestId, ...(screenshotId ? { screenshot_id: screenshotId } : {}),
      }),
    }, operation, CHAT_TIMEOUT_MS);
    if (!isCurrent(operation)) return;
    optionsRef.current.onReply?.(data.reply, data.tools_used || [], data.steps || [], data.pending_confirmation || null, data.answered_by || "local", data.pending_draft || null, options.spoken ? text : null);
    await speakForOperation(data.reply, operation);
  }

  async function sendTextMessage(text, options = {}) {
    let operation;
    try {
      operation = beginOperation("chat");
      if (!operation) throw new Error("Cortana is handling a request. Press Stop before starting another.");
      await chatWithOperation(text, operation, options);
    } catch (error) { reportError(error); }
    finally { if (operation) finishOperation(operation); }
  }

  async function pushToTalkStart(event) {
    event?.preventDefault?.();
    if (pttRef.current) return;
    let operation;
    try {
      operation = beginOperation("ptt");
      if (!operation) return;
      closeConversation();
      speechQueueRef.current?.close();
      speechQueueRef.current = null;
      pttRef.current = { operation, clip: null, released: false };
      setPttRecording(true);
      updateState("listening");
      const blob = await capture(operation, MAX_PTT_MS);
      if (!isCurrent(operation)) return;
      updateState("thinking");
      const { text } = await transcribe(blob, operation);
      if (!isUsableSpeech(text)) throw new Error("I did not catch that. Try speaking closer to the microphone.");
      await chatWithOperation(text, operation, { spoken: true });
    } catch (error) {
      if (error.name === "NotAllowedError" || error.name === "NotFoundError") setMicError(error.message);
      reportError(error);
    } finally { if (operation) finishOperation(operation); }
  }
  function pushToTalkStop(event) {
    event?.preventDefault?.();
    if (!pttRef.current) return;
    // Releasing while Windows' mic prompt is still open must also end the recording.
    pttRef.current.released = true;
    pttRef.current.clip?.finish();
  }

  const stop = useCallback(() => {
    cancelOperation(operationRef.current);
    if (optionsRef.current.wakeWordEnabled) openConversation();
    else closeConversation();
    announcementsRef.current.splice(0).forEach((item) => item.resolve(false));
    releaseStream();
    updateState("idle");
  }, [cancelOperation, closeConversation, openConversation, releaseStream, updateState]);
  const stopSpeaking = useCallback(() => {
    const operation = operationRef.current;
    operation?.speechController?.abort();
    playbackRef.current?.stop();
    announcementsRef.current.splice(0).forEach((item) => item.resolve(false));
    updateState("idle");
  }, [updateState]);
  const setSpeechLanguage = useCallback((value) => {
    if (!["en", "hi", "auto"].includes(value)) return;
    localStorage.setItem("cortana.speech.language", value);
    setSpeechLanguageState(value);
  }, []);
  const startConversation = useCallback(() => {
    if (!optionsRef.current.enabled) return;
    // Conversation stays active until the owner explicitly turns the mic off.
    cancelOperation(operationRef.current);
    releaseStream();
    openConversation();
    optionsRef.current.wakeWordEnabled = true;
    setWakeState(true);
    localStorage.setItem(WAKE_STORAGE_KEY, "true");
    updateState("idle");
  }, [cancelOperation, releaseStream, updateState, openConversation]);
  const setWakeWordEnabled = useCallback((next) => {
    const value = typeof next === "function" ? next(optionsRef.current.wakeWordEnabled) : Boolean(next);
    try { localStorage.setItem(WAKE_STORAGE_KEY, String(value)); } catch { /* preference storage can be unavailable */ }
    setWakeState(value);
    optionsRef.current.wakeWordEnabled = value;
    if (value) openConversation();
    if (!value) {
      closeConversation();
      cancelOperation(operationRef.current);
      announcementsRef.current.splice(0).forEach((item) => item.resolve(false));
      releaseStream();
      setHeardText("");
      updateState("idle");
    }
  }, [cancelOperation, closeConversation, openConversation, releaseStream, updateState]);
  const confirmAction = useCallback(async (confirmationId, approve) => {
    const response = await apiFetch(`/api/confirm/${confirmationId}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approve }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Confirmation failed: ${response.status}`);
    return data;
  }, []);
  const speakText = useCallback((text) => new Promise((resolve) => {
    if (announcementsRef.current.length >= 10) { resolve(false); return; }
    announcementsRef.current.push({ text, resolve });
  }), []);

  useLayoutEffect(() => {
    methodsRef.current = { capture, transcribe, chatWithOperation, speakForOperation, sendTextMessage, pushToTalkStart, pushToTalkStop };
  });

  // Display provisional speech while the utterance is still being captured.
  // Preview text never reaches /chat or authorizes any action.
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const timer = setInterval(async () => {
      const operation = operationRef.current;
      if (!operation || !['wake', 'ptt'].includes(operation.kind) || previewRef.current) return;
      const ptt = operation.kind === 'ptt';
      const snapshot = ptt ? recorderRef.current?.clip.snapshot() : speechQueueRef.current?.snapshot();
      if (!snapshot) return;
      const controller = new AbortController();
      previewRef.current = controller;
      const abortPreview = () => controller.abort();
      operation.controller.signal.addEventListener('abort', abortPreview, { once: true });
      const timeout = setTimeout(abortPreview, 3000);
      try {
        const form = new FormData();
        form.append('audio', ptt ? snapshot : snapshot.blob, 'preview.wav');
        form.append('language', optionsRef.current.speechLanguage);
        const response = await apiFetch('/api/stt-preview', { method: 'POST', body: form, signal: controller.signal });
        const result = await response.json();
        if (!response.ok || cancelled || controller.signal.aborted || !isCurrent(operation)) return;
        const sameUtterance = ptt ? Boolean(recorderRef.current?.clip.snapshot())
          : speechQueueRef.current?.snapshot()?.id === snapshot.id;
        if (!sameUtterance) return;
        const addressed = ptt || commandWindowOpen(conversationRef.current) || result.detected;
        if (addressed) setPartialTranscript(result.detected ? result.remainder || 'Hey Cortana…' : result.text);
      } catch { /* Provisional feedback must never stop the final recognizer. */ }
      finally {
        clearTimeout(timeout);
        operation.controller.signal.removeEventListener('abort', abortPreview);
        if (previewRef.current === controller) previewRef.current = null;
      }
    }, 1200);
    return () => { cancelled = true; clearInterval(timer); previewRef.current?.abort(); };
  }, [enabled, isCurrent]);

  // Losing the backend or locking Windows releases the device immediately,
  // while preserving the user's opt-in wake preference for the next ready state.
  useEffect(() => {
    if (!enabled) {
      cancelOperation(operationRef.current);
      releaseStream();
      closeConversation();
      updateState("idle");
    } else if (wakeWordEnabled) openConversation();
  }, [enabled, wakeWordEnabled, cancelOperation, releaseStream, closeConversation, openConversation, updateState]);

  // One loop owns wake capture; user commands preempt its current recording safely.
  useEffect(() => {
    if (!enabled || !wakeWordEnabled) return;
    let cancelled = false;
    let failures = 0;
    async function run() {
      while (!cancelled) {
        if (operationRef.current || announcementsRef.current.length) { await delay(150); continue; }
        let operation;
        try {
          operation = beginOperation("wake");
          if (!operation) continue;
          const active = commandWindowOpen(conversationRef.current);
          if (!active && conversationRef.current.open) closeConversation();
          updateState(active ? "listening" : "idle");
          const windowRemaining = conversationRef.current.expiresAt - Date.now();
          const blob = await methodsRef.current.capture(operation, active
            ? Math.max(1, Math.min(COMMAND_RECORD_MS, windowRemaining)) : WAKE_CHUNK_MS);
          if (cancelled || !isCurrent(operation)) continue;
          // Wake-check also returns the transcript. Always spot a leading wake
          // phrase, including during a bounded command window.
          const result = await methodsRef.current.transcribe(blob, operation, true);
          if (cancelled || !isCurrent(operation)) continue;
          failures = 0;
          const command = addressedSpeech(result, active);
          if (result.detected && !isUsableSpeech(command)) {
            speechQueueRef.current?.pause(true);
            optionsRef.current.onReply?.("Hello Master Chief.", [], [], null, "local greeting", null);
            await methodsRef.current.speakForOperation("Hello Master Chief.", operation);
            if (!isCurrent(operation)) continue;
            openConversation();
          } else if (isUsableSpeech(command)) {
            // Keep the conversation active across replies. Mic off is the
            // explicit boundary when the owner addresses another application.
            setHeardText(command);
            speechQueueRef.current?.pause(true);
            await methodsRef.current.chatWithOperation(command, operation, { spoken: true });
            speechQueueRef.current?.pause(false);
          }
        } catch (error) {
          if (!cancelled && error.name !== "AbortError") {
            failures += 1;
            if (failures === 1) reportError(error);
            setMicError("Microphone retrying: " + (error.message || "audio unavailable"));
            // A transient decoder/device failure must never silently turn the
            // owner's automatic-listening preference off.
            await delay(Math.min(5000, 1000 * failures));
          }
        } finally {
          speechQueueRef.current?.pause(false);
          if (operation) finishOperation(operation);
        }
      }
    }
    run();
    return () => {
      cancelled = true;
      if (operationRef.current?.kind === "wake") cancelOperation(operationRef.current);
    };
  }, [enabled, wakeWordEnabled, beginOperation, cancelOperation, closeConversation, openConversation, finishOperation, isCurrent, reportError, setWakeWordEnabled, updateState]);

  // Greetings and reminders wait for the current task; never speak over a command.
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(async () => {
      if (!announcementsRef.current.length || (operationRef.current && operationRef.current.kind !== "wake")) return;
      const item = announcementsRef.current.shift();
      const operation = beginOperation("announcement");
      if (!operation) { announcementsRef.current.unshift(item); return; }
      try {
        await methodsRef.current.speakForOperation(item.text, operation);
        item.resolve(isCurrent(operation));
      } finally { finishOperation(operation); }
    }, 200);
    return () => clearInterval(timer);
  }, [enabled, beginOperation, finishOperation, isCurrent]);

  useEffect(() => {
    mountedRef.current = true;
    const announcements = announcementsRef.current;
    return () => {
      mountedRef.current = false;
      cancelOperation(operationRef.current);
      announcements.splice(0).forEach((item) => item.resolve(false));
      releaseStream();
      audioCtxRef.current?.close();
      audioCtxRef.current = null;
    };
  }, [cancelOperation, releaseStream]);

  return {
    state: state === "idle" && conversationOpen ? "listening" : state,
    analyser: state === "listening" || (state === "idle" && micActive) ? micAnalyser : speechAnalyser,
    micActive, micLabel, heardText, partialTranscript, startConversation,
    wakeWordEnabled, setWakeWordEnabled, conversationOpen, micError, speechLanguage, setSpeechLanguage, stopSpeaking,
    pushToTalkStart: useCallback((...args) => methodsRef.current.pushToTalkStart(...args), []),
    pushToTalkStop: useCallback((...args) => methodsRef.current.pushToTalkStop(...args), []),
    sendTextMessage: useCallback((...args) => methodsRef.current.sendTextMessage(...args), []),
    speakText, confirmAction, stop,
    busy: state === 'thinking' || state === 'speaking' || pttRecording,
  };
}
