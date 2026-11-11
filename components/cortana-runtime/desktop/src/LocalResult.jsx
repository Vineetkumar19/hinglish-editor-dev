function localTime(value) {
  return new Date(value).toLocaleString('en-IN', {timeZone:'Asia/Kolkata'});
}

export default function LocalResult({ result }) {
  if (!result) return null;
  let content;
  if (result.findings) {
    content = <>
      {result.findings.map((finding,index)=><article key={index}>
        <h4>{finding.finding}</h4><p>{finding.evidence}</p>
        <p>Possible explanation: {finding.hypothesis}</p><p>{finding.proposed_action}</p>
      </article>)}
      <p>Measured over {Math.round(result.finished_at-result.started_at)} seconds. No application was stopped.</p>
    </>;
  } else if (result.sources) {
    content = <>
      {!result.sources.length && <p>No current source evidence found.</p>}
      {result.sources.map((source,index)=><article key={index}>
        <h4>{source.path} — page / section {source.page}</h4>
        <blockquote>{source.text}</blockquote>
        {source.method === 'ocr' && <p>Scanned text; {source.confidence == null ? 'confidence unavailable — check the original' : `${Math.round(source.confidence*100)}% OCR confidence`}.</p>}
      </article>)}
      <p>{result.uncertainty || result.note}</p>
    </>;
  } else if (result.outcomes) {
    content = <ul>{result.outcomes.map((item,index)=><li key={index}>
      <strong>{item.target}</strong>: {item.status === 'opened_unverified' ? 'Opened — check the target application' : item.status.replaceAll('_',' ')}
      <p>{item.error || item.note || item.result?.warning}</p>
      {item.result?.playback && <p>Video at {Math.floor(item.result.playback.seconds)} seconds; {item.result.playback.paused ? 'paused' : 'playing'}.</p>}
    </li>)}</ul>;
  } else if (result.workspace && result.items) {
    content = <><h4>{result.workspace.name}</h4><p>{result.workspace.context_note}</p>
      <ul>{result.items.map((item,index)=><li key={index}>{item.kind}: {item.target} — {item.status.replaceAll('_',' ')} {item.note}</li>)}</ul>
      <p>{result.note}</p></>;
  } else if (result.profiles) {
    content = <><p>Selected: {result.selected_model}</p>
      <ul>{Object.entries(result.profiles).map(([key,value])=><li key={key}>{value.tag} — {value.installed?'installed':'unavailable'}</li>)}</ul>
      <p>Available RAM: {(result.available_ram_bytes/1024**3).toFixed(1)} GiB.</p></>;
  } else if (result.path && result.pages != null) {
    content = <><h4>{result.path}</h4><p>{result.pages} pages / sections; {result.status}.</p>
      {result.field_candidates?.length > 0 && <ul>{result.field_candidates.map((field,index)=><li key={index}>{field.field}: {field.value} (page {field.page}; unconfirmed source text)</li>)}</ul>}
      {result.warnings?.map((warning,index)=><p key={index}>Page {warning.page}: {warning.error}</p>)}</>;
  } else if (result.name && result.items) {
    content = <><h4>Saved: {result.name}</h4><p>{result.items.length} selected items · {localTime(result.captured_at)} IST</p><p>{result.context_note}</p></>;
  } else if (result.title && result.due_at) {
    content = <><h4>{result.title}</h4><p>{result.status} · {localTime(result.due_at)} IST</p><blockquote>{result.source_span?.quote}</blockquote></>;
  } else if (result.before && result.after) {
    content = <><p>Available RAM: {(result.before.available_ram_bytes/1024**3).toFixed(1)} → {(result.after.available_ram_bytes/1024**3).toFixed(1)} GiB.</p>
      <p>CPU average: {result.before.cpu_percent.toFixed(1)}% → {result.after.cpu_percent.toFixed(1)}%.</p><p>{result.note}</p></>;
  } else {
    content = <p>{result.error || result.note || (result.exported ? `Exported to ${result.exported}` : result.status ? result.status.replaceAll('_',' ') : 'Action finished. Expand details to inspect the result.')}</p>;
  }
  return <section className="local-result"><h3>Result</h3>{content}
    <details><summary>Recorded details</summary><pre>{JSON.stringify(result,null,2)}</pre></details>
  </section>;
}
