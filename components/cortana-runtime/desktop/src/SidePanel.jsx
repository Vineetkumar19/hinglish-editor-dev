import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "./api";

// The right-hand rail's secondary tabs: what Cortana remembers, what's
// due, and an audit trail of every tool she has actually run. These read
// straight from the agent's SQLite tables, so the panel can't drift out of
// sync with what she actually knows.

function timeAgo(ts) {
  const secs = Math.floor(Date.now() / 1000 - ts);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export default function SidePanel({ tab, refreshKey }) {
  const [facts, setFacts] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      if (tab === "memory") {
        const r = await apiFetch("/api/memory/facts");
        if (!r.ok) throw new Error("Memory is unavailable.");
        setFacts((await r.json()).facts || []);
      } else if (tab === "reminders") {
        const r = await apiFetch("/api/reminders");
        if (!r.ok) throw new Error("Reminders are unavailable.");
        setReminders((await r.json()).reminders || []);
      } else if (tab === "audit") {
        const r = await apiFetch("/api/audit/log?limit=60");
        if (!r.ok) throw new Error("Activity is unavailable.");
        setAudit((await r.json()).entries || []);
      }
      setError(null);
    } catch {
      setError("Can't reach the agent.");
    }
  }, [tab]);

  useEffect(() => {
    queueMicrotask(load);
  }, [load, refreshKey]);

  async function forget(id) {
    try {
      const result = await apiFetch(`/api/memory/facts/${id}`, { method: "DELETE" });
      if (!result.ok) throw new Error("Could not forget this item.");
      load();
    } catch (e) { setError(e.message); }
  }

  async function completeReminder(id) {
    try {
      const result = await apiFetch(`/api/reminders/${id}/complete`, { method: "POST" });
      if (!result.ok) throw new Error("Could not complete this reminder.");
      load();
    } catch (e) { setError(e.message); }
  }

  if (error) return <div className="panel-empty">{error}</div>;

  if (tab === "memory") {
    if (!facts.length) {
      return (
        <div className="panel-empty">
          Nothing remembered yet. Try saying
          <br />
          <em>&ldquo;remember that my sister&rsquo;s birthday is 3 March&rdquo;</em>
        </div>
      );
    }
    return (
      <div className="panel-list">
        {facts.map((f) => (
          <div key={f.id} className="panel-item">
            <div className="panel-item-main">
              <span className="tag">{f.category}</span>
              <span className="panel-item-text">{f.content}</span>
            </div>
            <button className="icon-btn" onClick={() => forget(f.id)} title="Forget this">
              ×
            </button>
          </div>
        ))}
      </div>
    );
  }

  if (tab === "reminders") {
    if (!reminders.length) {
      return (
        <div className="panel-empty">
          No reminders set. Try
          <br />
          <em>&ldquo;remind me to call mom in 30 minutes&rdquo;</em>
        </div>
      );
    }
    return (
      <div className="panel-list">
        {reminders.map((r) => (
          <div key={r.id} className={`panel-item ${r.overdue ? "panel-item-due" : ""}`}>
            <div className="panel-item-main">
              <span className="panel-item-text">{r.text}</span>
              <span className="panel-item-sub">
                {r.due}
                {r.overdue && " · due"}
              </span>
            </div>
            <button className="icon-btn" onClick={() => completeReminder(r.id)} title="Mark done">
              ✓
            </button>
          </div>
        ))}
      </div>
    );
  }

  // audit
  if (!audit.length) return <div className="panel-empty">No tools have run yet.</div>;
  return (
    <div className="panel-list">
      {audit.map((a, i) => (
        <div key={i} className="panel-item">
          <div className="panel-item-main">
            <span className="panel-item-text mono">{a.tool_name}</span>
            <span className="panel-item-sub">
              <span className={`decision decision-${a.decision}`}>{a.decision}</span>
              {" · "}
              {a.risk_level} · {timeAgo(a.created_at)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
