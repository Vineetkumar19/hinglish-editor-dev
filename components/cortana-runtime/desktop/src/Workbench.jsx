import { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from './api';
import LocalResult from './LocalResult';

export default function Workbench({ enabled = true, onBusyChange }) {
  const [data, setData] = useState(null), [result, setResult] = useState(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [path, setPath] = useState(''), [query, setQuery] = useState('');
  const [name, setName] = useState(''), [note, setNote] = useState('');
  const [items, setItems] = useState(''), [browser, setBrowser] = useState('chrome');
  const [profile, setProfile] = useState('Default');
  const [pending, setPending] = useState(null);
  const [task, setTask] = useState({title:'', source_document_id:'', page:1, quote:'', due_at:'', date_confidence:'explicit'});
  const [root, setRoot] = useState(''), [filename, setFilename] = useState('');
  const [before, setBefore] = useState(''), [after, setAfter] = useState('');
  const active = useRef(null);
  useEffect(() => {
    if (!busy && !pending) return;
    onBusyChange?.(1);
    return () => onBusyChange?.(-1);
  }, [busy, pending, onBusyChange]);
  const refresh = useCallback(async () => {
    const response = await apiFetch('/api/local/state');
    if (!response.ok) throw new Error('Could not read local workflow state.');
    setData(await response.json());
  }, []);
  useEffect(() => { queueMicrotask(()=>refresh().catch(e => setError(e.message))); }, [refresh]);
  useEffect(() => {
    const stop = () => {
      if (active.current) apiFetch(`/api/tasks/${active.current}/cancel`, {method:'POST'}).catch(e=>setError(e.message));
      setPending(null);
    };
    window.addEventListener('cortana-stop-workbench', stop);
    return () => { stop(); window.removeEventListener('cortana-stop-workbench', stop); };
  }, []);
  async function perform(tool, arguments_, endpoint='/api/local/action') {
    if (busy || !enabled) return;
    setBusy(true); setError(''); setPending(null);
    const request_id = crypto.randomUUID(); active.current = request_id;
    try {
      const payload = endpoint.endsWith('/action') ? {tool, arguments:arguments_, request_id} : {...arguments_, request_id};
      const response = await apiFetch(endpoint, {method:'POST',body:JSON.stringify(payload)});
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'Workflow failed.');
      setResult(body.result || null); setPending(body.pending_confirmation || null);
      await refresh();
    } catch (e) { setError(e.message); }
    finally { active.current = null; setBusy(false); }
  }
  async function decide(approve) {
    if (busy || !enabled || !pending) return;
    const current = pending;
    setPending(null); setBusy(true); setError('');
    const request_id = crypto.randomUUID(); active.current = request_id;
    try {
      const response = await apiFetch(`/api/confirm/${current.id}`, {method:'POST',body:JSON.stringify({approve,request_id})});
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'Approval failed.');
      setResult(body.result); await refresh();
    } catch(e) { setError(e.message); }
    finally {active.current=null;setBusy(false);}
  }
  function selectedItems() {
    return items.split('\n').filter(x=>x.trim()).map(line => {
      const split = line.indexOf('|');
      if (split < 0) throw new Error('Use kind|path, for example folder|D:/Cortana/documents');
      return {kind:line.slice(0,split).trim(),target:line.slice(split+1).trim()};
    });
  }
  function saveWorkspace() {
    return perform('capture_workspace', {name,items:selectedItems(),context_note:note});
  }
  return <section className="workbench">
    <h2>Local workbench</h2>
    <p>Selected documents, saved workspaces and measured PC performance. Cloud is disabled.</p>
    {error && <p role="alert">{error}</p>}
    {busy && <p role="status">Working locally… Use Stop to cancel further steps.</p>}
    <fieldset disabled={busy || !enabled}><legend>Documents and evidence</legend>
      <label>Document path<input value={path} onChange={e=>setPath(e.target.value)} placeholder="D:/Documents/receipt.pdf" /></label>
      <button onClick={()=>perform('index_document',{path})}>Import document</button>
      <label>Question or search<input value={query} onChange={e=>setQuery(e.target.value)} /></label>
      <button onClick={()=>perform('answer_with_sources',{query})}>Find source evidence</button>
      <button onClick={()=>perform('semantic_document_search',{query})}>Search semantic index</button>
      {data?.documents.map(d=><p key={d.id}>{d.path} · {d.status} · {d.pages} pages/sections
        <button onClick={()=>perform('build_document_embeddings',{document_id:d.id})}>Build local semantic index</button>
        <button onClick={()=>perform('forget_document',{document_id:d.id})}>Remove from index</button></p>)}
    </fieldset>
    <fieldset disabled={busy || !enabled}><legend>Find files</legend>
      <label>Folder to index<input value={root} onChange={e=>setRoot(e.target.value)} /></label>
      <button onClick={()=>perform('index_file_metadata',{root})}>Scan / continue selected folder</button>
      <label>Filename contains<input value={filename} onChange={e=>setFilename(e.target.value)} /></label>
      <button onClick={()=>perform('search_file_index',{query:filename})}>Find matching files</button>
    </fieldset>
    <fieldset disabled={busy || !enabled}><legend>Workspace resume</legend>
      <label>Name<input value={name} onChange={e=>setName(e.target.value)} /></label>
      <label>Selected items, one per line<textarea value={items} onChange={e=>setItems(e.target.value)} placeholder={'file|D:/Documents/notes.txt\nfolder|D:/Projects/gcp\napp|vs code'} /></label>
      <label>Last step / next action<input value={note} onChange={e=>setNote(e.target.value)} /></label>
      <button onClick={()=>{try {saveWorkspace();} catch(e){setError(e.message);}}}>Save selected workspace</button>
      <label>Browser<select value={browser} onChange={e=>setBrowser(e.target.value)}><option>chrome</option><option>brave</option></select></label>
      <label>Extension profile label<input value={profile} onChange={e=>setProfile(e.target.value)} /></label>
      <button onClick={()=>{try {perform(null,{name,browser,profile,items:selectedItems(),context_note:note},'/api/local/capture-browser');} catch(e){setError(e.message);}}}>Save workspace with selected browser tabs</button>
      {data?.workspaces.map(w=><div key={w.id}><p>{w.name} · {w.captured_at} · {w.items.length} items</p>
        <button onClick={()=>perform('preview_restore',{workspace_id:w.id})}>Preview</button>
        <button onClick={()=>perform('restore_workspace',{workspace_id:w.id,revision:w.revision})}>Review restore</button>
        {!w.parent_workspace_id && <button onClick={()=>perform('configure_workspace_capture',{workspace_id:w.id,revision:w.revision,
          enabled:!data.workspace_schedules?.find(s=>s.workspace_id===w.id)?.enabled,minutes:15})}>
          {data.workspace_schedules?.find(s=>s.workspace_id===w.id)?.enabled?'Disable periodic capture':'Review capture every 15 minutes'}
        </button>}
        {data.workspace_schedules?.filter(s=>s.workspace_id===w.id).map(s=><p key={s.id}>Periodic capture: {s.status} {s.error || ''}</p>)}
      </div>)}
    </fieldset>
    <fieldset disabled={busy || !enabled}><legend>Local models and diagnostics</legend>
      <button onClick={()=>perform('model_profiles',{})}>Inspect model profiles</button>
      <button onClick={()=>perform('switch_model_profile',{profile:'local_9b_q4'})}>Review 9B Q4 switch</button>
      <button onClick={()=>perform('switch_model_profile',{profile:'local_14b_q4'})}>Review 14B Q4 switch</button>
      <button onClick={()=>perform('sample_system',{seconds:30})}>Measure PC for 30 seconds</button>
      <p>Diagnostics read system metrics. Applications are never closed automatically.</p>
      <label>Before measurement<select value={before} onChange={e=>setBefore(e.target.value)}><option value="">Choose a report</option>
        {data?.diagnostics.map(d=><option key={d.id} value={d.id}>{new Date(d.started_at*1000).toLocaleString()}</option>)}
      </select></label>
      <label>After measurement<select value={after} onChange={e=>setAfter(e.target.value)}><option value="">Choose a report</option>
        {data?.diagnostics.map(d=><option key={d.id} value={d.id}>{new Date(d.started_at*1000).toLocaleString()}</option>)}
      </select></label>
      <button disabled={!before || !after || before===after} onClick={()=>perform('compare_diagnostics',{before_id:before,after_id:after})}>Compare measurements</button>
    </fieldset>
    <h3>Document tasks</h3>
    <fieldset disabled={busy || !enabled}><legend>Propose a source-backed deadline</legend>
      <label>Task title<input value={task.title} onChange={e=>setTask({...task,title:e.target.value})} /></label>
      <label>Source<select value={task.source_document_id} onChange={e=>setTask({...task,source_document_id:e.target.value})}>
        <option value="">Choose an imported document</option>
        {data?.documents.map(d=><option key={d.id} value={d.id}>{d.path}</option>)}
      </select></label>
      <label>Page / section<input type="number" min="1" value={task.page} onChange={e=>setTask({...task,page:Number(e.target.value)})} /></label>
      <label>Exact source quote<textarea value={task.quote} onChange={e=>setTask({...task,quote:e.target.value})} /></label>
      <label>Deadline in India time (Asia/Kolkata)<input type="datetime-local" value={task.due_at} onChange={e=>setTask({...task,due_at:e.target.value})} /></label>
      <label>Date evidence<select value={task.date_confidence} onChange={e=>setTask({...task,date_confidence:e.target.value})}>
        <option value="explicit">Date stated in source</option><option value="inferred">Date inferred — needs review</option>
      </select></label>
      <button onClick={()=>perform('propose_document_task',{...task,due_at:task.due_at+':00+05:30'})}>Propose for review</button>
    </fieldset>
    <fieldset disabled={busy || !enabled}><legend>Stored data</legend>
      <button onClick={()=>perform('inspect_local_data',{})}>Inspect stored data</button>
      <button onClick={()=>perform('export_local_data',{})}>Review local export</button>
      <button onClick={()=>perform('prune_local_history',{days:90})}>Review 90-day history cleanup</button>
    </fieldset>
    {data?.tasks.map(t=><p key={t.id}>{t.title} · {t.status} · {t.due_at} ({t.timezone}) {t.overdue?'— overdue':''}
      {t.overdue && !t.acknowledged && <button disabled={busy || !enabled} onClick={()=>perform('acknowledge_document_task',{task_id:t.id,revision:t.revision})}>Acknowledge reminder</button>}
      {!['completed','cancelled'].includes(t.status) && <>
        <button disabled={busy || !enabled} onClick={()=>perform('finish_document_task',{task_id:t.id,revision:t.revision,status:'completed'})}>Review completion</button>
        <button disabled={busy || !enabled} onClick={()=>perform('finish_document_task',{task_id:t.id,revision:t.revision,status:'cancelled'})}>Review cancellation</button>
      </>}
      {t.status==='proposed' && <button disabled={busy || !enabled} onClick={()=>perform('confirm_document_task',{task_id:t.id,revision:t.revision})}>Review deadline</button>}</p>)}
    {pending && <section><h3>Review action</h3><pre>{pending.preview}</pre>
      <button disabled={busy || !enabled} onClick={()=>decide(true)}>Approve</button><button disabled={busy || !enabled} onClick={()=>decide(false)}>Reject</button></section>}
    <LocalResult result={result} />
  </section>;
}
