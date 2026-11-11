"use strict";

const $ = (selector) => document.querySelector(selector);
const token = document.documentElement.dataset.token;
const audio = $("#audio");
const dialog = $("#import-dialog");
const form = $("#import-form");
const speakers = { agent: "Agent", caller: "Caller", unknown: "Speaker" };
let settings;
let calls = [];
let before;
let call;
let selectedSegment;
let criteria;
let dirty = false;
let conflict = false;
let selectionRequest;
let listRequest;
let mediaUrl;
let clipEnd;
let playFrame;
let eventId;

document.body.classList.toggle("embedded", new URLSearchParams(location.search).has("embedded"));

function element(tag, value, className) {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (className) node.className = className;
  return node;
}

function button(label, action, className) {
  const node = element("button", label, className);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

function options(node, values) {
  Object.entries(values).forEach(([value, label]) => node.add(new Option(label, value)));
}

function clock(ms) {
  const minutes = Math.floor(ms / 60000);
  const seconds = (ms % 60000) / 1000;
  return String(minutes).padStart(2, "0") + ":" + seconds.toFixed(3).padStart(6, "0");
}

function span(range) {
  return clock(range.start_ms) + "–" + clock(range.end_ms);
}

function status(selector, message, error = false) {
  const node = $(selector);
  node.textContent = message;
  node.classList.toggle("notice", error);
}

async function api(route, { body, signal } = {}) {
  const response = await fetch("/api/call-qa/" + route, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Hinglish-Token": token, "Content-Type": "application/json" },
    cache: "no-store",
    signal,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || "Call QA could not complete the request.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function evidenceButtons(turnIds) {
  return turnIds.flatMap((id) => {
    const turn = call.transcript.find((row) => row.id === id);
    return turn ? [button(clock(turn.start_ms), () => playEvidence(turn), "time-button")] : [];
  });
}

function renderReport() {
  clearReportDownload();
  const report = call.report;
  status("#report-state", report ? "Rubric " + report.version + " · " + report.reviewer : "Review queued…");
  $("#report-summary").textContent = report?.summary ?? "";
  $("#facts").replaceChildren(...(report?.facts || []).flatMap((fact) => {
    const term = element("dt", settings.fact_kinds[fact.kind] + " · " + fact.confidence + " confidence");
    const definition = element("dd", fact.value);
    definition.append(...evidenceButtons(fact.turn_ids));
    return [term, definition];
  }));
  for (const [key, state] of Object.entries(criteria)) {
    const finding = report?.findings?.[key];
    state.machine.replaceChildren();
    if (finding) {
      state.machine.append(element("strong", "Report · " + settings.outcomes[finding.outcome]));
      state.machine.append(element("p", finding.explanation), ...evidenceButtons(finding.turn_ids));
    }
  }
}

async function pollReport(id, request) {
  for (let tries = 0; tries < 125 && !request.signal.aborted; tries++) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    if (request.signal.aborted) return;
    try {
      const latest = await api("calls/" + id, { signal: request.signal });
      if (latest.report && !request.signal.aborted) {
        call.report = latest.report;
        renderReport();
        return;
      }
    } catch (error) {
      if (!request.signal.aborted) status("#report-state", error.message, true);
      return;
    }
  }
  if (!request.signal.aborted) status("#report-state", "Review is still queued. Reopen the call to check again.");
}

function renderCalls() {
  const items = calls.map((row) => {
    const li = element("li");
    const open = button(undefined, () => openCall(row.id), "call-row");
    open.setAttribute("aria-current", String(row.id === call?.id));
    open.append(
      element("strong", row.title),
      element("span", settings.languages[row.language] + " · " + clock(row.duration_ms).slice(0, 5), "muted"),
      element("span", row.revision ? "Reviewed" : "Awaiting review", "muted"),
    );
    li.append(open);
    return li;
  });
  $("#calls").replaceChildren(...items);
  status("#list-state", items.length ? items.length + (items.length === 1 ? " call shown" : " calls shown") : "No test calls match this view.");
  $("#older").hidden = !before;
}

async function loadList(older = false) {
  listRequest?.abort();
  const request = listRequest = new AbortController();
  const query = new URLSearchParams({ language: $("#language-filter").value });
  if (older && before) query.set("before", before);
  $("#older").disabled = true;
  status("#list-state", "Loading test calls…");
  try {
    const page = await api("calls?" + query, { signal: request.signal });
    if (request.signal.aborted) return;
    calls = older ? calls.concat(page.calls) : page.calls;
    before = page.before;
    renderCalls();
  } catch (error) {
    if (!request.signal.aborted) status("#list-state", error.message, true);
  } finally {
    if (!request.signal.aborted) $("#older").disabled = false;
  }
}

function resetAudio() {
  clipEnd = undefined;
  cancelAnimationFrame(playFrame);
  audio.pause();
  audio.removeAttribute("src");
  audio.load();
  if (mediaUrl) URL.revokeObjectURL(mediaUrl);
  mediaUrl = undefined;
}

function canLeave() {
  return $("#save-review").dataset.saving !== "true" &&
    (!dirty || window.confirm("Discard unsaved changes to this review?"));
}

async function openCall(id, reload = false) {
  if (!reload && (call?.id === id || !canLeave())) return;
  selectionRequest?.abort();
  const request = selectionRequest = new AbortController();
  resetAudio();
  clearReportDownload();
  call = undefined;
  dirty = false;
  conflict = false;
  selectedSegment = undefined;
  $("#detail-error").hidden = true;
  $("#call").hidden = true;
  $("#empty").hidden = false;
  $("#empty").textContent = "Loading call…";
  $("#workspace").dataset.showCall = "";
  try {
    const data = await api("calls/" + id, { signal: request.signal });
    if (request.signal.aborted) return;
    call = data;
    $("#call-title").textContent = call.title;
    $("#call-meta").textContent = [
      settings.languages[call.language], clock(call.duration_ms).slice(0, 5),
      call.source === "gateway" ? "Inbound gateway" : "Imported test recording",
      call.status === "partial" ? "Partial recording" : "Call ended",
      new Date(call.received_at).toLocaleString(),
    ].join(" · ");
    if (call.quality) $("#call-meta").textContent += " · " + call.quality;
    const timings = call.timing || [];
    $("#timing").hidden = !timings.length;
    $("#timing-samples").replaceChildren(...timings.map((sample) =>
      element("li", clock(sample.speech_end_ms) + " · " + sample.first_output_ms +
        " ms to output · " + sample.reply_mark_ms + " ms to playback acknowledgment")));
    $("#recording-time").textContent = clock(0);
    status("#audio-status", "Loading recording…");
    $("#empty").hidden = true;
    $("#call").hidden = false;
    if (matchMedia("(max-width: 620px)").matches) $("#call-title").focus();
    $("#reload-call").hidden = true;
    renderCalls();
    renderTranscript();
    renderReview();
    renderReport();
    if (!call.report) pollReport(id, request);
    status("#review-status", call.revision ? "Saved review · revision " + call.revision : "Awaiting review.");
    const grant = await api("calls/" + id + "/playback", { signal: request.signal });
    const response = await fetch(grant.url, { signal: request.signal, cache: "no-store", referrerPolicy: "no-referrer" });
    if (!response.ok) throw new Error("Recording access expired or the test call was removed. Reopen the call.");
    const blob = await response.blob();
    if (request.signal.aborted) return;
    mediaUrl = URL.createObjectURL(blob);
    audio.src = mediaUrl;
  } catch (error) {
    if (request.signal.aborted) return;
    if (call) status("#audio-status", error.message, true);
    else {
      $("#empty").hidden = true;
      $("#detail-error").hidden = false;
      status("#detail-error", error.message, true);
    }
  }
}

function playEvidence(range) {
  if (audio.readyState < 1) {
    status("#audio-status", "Wait for the recording to load before playing evidence.");
    return;
  }
  clipEnd = range.end_ms / 1000;
  audio.currentTime = range.start_ms / 1000;
  audio.play().catch(() => status("#audio-status", "Press Play to listen from the evidence timestamp.", true));
}

function watchPlayback() {
  if (audio.paused) return;
  if (clipEnd !== undefined && audio.currentTime >= clipEnd) {
    audio.pause();
    audio.currentTime = clipEnd;
    clipEnd = undefined;
    return;
  }
  playFrame = requestAnimationFrame(watchPlayback);
}

function renderTranscript() {
  $("#transcript-empty").hidden = call.transcript.length > 0;
  const rows = call.transcript.map((segment) => {
    const row = element("li", undefined, "transcript-row");
    const seek = button(clock(segment.start_ms), () => {
      selectedSegment = segment;
      for (const item of $("#transcript").children) item.removeAttribute("aria-current");
      row.setAttribute("aria-current", "true");
      syncCriteria();
      playEvidence(segment);
    }, "time-button");
    seek.title = "Select and play " + span(segment);
    seek.setAttribute("aria-label", "Play " + speakers[segment.speaker] + " at " + clock(segment.start_ms));
    seek.disabled = segment.played === false;
    const content = element("div");
    content.append(element("p", speakers[segment.speaker], "muted"), element("p", segment.text));
    if (segment.romanized) content.append(element("p", segment.romanized, "muted"));
    if (segment.confidence === "low") content.append(element("p", "Low transcription confidence", "muted"));
    if (segment.played === false) content.append(element("p", "Playback was not confirmed", "muted"));
    row.append(seek, content);
    return row;
  });
  $("#transcript").replaceChildren(...rows);
}

function editCriterion() {
  dirty = true;
  status("#review-status", "Unsaved review changes.");
  syncCriteria();
}

function renderReview() {
  criteria = {};
  const items = Object.entries(settings.rubric).map(([key, label]) => {
    const existing = call.review?.[key];
    const state = criteria[key] = {
      start: existing?.evidence?.start_ms ?? null,
      end: existing?.evidence?.end_ms ?? null,
      outcome: element("select"),
      note: element("textarea"),
      range: element("p", undefined, "muted"),
      machine: element("div", undefined, "machine-finding muted"),
    };
    options(state.outcome, settings.outcomes);
    state.outcome.value = existing?.outcome ?? "unobserved";
    state.note.value = existing?.note ?? "";
    state.note.maxLength = 1000;
    state.outcome.addEventListener("change", editCriterion);
    state.note.addEventListener("input", editCriterion);
    const outcomeLabel = element("label", label);
    outcomeLabel.append(state.outcome);
    const noteLabel = element("label", "Reviewer note");
    noteLabel.append(state.note);
    state.startButton = button("Mark start", () => {
      state.start = Math.floor(audio.currentTime * 1000);
      if (state.end !== null && state.end <= state.start) state.end = null;
      editCriterion();
    });
    state.endButton = button("Mark end", () => {
      const end = Math.min(call.duration_ms, Math.floor(audio.currentTime * 1000));
      if (end <= state.start) {
        status("#review-status", "Move the player past the marked start before setting an end.", true);
        return;
      }
      state.end = end;
      editCriterion();
    });
    state.segmentButton = button("Use transcript selection", () => {
      state.start = selectedSegment.start_ms;
      state.end = selectedSegment.end_ms;
      editCriterion();
    });
    state.playButton = button("Play evidence", () => playEvidence({ start_ms: state.start, end_ms: state.end }));
    const tools = element("div", undefined, "criterion-tools");
    tools.append(state.startButton, state.endButton, state.segmentButton, state.playButton);
    const criterion = element("div", undefined, "criterion");
    criterion.append(outcomeLabel, state.machine, state.range, tools, noteLabel);
    return criterion;
  });
  $("#criteria").replaceChildren(...items);
  renderSavedEvidence();
  syncCriteria();
}

function renderSavedEvidence() {
  const evidence = Object.entries(call.review || {}).flatMap(([key, row]) => {
    if (!row.evidence) return [];
    const jump = button(clock(row.evidence.start_ms) + " · " + key.replace("_", " "), () => playEvidence(row.evidence));
    jump.title = settings.rubric[key] + " · " + span(row.evidence);
    return [jump];
  });
  $("#evidence-track").replaceChildren(...evidence);
}

function syncCriteria() {
  if (!call || !criteria) return;
  const saving = $("#save-review").dataset.saving === "true";
  const ready = audio.readyState >= 1 && !audio.error;
  for (const state of Object.values(criteria)) {
    const observed = ["met", "needs_attention"].includes(state.outcome.value);
    const available = observed && !saving && ready;
    state.outcome.disabled = saving;
    state.note.disabled = saving;
    state.startButton.disabled = !available;
    state.endButton.disabled = !available || state.start === null;
    state.playButton.disabled = !available || state.end === null;
    state.segmentButton.disabled = !observed || saving || !selectedSegment;
    state.range.textContent = !observed || state.start === null ? "No evidence marked" :
      state.end === null ? "Start " + clock(state.start) : span({ start_ms: state.start, end_ms: state.end });
  }
  $("#save-review").disabled = saving || !dirty || conflict || !ready;
}

$("#review").addEventListener("submit", async (event) => {
  event.preventDefault();
  const save = $("#save-review");
  if (save.disabled) return;
  const review = {};
  for (const [key, state] of Object.entries(criteria)) {
    const outcome = state.outcome.value;
    const observed = ["met", "needs_attention"].includes(outcome);
    review[key] = {
      outcome, note: state.note.value,
      evidence: observed ? { start_ms: state.start, end_ms: state.end } : null,
    };
    if (observed && (state.start === null || state.end === null)) {
      status("#review-status", "Mark an evidence start and end for “" + settings.rubric[key] + "”.", true);
      return;
    }
  }
  save.dataset.saving = "true";
  syncCriteria();
  status("#review-status", "Saving review…");
  try {
    const saved = await api("calls/" + call.id + "/review", { body: { revision: call.revision, review } });
    Object.assign(call, saved);
    clearReportDownload();
    dirty = false;
    renderSavedEvidence();
    const item = calls.find((row) => row.id === call.id);
    if (item) item.revision = saved.revision;
    renderCalls();
    status("#review-status", "Saved review · revision " + saved.revision);
  } catch (error) {
    conflict = error.status === 409;
    $("#reload-call").hidden = !conflict;
    status("#review-status", error.message, true);
  } finally {
    delete save.dataset.saving;
    syncCriteria();
  }
});

$("#reload-call").addEventListener("click", () => {
  if (canLeave()) openCall(call.id, true);
});
function closeCall() {
  selectionRequest?.abort();
  resetAudio();
  clearReportDownload();
  call = undefined;
  dirty = false;
  $("#call").hidden = true;
  $("#empty").hidden = false;
  $("#empty").textContent = "Select a call to start a review.";
  delete $("#workspace").dataset.showCall;
  renderCalls();
  $("#calls button")?.focus();
}
$("#back").addEventListener("click", () => {
  if (canLeave()) closeCall();
});
function clearReportDownload() {
  const link = $("#download-report");
  if (link.href.startsWith("blob:")) URL.revokeObjectURL(link.href);
  link.removeAttribute("href");
  link.hidden = true;
}

$("#export-report").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const selected = call;
  const revision = selected.revision;
  const report = selected.report;
  const signal = selectionRequest.signal;
  button.disabled = true;
  clearReportDownload();
  try {
    let href;
    try {
      const grant = await api("calls/" + selected.id + "/export-link", { signal });
      href = grant.url;
    } catch (error) {
      if (error.status !== 404) throw error;
      // The workspace may still be served by a process started before the update.
      const data = await api("calls/" + selected.id + "/export", { signal });
      href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    }
    if (signal.aborted || selected.revision !== revision || selected.report !== report) {
      if (href.startsWith("blob:")) URL.revokeObjectURL(href);
      return;
    }
    const link = $("#download-report");
    link.href = href;
    link.hidden = false;
    link.focus();
    status("#report-state", "Anonymized report ready to download.");
  } catch (error) {
    if (!signal.aborted) status("#report-state", error.message, true);
  } finally {
    button.disabled = false;
  }
});
$("#save-report").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const signal = selectionRequest.signal;
  button.disabled = true;
  try {
    const saved = await api("calls/" + call.id + "/save-export", { body: {}, signal });
    if (!signal.aborted) status("#report-state", "Saved anonymized report to " + saved.path);
  } catch (error) {
    if (!signal.aborted) status("#report-state", error.message, true);
  } finally {
    button.disabled = false;
  }
});
$("#delete-call").addEventListener("click", async () => {
  if (!canLeave() || !window.confirm("Permanently remove this test recording, transcript and review?")) return;
  const id = call.id;
  try {
    await api("calls/" + id + "/delete", { body: { confirmed: true } });
    if (call?.id === id) closeCall();
    await loadList();
  } catch (error) {
    status("#review-status", error.message, true);
  }
});
audio.addEventListener("loadedmetadata", () => {
  status("#audio-status", "Choose a timestamp to play its evidence.");
  syncCriteria();
});
audio.addEventListener("error", () => {
  if (mediaUrl) status("#audio-status", "The browser could not play this recording. Reload the call or import a PCM WAV.", true);
  syncCriteria();
});
audio.addEventListener("timeupdate", () => { $("#recording-time").textContent = clock(Math.floor(audio.currentTime * 1000)); });
audio.addEventListener("playing", () => {
  cancelAnimationFrame(playFrame);
  watchPlayback();
});
audio.addEventListener("pause", () => cancelAnimationFrame(playFrame));
audio.addEventListener("ended", () => { clipEnd = undefined; });
window.addEventListener("beforeunload", (event) => {
  if (dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});

function readRecording(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",", 2)[1]);
    reader.onerror = () => reject(new Error("Could not read the recording. Select the WAV again."));
    reader.readAsDataURL(file);
  });
}

