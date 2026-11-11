import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "./api";
import DraftCard from "./DraftCard";
import { PLATFORMS, connectionLabel, draftRequest, platformInfo, stoppedDraft } from "./draftState";

export default function IntegrationsPanel({ enabled = true, refreshKey = 0, draftSessionVersion = 0, onBusyChange }) {
  const [integrations, setIntegrations] = useState([]);
  const [browserNote, setBrowserNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [opening, setOpening] = useState("");
  const [error, setError] = useState("");
  const [platform, setPlatform] = useState("whatsapp");
  const [recipient, setRecipient] = useState("");
  const [body, setBody] = useState("");
  const [subject, setSubject] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [draft, setDraft] = useState(null);
  const sessionVersionRef = useRef(draftSessionVersion);
  useEffect(() => {
    if (sessionVersionRef.current === draftSessionVersion) return;
    sessionVersionRef.current = draftSessionVersion;
    queueMicrotask(() => setDraft(stoppedDraft));
  }, [draftSessionVersion]);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    onBusyChange?.(1);
    setError("");
    try {
      const response = await apiFetch("/api/integrations/status");
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not check app connections.");
      setIntegrations(Array.isArray(data.integrations) ? data.integrations : []);
      setBrowserNote(data.browser?.note || "");
    } catch (e) { setError(e.name === "AbortError" ? "Connection check stopped." : e.message); }
    finally { setLoading(false); onBusyChange?.(-1); }
  }, [enabled, onBusyChange]);

  useEffect(() => { queueMicrotask(load); }, [load, refreshKey]);

  async function open(id) {
    if (!enabled || opening) return;
    setOpening(id);
    onBusyChange?.(1);
    setError("");
    try {
      const response = await apiFetch(`/api/integrations/${id}/open`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not open the app.");
      setIntegrations((items) => [...items.filter((item) => item.platform !== id), { ...result, platform: id }]);
      if (result.status === "error") setError(result.note || "The app could not be opened.");
    } catch (e) { setError(e.name === "AbortError" ? "Opening stopped." : e.message); }
    finally { setOpening(""); onBusyChange?.(-1); }
  }

  async function prepare(event) {
    event.preventDefault();
    if (!enabled || preparing) return;
    setError("");
    let payload;
    try { payload = draftRequest({ platform, recipient, body, subject }); }
    catch (e) { setError(e.message); return; }
    setPreparing(true);
    onBusyChange?.(1);
    try {
      const response = await apiFetch("/api/drafts/prepare", { method: "POST", body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not prepare the draft.");
      setDraft({ platform, ...result });
    } catch (e) { setError(e.name === "AbortError" ? "Draft preparation stopped. Check the app for any text already entered." : e.message); }
    finally { setPreparing(false); onBusyChange?.(-1); }
  }

  return (
    <div className="integrations-panel">
      <div className="connect-heading">
        <div><h2>Your apps</h2><p>Installed apps first. Gmail and website fallbacks use your normal Chrome and existing logins.</p></div>
        <button className="header-button" disabled={!enabled || loading || Boolean(opening)} onClick={load}>{loading ? "Checking…" : "Check status"}</button>
      </div>
      <div className="integration-cards">
        {PLATFORMS.map((item) => {
          const connection = integrations.find((entry) => entry.platform === item.id);
          return (
            <article className="integration-card" key={item.id}>
              <span className={`platform-icon platform-${item.id}`}>{item.initials}</span>
              <div className="integration-info"><strong>{item.label}</strong><span className={`integration-status integration-${connection?.status || "unknown"}`}>{connectionLabel(connection?.status)}</span></div>
              <button className="header-button" disabled={!enabled || Boolean(opening)} onClick={() => open(item.id)}>
                {opening === item.id ? "Opening…" : `Open ${item.label}`}
              </button>
              {connection?.note && <p>{connection.note}</p>}
            </article>
          );
        })}
      </div>
      {browserNote && <p className="connect-note">{browserNote}</p>}
      <p className="manual-send-note">You sign in directly in the opened app. Cortana prepares drafts; you review the recipient and press Send yourself.</p>
      <form className="draft-form" onSubmit={prepare}>
        <h3>Prepare an exact message</h3>
        <label>App<select value={platform} onChange={(e) => setPlatform(e.target.value)} disabled={preparing}>
          {PLATFORMS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select></label>
        <label>Recipient<input name="draft-recipient" autoComplete="off" value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder={platformInfo(platform).recipientHint} maxLength={300} disabled={preparing} /></label>
        {platform === "gmail" && <label>Subject<input name="draft-subject" value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={500} disabled={preparing} /></label>}
        <label>Exact message<textarea name="draft-body" value={body} onChange={(e) => setBody(e.target.value)} rows={4} maxLength={20_000} placeholder={platform === "gmail" ? "Enter the exact message in English…" : "Enter the exact message in English or Roman Hinglish…"} disabled={preparing} /></label>
        <p className="connect-note">{platform === "gmail" ? "Gmail messages and subjects must be in English." : "WhatsApp and Instagram messages must be in English or Hinglish using Roman letters."} You can still give Cortana instructions in English, Hindi or Hinglish.</p>
        <button className="header-button" type="submit" disabled={!enabled || preparing || !recipient.trim() || !body.trim()}>{preparing ? "Preparing…" : "Prepare draft"}</button>
      </form>
      {error && <p className="integration-error" role="alert">{error}</p>}
      {draft && <DraftCard draft={draft} enabled={enabled && !preparing} onChange={setDraft} onBusyChange={onBusyChange} />}
      {!enabled && <p className="connect-note">Wait for the local assistant to connect.</p>}
    </div>
  );
}
