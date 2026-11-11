import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import Orb from "./Orb";
import SidePanel from "./SidePanel";
import { useVoicePipeline } from "./useVoicePipeline";
import { apiFetch } from "./api";
import { wantsScreenContext } from "./screenIntent";
import IntegrationsPanel from "./IntegrationsPanel";
import DraftCard from "./DraftCard";
import Workbench from "./Workbench";
import DocumentReminders from "./DocumentReminders";
import LocalResult from "./LocalResult";
import { stoppedDraft } from "./draftState";

const SESSION_ID = "default";
const REMINDER_POLL_MS = 20000;

const STATE_LABEL = {
  idle: "Standing by",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

const TABS = [
  { id: "workbench", label: "Workbench" },
  { id: "chat", label: "Chat" },
  { id: "memory", label: "Memory" },
  { id: "reminders", label: "Reminders" },
  { id: "audit", label: "Activity" },
  { id: "connect", label: "Connect" },
];

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [agentStatus, setAgentStatus] = useState("checking");
  const [statusDetail, setStatusDetail] = useState("Starting the local assistant…");
  const [runtime, setRuntime] = useState(null);
  const [settings, setSettings] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [screenContext, setScreenContext] = useState(null);
  const [capturing, setCapturing] = useState(false);
  const [locked, setLocked] = useState(false);
  const [tab, setTab] = useState("chat");
  const [panelKey, setPanelKey] = useState(0);
  const [draftOperations, setDraftOperations] = useState(0);
  const [draftStopping, setDraftStopping] = useState(false);
  const [draftSessionVersion, setDraftSessionVersion] = useState(0);
  const draftCancelRef = useRef(null);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  const voice = useVoicePipeline({
    sessionId: SESSION_ID,
    enabled: agentStatus === "online" && !locked && !draftOperations && !draftStopping,
    getRequestContext: async (text) => {
      const screenshotId = screenContext?.screenshot_id;
      if (screenshotId) { setScreenContext(null); return { screenshotId }; }
      if (window.cortana && wantsScreenContext(text)) {
        const capture = await window.cortana.captureScreen();
        return { screenshotId: capture.screenshot_id };
      }
      return {};
    },
    onTranscript: (text, spoken) => {
      setTab("chat");
      if (spoken) setInput((current) => current || text);
      setMessages((m) => [...m, { role: "user", text }]);
    },
    onReply: (text, toolsUsed, steps, pendingConfirmation, answeredBy, pendingDraft, spokenText) => {
      if (spokenText) setInput((current) => current === spokenText ? "" : current);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text,
          toolsUsed: toolsUsed?.length ? toolsUsed : undefined,
          steps: steps?.length ? steps : undefined,
          pendingConfirmation: pendingConfirmation || undefined,
          answeredBy,
          pendingDraft: pendingDraft || undefined,
        },
      ]);
      // A tool run may have changed memory/reminders — refresh the panels.
      if (toolsUsed?.length) setPanelKey((k) => k + 1);
    },
    onError: (msg) => setMessages((m) => [...m, { role: "system", text: msg }]),
  });

  const { speakText, stop } = voice;
  const greetedRef = useRef(false);
  useEffect(() => {
    if (agentStatus !== "online" || locked || greetedRef.current) return;
    greetedRef.current = true;
    setMessages((items) => [...items, { role: "assistant", text: "Hello Master Chief. I'm listening.", answeredBy: "local greeting" }]);
    speakText("Hello Master Chief. I'm listening.");
  }, [agentStatus, locked, speakText]);
  const onDraftBusyChange = useCallback((delta) => setDraftOperations((count) => Math.max(0, count + delta)), []);
  const invalidateDrafts = useCallback(() => {
    setDraftSessionVersion((version) => version + 1);
    setMessages((items) => items.map((item) => item.pendingDraft ? { ...item, pendingDraft: stoppedDraft(item.pendingDraft) } : item));
  }, []);
  const stopAll = useCallback(() => {
    window.dispatchEvent(new Event('cortana-stop-workbench'));
    apiFetch('/api/local/stop', {method:'POST'}).then(response => {
      if (!response.ok) throw new Error('Cortana did not acknowledge stopping the local workflow.');
      setMessages(items => items.map(item => item.pendingConfirmation && !item.pendingConfirmation.resolved
        ? {...item,pendingConfirmation:{...item.pendingConfirmation,resolved:true}} : item));
    }).catch(error => setMessages(items => [...items,{role:'system',text:error.message}]));
    stop();
    if (draftCancelRef.current || agentStatus !== "online" || locked) return;
    setDraftStopping(true);
    draftCancelRef.current = apiFetch("/api/drafts/cancel", { method: "POST" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not confirm that draft preparation stopped.");
        invalidateDrafts();
      })
      .catch((error) => setMessages((items) => [...items, { role: "system", text: error.message }]))
      .finally(() => { draftCancelRef.current = null; setDraftStopping(false); });
  }, [stop, agentStatus, locked, invalidateDrafts]);

  useEffect(() => {
    let cancelled = false;
    const bridge = window.cortana;
    if (!bridge) {
      queueMicrotask(() => {
        setAgentStatus("offline");
        setStatusDetail("Open Cortana using the desktop launcher. This browser preview cannot control your laptop.");
      });
      return;
    }
    function updateState(state) {
      if (cancelled) return;
      setAgentStatus(state.status === "ready" ? "online" : state.status === "starting" ? "starting" : "offline");
      setStatusDetail(state.detail);
    }
    async function checkStatus() {
      try {
        const state = await bridge.getState();
        updateState(state);
        if (state.status === "ready") {
          const r = await apiFetch("/api/status");
          if (!cancelled && r.ok) setRuntime(await r.json());
        }
      } catch { /* Backend is starting or Windows is locked. */ }
    }
    const unState = bridge.onState(updateState);
    const unError = bridge.onError((message) => setMessages((m) => [...m, { role: "system", text: message }]));
    const unScreen = bridge.onScreen((capture) => {
      setScreenContext(capture);
      setTab("chat");
      inputRef.current?.focus();
    });
    const unLock = bridge.onLocked((value) => { setLocked(value); if (value) { stop(); invalidateDrafts(); } });
    bridge.getSettings().then(setSettings).catch(() => {});
    checkStatus();
    const interval = setInterval(checkStatus, 10_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
      unState(); unError(); unScreen(); unLock();
    };
  }, [stop, invalidateDrafts]);

  // Poll for reminders that have come due and have Cortana announce them.
  // The agent marks each one announced as it hands it over, so a reminder
  // is spoken exactly once even if the window is reloaded.
  useEffect(() => {
    let cancelled = false;

    async function checkDue() {
      if (agentStatus !== "online" || voice.busy || locked) return;
      try {
        const r = await apiFetch("/api/reminders/due");
        if (!r.ok || cancelled) return;
        const { due } = await r.json();
        if (!due?.length) return;

        for (const item of due) {
          const line = `Reminder: ${item.text}`;
          setMessages((m) => [...m, { role: "assistant", text: line }]);
          await speakText(line);
        }
        setPanelKey((k) => k + 1);
      } catch {
        /* agent not up yet — try again next tick */
      }
    }

    const interval = setInterval(checkDue, REMINDER_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [speakText, agentStatus, voice.busy, locked]);

  useEffect(() => {
    if (tab === "chat") {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, tab]);

  // Esc anywhere cuts Cortana off mid-sentence — faster than reaching for
  // the button when she's reading out something long.
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") stopAll();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stopAll]);

  const sendTyped = useCallback(
    async (e) => {
      e.preventDefault();
      const text = input.trim();
      if (!text || sending || voice.busy || draftOperations || draftStopping || agentStatus !== "online") return;

      // The user bubble is added by runChatTurn -> onTranscript, the same
      // path push-to-talk uses. Adding it here too would duplicate it.
      setInput("");
      setSending(true);
      setTab("chat");
      try {
        await voice.sendTextMessage(text);
      } finally {
        setSending(false);
      }
    },
    [input, sending, voice, agentStatus, draftOperations, draftStopping]
  );

  async function captureScreen() {
    if (!window.cortana || capturing || voice.busy) return;
    setCapturing(true);
    try {
      const capture = await window.cortana.captureScreen();
      setScreenContext(capture);
      setTab("chat");
      inputRef.current?.focus();
    } catch (error) {
      setMessages((m) => [...m, { role: "system", text: error.message }]);
    } finally { setCapturing(false); }
  }

  async function changeSetting(key, value) {
    try { setSettings(await window.cortana.setSettings({ [key]: value })); }
    catch (error) { setMessages((m) => [...m, { role: "system", text: error.message }]); }
  }

  // Approve/Reject on a pending edit_code_file card. Marks that message's
  // card resolved (so the buttons disappear) and appends a follow-up
  // message with what actually happened — applying is a real filesystem
  // write, so this is the one place a failure needs its own message rather
  // than silently vanishing.
  const handleConfirm = useCallback(
    async (messageIndex, confirmationId, approve) => {
      setMessages((m) =>
        m.map((msg, i) =>
          i === messageIndex
            ? { ...msg, pendingConfirmation: { ...msg.pendingConfirmation, resolving: true } }
            : msg
        )
      );
      let outcomeText, workflowResult;
      try {
        const data = await voice.confirmAction(confirmationId, approve);
        workflowResult = data.result;
        outcomeText = approve
          ? data.result?.error
            ? `The action could not finish: ${data.result.error}`
            : data.result?.outcomes ? 'Workspace restore returned the results below. Check each item in its target application.'
            : 'The reviewed action returned the result below.'
          : "Cancelled — no change made.";
      } catch (e) {
        outcomeText = `Couldn't ${approve ? "apply" : "cancel"} that: ${e.message}`;
      }
      setMessages((m) => [
        ...m.map((msg, i) =>
          i === messageIndex
            ? { ...msg, pendingConfirmation: { ...msg.pendingConfirmation, resolving: false, resolved: true } }
            : msg
        ),
        { role: "assistant", text: outcomeText, workflowResult },
      ]);
      setPanelKey((k) => k + 1);
    },
    [voice]
  );

  const latestReply = [...messages].reverse().find((m) => m.role === "assistant");

  return (
    <div className="app">
      <div className="grid-bg" aria-hidden="true" />

      <header className="app-header">
        <div className="brand">
          <span className="dot" />
          <span className="brand-name">CORTANA</span>
        </div>
        <div className="header-right">
          <select aria-label="Speech language" value={voice.speechLanguage} onChange={(event) => voice.setSpeechLanguage(event.target.value)}>
            <option value="en">English</option>
            <option value="hi">Hindi</option>
            <option value="auto">Hindi + English / Hinglish</option>
          </select>
          {voice.state === "speaking" && <button className="header-button" onClick={voice.stopSpeaking}>Stop voice</button>}
          <button className="header-button" aria-pressed={!voice.wakeWordEnabled}
            onClick={() => voice.setWakeWordEnabled(!voice.wakeWordEnabled)}
            disabled={locked}
            title="Mic off stops capture and cancels the current voice task">
            {voice.wakeWordEnabled ? "Turn mic off" : "Turn mic on"}
          </button>
          {voice.wakeWordEnabled && voice.conversationOpen && (
            <span className="status status-live" title="Resumes listening after each reply. Use Mic off to end the conversation.">
              conversation on
            </span>
          )}
          <span className={`status status-${agentStatus}`}>{agentStatus}</span>
          <button className="header-button" onClick={() => setShowSettings(!showSettings)} aria-expanded={showSettings}>Settings</button>
          <button className="header-button" onClick={() => window.cortana?.hide()} title="Keep Cortana in the tray">Hide</button>
        </div>
      </header>
      <div className={`connection-bar ${agentStatus !== "online" ? "connection-warning" : ""}`} role="status">
        <span>{runtime?.model_work_paused
          ? "Voice and AI are waiting for StoryLens to release the GPU"
          : agentStatus === "online" && runtime?.brain?.available === false
          ? "Connected · local model needs setup; app and website shortcuts remain available"
          : agentStatus === "online" && runtime?.brain?.loaded === false
            ? runtime?.brain?.warmup === 'warming'
              ? "Connected · preparing local reasoning model"
              : "Connected · local model will load when needed"
            : statusDetail}</span>
        <span className="privacy-label">Local AI · Speech: {runtime?.speech?.device === 'cuda' ? 'GPU' : runtime?.speech?.device || 'starting'}{runtime?.speech?.warmup === 'warming' ? ' warming…' : ''} · English / हिन्दी / Hinglish</span>
      </div>
      {showSettings && (
        <section className="settings-panel" aria-label="Cortana settings">
          <label><input type="checkbox" checked={settings?.openAtLogin || false} disabled={!settings} onChange={(e) => changeSetting("openAtLogin", e.target.checked)} /> Start when I sign in to Windows</label>
          <label><input type="checkbox" checked={settings?.floatingButton !== false} disabled={!settings} onChange={(e) => changeSetting("floatingButton", e.target.checked)} /> Show the floating Cortana button</label>
          <p>Open or hide: <kbd>{settings?.shortcut || 'Use the floating button (shortcut unavailable)'}</kbd> · Ask about the screen: <kbd>{settings?.screenShortcut || 'Use the screen button (shortcut unavailable)'}</kbd></p>
          {runtime?.vision && <p>Vision model: {runtime.vision.model} · {runtime.vision.available ? (runtime.vision.loaded ? "Loaded locally" : "Ready to load locally") : "Not installed or unavailable"}</p>}
          <p>Conversation stays on and resumes listening after every reply. You do not need to repeat “Hey Cortana” or press a button for each question. Turn the mic off when talking to someone else; this releases the microphone. Your mic preference is remembered. Hold the mic button for a single request while background listening is off.</p>
          {runtime && <details><summary>Local readiness</summary><pre>{JSON.stringify(runtime, null, 2)}</pre></details>}
          <button className="header-button" onClick={() => window.cortana?.restart().catch((e) => setStatusDetail(e.message))}>Restart assistant</button>
          <button className="header-button" onClick={() => { setShowSettings(false); setTab("connect"); }}>Connect WhatsApp, Gmail &amp; Instagram</button>
        </section>
      )}

      <DocumentReminders enabled={agentStatus === "online" && !locked} onOpen={() => setTab('workbench')} />
      <div className="workspace">
        {/* LEFT — the orb and the single current caption. */}
        <section className="stage">
          <div className={`orb-wrap orb-${voice.state}`}>
            <span className="ring ring-1" />
            <span className="ring ring-2" />
            <Orb state={voice.state} analyser={voice.analyser} size={300} />
          </div>

          <div className={`state-pill state-pill-${voice.state}`}>
            <span className="state-dot" />
            {STATE_LABEL[voice.state]}
          </div>
          <p className="screen-hint" role="status">{voice.micActive
            ? `${voice.busy ? "Listening resumes after this reply" : "Conversation on · listening"} · ${voice.micLabel}`
            : voice.wakeWordEnabled ? "Microphone starting…" : "Mic off · background listening disabled"}</p>
          {voice.heardText && <p className="screen-hint">Heard: {voice.heardText}</p>}

          <div className="caption-box">
            {latestReply ? (
              <p className="caption-text">{latestReply.text}</p>
            ) : (
              <p className="caption-hint">
                Speak normally. Listening starts automatically and resumes after every reply.
                Choose your speech language above.
              </p>
            )}
          </div>

          {/* Interrupt button — only present when there's something to stop. */}
          <button
            className={`stop-btn ${voice.busy || draftOperations || draftStopping || messages.some(m=>m.pendingConfirmation && !m.pendingConfirmation.resolved) ? "stop-btn-on" : ""}`}
            onClick={stopAll}
            disabled={draftStopping || (!voice.busy && !draftOperations && !messages.some(m=>m.pendingConfirmation && !m.pendingConfirmation.resolved))}
            title="Stop the current task and draft preparation (Esc)"
          >
            <span className="stop-square" />
            {draftStopping ? "Stopping…" : "Stop"}
          </button>
          {voice.state === "speaking" && <button className="screen-button" onClick={voice.stopSpeaking}>Stop reading aloud</button>}
          <button className="screen-button" onClick={voice.startConversation}
            disabled={agentStatus !== "online" || locked || voice.busy || Boolean(draftOperations) || draftStopping}>
            Talk to Cortana
          </button>

          {voice.micError && <div className="mic-error">{voice.micError}</div>}
          <button className="screen-button" onClick={captureScreen} disabled={agentStatus !== "online" || capturing || voice.busy}>
            {capturing ? "Capturing your screen…" : "Ask about my screen"}
          </button>
          <p className="screen-hint">Cortana steps out of the way, captures this moment, and attaches it to your next question.</p>
        </section>

        {/* RIGHT — tabbed rail: conversation, memory, reminders, activity. */}
        <section className="rail">
          <nav className="rail-tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={`rail-tab ${tab === t.id ? "rail-tab-active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>

          <div className="rail-body">
            {tab === "chat" ? (
              <div className="chat-scroll" ref={scrollRef}>
                {voice.partialTranscript && <div className="voice-preview" role="status" aria-live="polite">
                  <small>Hearing you · provisional</small><p>{voice.partialTranscript}</p>
                </div>}
                {messages.length === 0 && <div className="panel-empty">Try “Open Chrome”, “YouTube kholo”, or attach your screen and ask about an error.</div>}
                {messages.map((m, i) => (
                  <div key={i} className={`row row-${m.role}`}>
                    <div className={`bubble bubble-${m.role}`}>
                      {m.text}
                      {m.workflowResult && <LocalResult result={m.workflowResult} />}
                      {m.answeredBy && <div className="answer-source">{m.answeredBy}</div>}
                      {m.pendingDraft && (
                        <DraftCard draft={m.pendingDraft} enabled={agentStatus === "online" && !locked && !voice.busy && !draftStopping}
                          onBusyChange={onDraftBusyChange}
                          onChange={(draft) => {
                            setMessages((items) => items.map((item, index) => index === i
                              ? { ...item, text: draft.note || item.text, pendingDraft: draft }
                              : item));
                            setPanelKey((key) => key + 1);
                          }} />
                      )}
                      {m.pendingConfirmation && (
                        <div className="confirm-card">
                          <pre className="confirm-diff">{typeof m.pendingConfirmation.preview === "string" ? m.pendingConfirmation.preview : JSON.stringify(m.pendingConfirmation.preview, null, 2)}</pre>
                          {m.pendingConfirmation.resolved ? (
                            <div className="confirm-done">Resolved.</div>
                          ) : (
                            <div className="confirm-actions">
                              <button
                                className="confirm-btn confirm-approve"
                                disabled={m.pendingConfirmation.resolving || locked || voice.busy || draftStopping}
                                onClick={() => handleConfirm(i, m.pendingConfirmation.id, true)}
                              >
                                Approve
                              </button>
                              <button
                                className="confirm-btn confirm-reject"
                                disabled={m.pendingConfirmation.resolving || locked || voice.busy || draftStopping}
                                onClick={() => handleConfirm(i, m.pendingConfirmation.id, false)}
                              >
                                Reject
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                      {m.steps && (
                        <div className="steps">
                          {m.steps.map((s, j) => (
                            <div key={j} className="step">
                              <span className="step-num">{s.round}</span>
                              <span className="step-tool">{s.tool}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {m.toolsUsed && !m.steps && (
                        <div className="bubble-tools">
                          {m.toolsUsed.map((t) => (
                            <span key={t} className="tool-chip">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : tab === "workbench" ? (
              <Workbench enabled={agentStatus === "online" && !locked && !voice.busy && !draftStopping} onBusyChange={onDraftBusyChange} />
            ) : tab === "connect" ? (
              <IntegrationsPanel enabled={agentStatus === "online" && !locked && !voice.busy && !draftStopping} refreshKey={panelKey} draftSessionVersion={draftSessionVersion} onBusyChange={onDraftBusyChange} />
            ) : (
              <SidePanel tab={tab} refreshKey={panelKey} />
            )}
          </div>

          {screenContext && <div className="screen-attached" role="status"><span>Screen captured · attached to your next question</span><button className="icon-btn" onClick={() => setScreenContext(null)} title="Remove screen capture">×</button></div>}
          <form className="composer" onSubmit={sendTyped}>
            <button
              type="button"
              className={`mic-btn ${voice.state === "listening" ? "mic-btn-active" : ""}`}
              onMouseDown={voice.pushToTalkStart}
              onMouseUp={voice.pushToTalkStop}
              onMouseLeave={(e) => e.buttons === 1 && voice.pushToTalkStop()}
              onTouchStart={voice.pushToTalkStart}
              onTouchEnd={voice.pushToTalkStop}
              disabled={agentStatus !== "online" || capturing || Boolean(draftOperations) || draftStopping}
              title="Hold to talk"
            >
              🎤
            </button>
            <input
              value={input || voice.partialTranscript}
              ref={inputRef}
              onChange={(e) => {
                if (voice.state === "speaking") voice.stopSpeaking();
                setInput(e.target.value);
              }}
              placeholder="Type a message, or hold the mic"
              disabled={(sending && voice.state !== "speaking") || agentStatus !== "online"}
            />
            <button type="submit" disabled={sending || voice.busy || Boolean(draftOperations) || draftStopping || !input.trim() || agentStatus !== "online"}>
              Ask
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}

export default App;
