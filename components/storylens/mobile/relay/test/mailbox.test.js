import assert from 'node:assert/strict';
import {createHash, timingSafeEqual, webcrypto} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import worker, {LIMITS, PersonalMailbox} from '../src/index.js';

// Workers supplies this native constant-time primitive; Node's equivalent is used here.
webcrypto.subtle.timingSafeEqual = (a, b) => timingSafeEqual(Buffer.from(a), Buffer.from(b));
Object.defineProperty(globalThis, 'crypto', {value: webcrypto, configurable: true});
const TOKENS = {phone: 'phone_fixture_token_'.repeat(3), laptop: 'laptop_fixture_token_'.repeat(3)};
const hash = value => createHash('sha256').update(value).digest('hex');
const settle = async () => { for (let i = 0; i < 20; i++) await new Promise(resolve => setImmediate(resolve)); };

class Clock {
  time = 1000000;
  next = 0;
  timers = new Map();
  now = () => this.time;
  setTimeout = (callback, delay) => {
    const id = ++this.next;
    this.timers.set(id, {at: this.time + delay, callback});
    return id;
  };
  clearTimeout = id => this.timers.delete(id);
  async advance(milliseconds) {
    const end = this.time + milliseconds;
    for (;;) {
      const entry = [...this.timers].sort((a, b) => a[1].at - b[1].at)[0];
      if (!entry || entry[1].at > end) break;
      this.time = entry[1].at;
      this.timers.delete(entry[0]);
      entry[1].callback();
      await settle();
    }
    this.time = end;
    await settle();
  }
}

function fixture(rate = '600') {
  const clock = new Clock();
  const state = new Proxy({}, {get(_target, key) { throw new Error(`Persistent state used: ${String(key)}`); }});
  const env = {PHONE_TOKEN_HASH: hash(TOKENS.phone), LAPTOP_TOKEN_HASH: hash(TOKENS.laptop), RATE_LIMIT_PER_MINUTE: rate};
  const mailbox = new PersonalMailbox(state, env, clock);
  const calls = [];
  env.PERSONAL_MAILBOX = {
    idFromName(name) { calls.push({name}); assert.equal(name, 'personal-v1'); return 'only-owner'; },
    get(id) {
      assert.equal(id, 'only-owner');
      return {fetch(request) { calls.push({role: request.headers.get('x-mailbox-role'), url: request.url}); return mailbox.fetch(request); }};
    }
  };
  function request(path, {role = 'phone', token = TOKENS[role], method = 'GET', body, headers = {}, signal, url} = {}) {
    const h = new Headers(headers);
    if (token !== null) h.set('Authorization', `Bearer ${token}`);
    if (body !== undefined && !h.has('Content-Type')) h.set('Content-Type', 'application/json');
    const init = {method, headers: h, signal};
    if (body !== undefined) {
      init.body = typeof body === 'string' || body instanceof ReadableStream ? body : JSON.stringify(body);
      if (body instanceof ReadableStream) init.duplex = 'half';
    }
    return worker.fetch(new Request(url || `https://relay.example${path}`, init), env);
  }
  const push = (body, options = {}) => request('/v1/push', {...options, method: 'POST', body});
  const pull = (role = 'laptop', wait = 0, options = {}) => request(`/v1/pull?wait=${wait}`, {role, ...options});
  return {clock, mailbox, env, calls, request, push, pull};
}

function frame(index = 1, bytes = 24) {
  const nonce = Buffer.alloc(12);
  nonce.writeUInt32BE(index, 8);
  return {v: 1, id: index.toString(16).padStart(8, '0'), nonce: nonce.toString('base64url'), data: Buffer.alloc(bytes, index % 256).toString('base64url')};
}
const bodyOf = async response => response.json();

test('generic health is public, no-store, no CORS and never reaches a mailbox', async () => {
  const f = fixture();
  const response = await f.request('/health', {token: null, headers: {Origin: 'https://untrusted.example'}});
  assert.equal(response.status, 200);
  assert.deepEqual(await bodyOf(response), {service: 'storylens-personal-link', version: 1});
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(response.headers.has('access-control-allow-origin'), false);
  assert.equal(f.calls.length, 0);
});