$("#import-open").addEventListener("click", () => dialog.showModal());
$("#import-close").addEventListener("click", () => dialog.close());
dialog.addEventListener("cancel", (event) => {
  if ($("#import-submit").disabled) event.preventDefault();
});
form.addEventListener("input", () => { eventId = undefined; });
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!canLeave()) return;
  const data = new FormData(form);
  const recording = data.get("recording");
  const transcriptFile = data.get("transcript");
  if (recording.size > 24 * 1024 * 1024 || transcriptFile.size > 512 * 1024) {
    status("#import-status", "Choose a recording up to 24 MiB and a transcript up to 512 KiB.", true);
    return;
  }
  const controls = Array.from(form.elements);
  controls.forEach((control) => { control.disabled = true; });
  status("#import-status", "Importing recording…");
  try {
    let transcript = [];
    if (transcriptFile.size) {
      try {
        transcript = JSON.parse(await transcriptFile.text());
      } catch {
        throw new Error("Choose a valid transcript JSON file.");
      }
    }
    const result = await api("calls", { body: {
      title: data.get("title"), language: data.get("language"),
      consent: data.get("consent") === "on", test_call: true,
      event_id: eventId ??= crypto.randomUUID(),
      transcript, recording: await readRecording(recording),
    } });
    form.reset();
    eventId = undefined;
    status("#import-status", "");
    dialog.close();
    $("#language-filter").value = "";
    await loadList();
    await openCall(result.id, true);
  } catch (error) {
    status("#import-status", error.message, true);
  } finally {
    controls.forEach((control) => { control.disabled = false; });
  }
});

$("#language-filter").addEventListener("change", () => loadList());
$("#refresh").addEventListener("click", async () => {
  try {
    const latest = await api("settings");
    renderGateway(latest);
  } catch (error) {
    status("#gateway", error.message, true);
  }
  await loadList();
});
$("#older").addEventListener("click", () => loadList(true));

function renderGateway(current) {
  const event = current.gateway_state;
  const message = current.gateway_enabled
    ? "Signed inbound gateway enabled" + (event ? " · " + event.detail : " · waiting for test-call delivery")
    : "Inbound gateway disabled · import a consented test recording to review";
  status("#gateway", message, current.gateway_enabled && ["unavailable", "expired"].includes(event?.status));
}

async function initialize() {
  try {
    settings = await api("settings");
    options($("#language-filter"), settings.languages);
    options(form.elements.language, settings.languages);
    $("#retention-label").textContent = "Test recordings and their reviews expire after " + settings.retention_days + " days.";
    renderGateway(settings);
    $("#import-open").disabled = false;
    $("#refresh").disabled = false;
    await loadList();
  } catch (error) {
    $("#workspace-error").hidden = false;
    status("#workspace-error", error.message, true);
    status("#list-state", "Call QA could not load.");
  }
}

initialize();
