const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const root = require('node:path').resolve(__dirname, '..');
const voice = fs.readFileSync(root + '/hinglish_app/static/support-call.js', 'utf8');
const actions = fs.readFileSync(root + '/hinglish_app/static/support-call-actions.js', 'utf8');
function section(text, start, end) { return text.slice(text.indexOf(start), text.indexOf(end, text.indexOf(start))); }
function evaluate(text, globals = {}) {
  const context = vm.createContext({ console, AbortController, setTimeout, clearTimeout, TextEncoder,
    btoa: text => Buffer.from(text, 'binary').toString('base64'), ...globals });
  vm.runInContext(text, context); return context;
}
(async () => {
  // An unresponsive localhost fetch cannot hold a voice turn indefinitely.
  let cancelled = false;
  const requests = evaluate(section(voice, '  async function request(', '\n  function release()'), {
    token: 'test-only', fetch: (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => { cancelled = true; reject(new Error('aborted')); });
    }),
  });
  await assert.rejects(requests.request('local-turn', { abort: new AbortController() }, { timeoutMs: 8 }), /too long/);
  assert.equal(cancelled, true);
  // An ignored permission prompt times out, and a late approval releases the track.
  let approveMicrophone, stoppedMicrophone = false;
  const microphone = evaluate(section(voice, '  async function openMicrophone(', '\n  async function connect('), {
    current: () => true, setTimeout: callback => setTimeout(callback, 5),
    navigator: {mediaDevices: {getUserMedia: () => new Promise(resolve => { approveMicrophone = resolve; })}},
  });
  await assert.rejects(microphone.openMicrophone({}), /Microphone permission timed out/);
  approveMicrophone({getTracks: () => [{stop: () => { stoppedMicrophone = true; }}]});
  await Promise.resolve();
  assert.equal(stoppedMicrophone, true);
  // Reporting delays are independent of both execution and deferred audio.
  let speechRequested = false;
  const action = evaluate(section(voice, '  async function applyTurnAction(', '\n  function reportTurn('), {
    window: { storylensApplyVoiceAction: async () => 'Set Render engine to Hyperframes.' },
    performance: { now: () => 10 }, minimizeCall() {}, reportTurn: () => new Promise(() => {}),
    request: async () => { speechRequested = true; return { audio: 'actual-answer' }; },
  });
  const data = { action: { type: 'set_control' }, turn_id: 'turn1', speech_id: 'speech1' };
  await Promise.race([action.applyTurnAction({}, data, new AbortController().signal),
    new Promise((_, reject) => setTimeout(() => reject(new Error('receipt blocked speech')), 100))]);
  assert.equal(speechRequested, true); assert.equal(data.audio, 'actual-answer');
  // Cached confirmations are only spoken after actual successful navigation/settings.
  speechRequested = false;
  const cached = { action: { type: 'set_control' }, turn_id: 'turn2', speech_id: 'speech2', confirmation_audio: 'updated' };
  await action.applyTurnAction({}, cached, new AbortController().signal);
  assert.equal(cached.audio, 'updated'); assert.equal(speechRequested, false);
  const failed = { action: { type: 'set_control' }, turn_id: 'turn3', speech_id: 'speech3', confirmation_audio: 'updated' };
  action.window.storylensApplyVoiceAction = async () => { throw new Error('setting did not change'); };
  await assert.rejects(action.applyTurnAction({}, failed, new AbortController().signal), /did not change/);
  assert.equal(failed.audio, undefined); assert.equal(speechRequested, false);
  // Short pauses within a phrase are not dispatched; ten 32ms quiet frames are.
  let now = 0; const sent = [];
  const capture = evaluate(section(voice, '  function resetLocalInput(', '\n  async function connectLocal('), {
    current: () => true, performance: { now: () => now }, stopLocalOutput() {}, updatePhase() {},
    localTurn: (...args) => sent.push(args),
  });
  const session = { localReady: true, noise: .003 }; capture.resetLocalInput(session);
  const voiced = new Float32Array(512).fill(.05), quiet = new Float32Array(512);
  for (let i = 0; i < 20; i++) { now += 32; capture.captureFrame(session, voiced); }
  for (let i = 0; i < 9; i++) { now += 32; capture.captureFrame(session, quiet); }
  assert.equal(sent.length, 0);
  now += 32; capture.captureFrame(session, quiet); assert.equal(sent.length, 1);
  assert.equal(now - sent[0][2], 320);
  // Latency includes silence detection, leading PCM silence and device output.
  const reported = [];
  const meter = evaluate(section(voice, '  function recordAudibleStart(', '\n  function renewLocalCall('), {
    window: {}, performance: { now: () => 650 },
    request: async (_url, _session, options) => reported.push(JSON.parse(options.body)),
  });
  const decoded = { length: 1000, numberOfChannels: 1, sampleRate: 1000,
    getChannelData: () => { const a = new Float32Array(1000); a[100] = .1; return a; } };
  meter.recordAudibleStart({ id: 'call', context: { baseLatency: .01, outputLatency: .02 } },
    { id: 'turn', sentAt: 320, speechEndedAt: 0, responseAt: 600, actionMs: 25 }, decoded);
  assert.equal(reported[0].client_timings.audio_start_ms, 780);
  assert.equal(reported[0].client_timings.endpoint_ms, 320);
  assert.equal('ok' in reported[0], false); // telemetry cannot overwrite action outcome
  // Only scoped dropdowns are exposed; hidden/secret settings never enter context.
  function field(label, opts = {}) { return { id: label.replaceAll(' ', ''), label, value: 'hyperframes',
    options: [{value:'hyperframes',label:'Hyperframes',disabled:false,hidden:false,closest:()=>null}], ...opts }; }
  const fields = [field('Render engine'), field('Password'), field('Hidden',{hidden:true}),
    field('Unavailable',{disabled:true}), field('Huge',{options: Array.from({length:80},(_,i)=>({
      value:'v'+i,label:'x'.repeat(120),hidden:false,closest:()=>null}))})];
  const snapshot = evaluate(section(actions, '  window.storylensVoiceFields =', '\n  function requiresReview('), {
    window: {}, settingScopes: () => [{querySelectorAll: () => fields}], currentSettingDocument: () => ({}),
    present: f => !f.hidden, labels: f => [f.label], available: f => !f.disabled,
  });
  const encoded = snapshot.window.storylensVoiceFields();
  assert.ok(encoded.length <= 12000);
  const rows = JSON.parse(Buffer.from(encoded, 'base64').toString('utf8'));
  assert.deepEqual(rows.map(r=>r.label), ['Render engine','Unavailable']);
  assert.equal(rows[1].disabled, true);
  assert.equal(rows[0].options[0].value, 'hyperframes');
  // Repeated setting labels are resolved by an exact ID inside the current scope.
  function select(id) { return { id, tagName: 'SELECT', value: 'remotion', closest: () => null,
    checkValidity: () => true, dispatchEvent() {}, ownerDocument: {defaultView:{Event:class {}}} }; }
  const one = select('motionEngine'), two = select('otherEngine');
  const setter = evaluate(section(actions, '  async function setControl(', '\n  window.storylensApplyVoiceAction ='), {
    settingName: s => s.toLowerCase(), settingScopes: () => [{ querySelectorAll: () => [one, two] }],
    available: () => true, labels: () => ['Render engine'],
    matchScore: (names, value) => names.some(n => n.toLowerCase() === value.toLowerCase()) ? 2 : 0,
    optionFor: (_field, value) => value === 'hyperframes' ? {value:'hyperframes',label:'Hyperframes'} : null,
    reveal() {},
  });
  await setter.setControl({}, {label:'Render engine',field_id:'motionEngine',value:'hyperframes'}, new AbortController().signal);
  assert.equal(one.value, 'hyperframes'); assert.equal(two.value, 'remotion');
  await assert.rejects(setter.setControl({}, {label:'Render engine',field_id:'missing',value:'hyperframes'},
    new AbortController().signal), /couldn’t find/);
  console.log('10 frontend latency/control scenarios passed (Node fixtures; no browser launched).');
})().catch(error => { console.error(error); process.exitCode=1; });