test('auth fails closed before Durable Object access and never reflects credentials', async () => {
  const f = fixture();
  for (const token of [null, 'short', 'wrong_token_'.repeat(5)]) {
    const response = await f.pull('phone', 0, {token});
    assert.equal(response.status, 401);
    assert.deepEqual(await bodyOf(response), {error: 'unauthorized'});
    assert.equal(response.headers.get('cache-control'), 'no-store');
  }
  assert.equal(f.calls.length, 0);
  f.env.PHONE_TOKEN_HASH = f.env.LAPTOP_TOKEN_HASH;
  assert.equal((await f.pull()).status, 503);
  f.env.PHONE_TOKEN_HASH = 'bad';
  assert.equal((await f.pull()).status, 503);
  assert.equal(f.calls.length, 0);
});

test('role scopes cannot be forged and each side receives only opposite-role frames', async () => {
  const f = fixture();
  const fromPhone = frame(1), fromLaptop = {...frame(2), id: fromPhone.id};
  assert.equal((await f.push(fromPhone, {headers: {'x-mailbox-role': 'laptop'}})).status, 200);
  assert.deepEqual(await bodyOf(await f.pull('phone')), {messages: []});
  assert.equal((await f.push(fromLaptop, {role: 'laptop'})).status, 200);
  assert.deepEqual(await bodyOf(await f.pull('laptop')), {messages: [fromPhone]});
  assert.deepEqual(await bodyOf(await f.pull('phone')), {messages: [fromLaptop]});
  assert.deepEqual(await bodyOf(await f.pull('laptop')), {messages: []});
  assert.ok(f.calls.filter(call => call.url).every(call => new URL(call.url).hostname === 'mailbox.internal'));
});

test('HTTP, routes, methods, query keys and content types are strictly bounded', async () => {
  const f = fixture();
  const requests = [
    [f.request('/health', {url: 'http://relay.example/health'}), 400],
    [f.request('/register', {method: 'POST', body: {}}), 404],
    [f.request('/v1/push', {method: 'GET'}), 405],
    [f.request('/v1/pull', {method: 'POST', body: {}}), 405],
    [f.request('/v1/push', {method: 'OPTIONS'}), 405],
    [f.request('/health?token=secret'), 400],
    [f.request('/v1/pull?wait=0&targetURL=https://example.com'), 400],
    [f.request('/v1/pull?wait=0&wait=1'), 400],
    [f.request('/v1/pull?wait=21'), 400],
    [f.request('/v1/pull?wait=-1'), 400],
    [f.request('/v1/pull?wait=1.5'), 400],
    [f.push(frame(), {headers: {'content-type': 'text/plain'}}), 415],
    [f.push(frame(), {headers: {'content-encoding': 'gzip'}}), 415]
  ];
  for (const [pending, expected] of requests) {
    const response = await pending;
    assert.equal(response.status, expected);
    assert.equal(response.headers.has('access-control-allow-origin'), false);
    assert.equal(response.headers.get('cache-control'), 'no-store');
  }
  assert.equal(f.calls.length, 0);
});

test('malformed envelopes/base64, extra plaintext fields and excessive ciphertext are refused', async () => {
  const f = fixture();
  const valid = frame();
  const invalid = [
    null, [], '{}', '{', {...valid, v: 2}, {...valid, id: 'not-an-id'},
    {...valid, id: 'f'.repeat(81)}, {...valid, nonce: Buffer.alloc(11).toString('base64url')},
    {...valid, nonce: valid.nonce + '='}, {...valid, data: 'AA=='},
    {...valid, data: '*'.repeat(32)}, {...valid, data: 'A'},
    {...valid, data: Buffer.alloc(15).toString('base64url')},
    {...valid, data: 'A'.repeat(21) + 'B'},
    {...valid, data: 123}, {...valid, command: 'plaintext is forbidden'},
    {...valid, data: Buffer.alloc(LIMITS.MAX_DATA_BYTES + 1).toString('base64url')}
  ];
  for (const value of invalid) {
    const response = await f.push(value);
    assert.equal(response.status, 400, JSON.stringify(value)?.slice(0, 120));
    assert.deepEqual(await bodyOf(response), {error: 'invalid_envelope'});
  }
  assert.equal(f.calls.length, 0);
  assert.equal((await f.push(frame(2, LIMITS.MAX_DATA_BYTES))).status, 200);
});

