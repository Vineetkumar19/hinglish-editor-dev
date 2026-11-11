import { useState } from "react";
import { apiFetch } from "./api";
import { draftLabel, platformInfo, previewParts } from "./draftState";

export default function DraftCard({ draft, enabled = true, onChange, onBusyChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const platform = platformInfo(draft?.platform);
  const preview = previewParts(draft);
  const candidates = Array.isArray(draft?.candidates) ? draft.candidates : [];
  const validId = /^[a-zA-Z0-9_-]{1,100}$/.test(draft?.draft_id || "");
  const canAct = enabled && !busy && validId;
  async function run(action, payload) {
    if (!canAct) return;
    setBusy(true);
    onBusyChange?.(1);
    setError("");
    try {
      const response = await apiFetch(`/api/drafts/${draft.draft_id}/${action}`, {
        method: "POST", ...(payload ? { body: JSON.stringify(payload) } : {}),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not update the draft.");
      onChange?.({ ...draft, ...result });
    } catch (e) { setError(e.name === "AbortError" ? "Draft preparation stopped. Check the app for any text already entered." : e.message); }
    finally { setBusy(false); onBusyChange?.(-1); }
  }

  async function openApp() {
    if (!enabled || busy || !platform.id) return;
    setBusy(true);
    onBusyChange?.(1);
    setError("");
    try {
      const response = await apiFetch(`/api/integrations/${platform.id}/open`, { method: "POST" });
      const result = await response.json();
      if (!response.ok || result.status === "error") throw new Error(result.note || result.detail || "Could not open the app.");
    } catch (e) { setError(e.name === "AbortError" ? "Opening stopped." : e.message); }
    finally { setBusy(false); onBusyChange?.(-1); }
  }

  return (
    <section className={`draft-card draft-${draft?.status || "unknown"}`} aria-label={`${platform.label} draft`}>
      <div className="draft-heading"><span className="tag">{platform.label}</span><strong>{draftLabel(draft?.status)}</strong></div>
      {draft?.recipient && <p className="draft-recipient">To: {draft.recipient}</p>}
      {draft?.sender && <p className="draft-recipient">From: {draft.sender}</p>}
      {preview.subject && <p className="draft-subject">Subject: {preview.subject}</p>}
      {preview.body && <pre className="draft-body">{preview.body}</pre>}
      {draft?.note && draft.status !== "draft_ready" && <p className="draft-note">{draft.note}</p>}
      {draft?.status === "choose_recipient" && (
        <div className="candidate-list" aria-label="Recipient choices">
          {candidates.length ? candidates.map((candidate) => (
            <button key={candidate.id} className="candidate-button" disabled={!canAct}
              onClick={() => run("select", { candidate_id: candidate.id })}>
              <strong>{candidate.label}</strong>
              {candidate.detail && <span>{candidate.detail}</span>}
              <small>Choose this recipient</small>
            </button>
          )) : <p className="draft-note">No recipient choices were returned. Check the name and prepare a new draft.</p>}
        </div>
      )}
      {draft?.status === "needs_login" && (
        <div className="draft-actions">
          <button className="header-button" disabled={!enabled || busy || !platform.id} onClick={openApp}>Open {platform.label} to sign in</button>
          <button className="header-button" disabled={!canAct} onClick={() => run("resume")}>Continue after sign-in</button>
        </div>
      )}
      {draft?.status === "error" && validId && <button className="header-button" disabled={!canAct} onClick={() => run("resume")}>Retry preparing draft</button>}
      {busy && <p className="draft-note" role="status">Working on the draft…</p>}
      {error && <p className="integration-error" role="alert">{error}</p>}
      {draft?.status === "draft_ready" && <p className="manual-send-note">Draft ready. Verify it and press Send in {platform.label}.</p>}
    </section>
  );
}