test('wire limit is enforced against declared length and actual streamed bytes before JSON parsing', async () => {
  const f = fixture();
  assert.equal((await f.push('{}', {headers: {'content-length': `${LIMITS.MAX_BODY_BYTES + 1}`}})).status, 413);
  let cancelled = false;
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(LIMITS.MAX_BODY_BYTES));
      controller.enqueue(new Uint8Array(1));
    },
    cancel() { cancelled = true; }
  });
  assert.equal((await f.push(stream)).status, 413);
  assert.equal(cancelled, true);
  assert.equal(f.calls.length, 0);
});

test('pull returns at most eight frames in FIFO order', async () => {
  const f = fixture();
  for (let i = 1; i <= 10; i++) assert.equal((await f.push(frame(i))).status, 200);
  assert.deepEqual((await bodyOf(await f.pull())).messages.map(value => value.id), Array.from({length: 8}, (_, i) => frame(i + 1).id));
  assert.deepEqual((await bodyOf(await f.pull())).messages.map(value => value.id), [frame(9).id, frame(10).id]);
});

test('eight maximum-size frames fit the laptop two-MiB pull response limit', async () => {
  const f = fixture();
  for (let i = 1; i <= 8; i++) assert.equal((await f.push(frame(i, LIMITS.MAX_DATA_BYTES))).status, 200);
  const response = await f.pull();
  const text = await response.text();
  assert.equal(JSON.parse(text).messages.length, 8);
  assert.ok(Buffer.byteLength(text) < 2 * 1024 * 1024);
});

test('frame capacity is per direction and rejects overflow without dropping prior frames', async () => {
  const f = fixture();
  for (let i = 1; i <= 64; i++) assert.equal((await f.push(frame(i))).status, 200);
  const full = await f.push(frame(65));
  assert.equal(full.status, 429);
  assert.deepEqual(await bodyOf(full), {error: 'mailbox_full'});
  assert.equal((await f.push(frame(66), {role: 'laptop'})).status, 200);
  assert.equal((await bodyOf(await f.pull())).messages.length, 8);
  assert.equal((await f.push(frame(65))).status, 200);
});

test('serialized memory byte capacity applies before the frame count cap', async () => {
  const f = fixture();
  let accepted = 0;
  let bytes = 0;
  for (let i = 1; i <= 64; i++) {
    const envelope = frame(i, LIMITS.MAX_DATA_BYTES);
    const size = Buffer.byteLength(JSON.stringify(envelope));
    const response = await f.push(envelope);
    if (bytes + size <= LIMITS.MAX_QUEUE_BYTES) {
      assert.equal(response.status, 200);
      accepted++;
      bytes += size;
    } else {
      assert.equal(response.status, 429);
      break;
    }
  }
  assert.ok(accepted < 64 && accepted > 25);
  let received = 0;
  while (received < accepted) received += (await bodyOf(await f.pull())).messages.length;
  assert.equal(received, accepted);
});

test('expired frames disappear without polling and duplicate receipts do not extend TTL', async () => {
  const f = fixture();
  const response = await bodyOf(await f.push(frame()));
  await f.clock.advance(119000);
  const duplicate = await bodyOf(await f.push(frame()));
  assert.equal(duplicate.expires_at, response.expires_at);
  await f.clock.advance(1000);
  assert.equal(f.mailbox.queues.laptop.length, 0);
  assert.deepEqual(await bodyOf(await f.pull()), {messages: []});
  assert.equal((await f.push(frame())).status, 200);
});

test('identical retries are receipts only, including after pull; changed ID content and reused nonce conflict', async () => {
  const f = fixture();
  const original = frame();
  assert.equal((await f.push(original)).status, 200);
  const retry = await f.push(original);
  assert.equal(retry.status, 200);
  assert.deepEqual(await bodyOf(retry), {id: original.id, status: 'queued', duplicate: true, expires_at: f.clock.now() + LIMITS.TTL_MS});
  assert.equal((await f.push({...frame(2), id: original.id})).status, 409);
  assert.equal((await f.push({...original, data: frame(3).data})).status, 409);
  assert.equal((await f.push({...original, id: frame(4).id})).status, 409);
  assert.deepEqual((await bodyOf(await f.pull())).messages, [original]);
  const delivered = await bodyOf(await f.push(original));
  assert.equal(delivered.status, 'delivered');
  assert.equal(delivered.duplicate, true);
  assert.deepEqual(await bodyOf(await f.pull()), {messages: []});
});

test('simultaneous identical push retries enqueue only once', async () => {
  const f = fixture();
  const responses = await Promise.all(Array.from({length: 12}, () => f.push(frame())));
  assert.ok(responses.every(response => response.status === 200));
  const receipts = await Promise.all(responses.map(bodyOf));
  assert.equal(receipts.filter(receipt => receipt.duplicate === false).length, 1);
  assert.equal(receipts.filter(receipt => receipt.duplicate === true).length, 11);
  assert.deepEqual((await bodyOf(await f.pull())).messages, [frame()]);
});

test('longpoll is woken only by opposite-role traffic and only one waiter per role is allowed', async () => {
  const f = fixture();
  let resolved = false;
  const waiting = f.pull('laptop', 20).then(response => { resolved = true; return response; });
  await settle();
  const competing = await f.pull('laptop', 0);
  assert.equal(competing.status, 409);
  assert.deepEqual(await bodyOf(competing), {error: 'pull_in_progress'});
  assert.equal((await f.push(frame(2), {role: 'laptop'})).status, 200);
  await settle();
  assert.equal(resolved, false);
  assert.equal((await f.push(frame(3), {role: 'phone'})).status, 200);
  assert.deepEqual(await bodyOf(await waiting), {messages: [frame(3)]});
  assert.deepEqual(await bodyOf(await f.pull('phone')), {messages: [frame(2)]});
  assert.equal(f.mailbox.waiters.laptop, null);
});

test('default and explicit longpoll timeouts release the role slot', async () => {
  const f = fixture();
  const waiting = f.request('/v1/pull', {role: 'phone'});
  await settle();
  await f.clock.advance(19999);
  assert.ok(f.mailbox.waiters.phone);
  await f.clock.advance(1);
  assert.deepEqual(await bodyOf(await waiting), {messages: []});
  const second = f.pull('phone', 1);
  await settle();
  await f.clock.advance(1000);
  assert.deepEqual(await bodyOf(await second), {messages: []});
});

test('aborted pull releases waiter and does not consume future frames', async () => {
  const f = fixture();
  const controller = new AbortController();
  const waiting = f.pull('laptop', 20, {signal: controller.signal});
  await settle();
  controller.abort();
  assert.equal((await waiting).status, 499);
  assert.equal(f.mailbox.waiters.laptop, null);
  await f.push(frame());
  assert.deepEqual(await bodyOf(await f.pull()), {messages: [frame()]});
});

test('rolling rate limit is role-specific, has Retry-After, and releases at one minute', async () => {
  const f = fixture('3');
  for (let i = 1; i <= 3; i++) assert.equal((await f.push(frame(i))).status, 200);
  const limited = await f.pull('phone');
  assert.equal(limited.status, 429);
  assert.deepEqual(await bodyOf(limited), {error: 'rate_limited'});
  assert.equal(limited.headers.get('retry-after'), '60');
  assert.equal((await f.pull('laptop')).status, 200);
  await f.clock.advance(60000);
  assert.equal((await f.push(frame(4))).status, 200);
});

test('invalid rate configuration fails closed and unexpected failures have no stack or reflection', async () => {
  const f = fixture('601');
  assert.equal((await f.push(frame())).status, 503);
  const g = fixture();
  g.env.PERSONAL_MAILBOX.get = () => { throw new Error(`secret ${TOKENS.phone}`); };
  const response = await g.push(frame());
  assert.equal(response.status, 503);
  assert.deepEqual(await bodyOf(response), {error: 'unavailable'});
});

test('no persistent storage is used and recreation loses messages/receipts', async () => {
  const f = fixture();
  await f.push(frame());
  const restarted = new PersonalMailbox(new Proxy({}, {get() { throw new Error('storage forbidden'); }}), f.env, f.clock);
  const response = await restarted.fetch(new Request('https://mailbox.internal/v1/pull?wait=0', {headers: {'x-mailbox-role': 'laptop'}}));
  assert.deepEqual(await bodyOf(response), {messages: []});
  assert.equal((await restarted.fetch(new Request('https://mailbox.internal/v1/pull?wait=0'))).status, 403);
});

test('final safe boundaries: no origin privilege, bearer forwarding, plaintext extras or stale waiter', async () => {
  const f = fixture();
  const target = f.env.PERSONAL_MAILBOX.get;
  f.env.PERSONAL_MAILBOX.get = id => {
    const stub = target(id);
    return {fetch(request) {
      assert.equal(request.headers.has('Authorization'), false);
      assert.equal(request.headers.has('Origin'), false);
      return stub.fetch(request);
    }};
  };
  assert.equal((await f.push(frame(), {token: 'x'.repeat(257)})).status, 401);
  assert.equal((await f.push({...frame(), v: true})).status, 400);
  assert.equal((await f.push({...frame(), plaintext: 'never forward this'})).status, 400);
  assert.equal(f.calls.length, 0);
  const sent = await f.push(frame(), {headers: {Origin: 'https://attacker.invalid', 'x-mailbox-role': 'laptop'}});
  assert.equal(sent.status, 200);
  assert.equal(sent.headers.has('access-control-allow-origin'), false);
  assert.deepEqual((await bodyOf(await f.pull('laptop'))).messages, [frame()]);
  const timeout = f.pull('laptop', 1);
  await settle();
  await f.clock.advance(1000);
  assert.deepEqual(await bodyOf(await timeout), {messages: []});
  assert.equal((await f.push(frame(2))).status, 200);
  assert.deepEqual((await bodyOf(await f.pull('laptop'))).messages, [frame(2)]);
});

test('manifest uses one SQLite Durable Object binding and disabled observability with no secrets', async () => {
  const config = JSON.parse(await readFile(new URL('../wrangler.jsonc', import.meta.url), 'utf8'));
  assert.equal(config.name, 'storylens-personal-link');
  assert.equal(config.compatibility_date, '2026-10-01');
  assert.deepEqual(config.durable_objects.bindings, [{name: 'PERSONAL_MAILBOX', class_name: 'PersonalMailbox'}]);
  assert.deepEqual(config.migrations, [{tag: 'v1', new_sqlite_classes: ['PersonalMailbox']}]);
  assert.equal(config.observability.enabled, false);
  assert.equal(config.observability.logs.enabled, false);
  assert.equal(config.vars.RATE_LIMIT_PER_MINUTE, '600');
  assert.equal('PHONE_TOKEN_HASH' in config.vars, false);
  assert.equal('LAPTOP_TOKEN_HASH' in config.vars, false);
  const source = await readFile(new URL('../src/index.js', import.meta.url), 'utf8');
  assert.equal(/console\.|\.storage\b|\.sql\b|Access-Control-Allow-Origin|targetURL/.test(source), false);
});
