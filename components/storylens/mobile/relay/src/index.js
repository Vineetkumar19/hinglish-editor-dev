export const LIMITS = Object.freeze({
  MAX_BODY_BYTES: 256 * 1024,
  MAX_DATA_BYTES: 180 * 1024,
  MAX_QUEUE_BYTES: 8 * 1024 * 1024,
  MAX_FRAMES: 64,
  MAX_PULL: 8,
  TTL_MS: 120000,
  MAX_WAIT_SECONDS: 20,
  MAX_RATE_PER_MINUTE: 600,
  BODY_READ_TIMEOUT_MS: 10000
});

const ROLES = ['phone', 'laptop'];
const textEncoder = new TextEncoder();
const runtimeClock = {now: () => Date.now(), setTimeout: (fn, ms) => setTimeout(fn, ms), clearTimeout: id => clearTimeout(id)};

class MailboxError extends Error {
  constructor(status, code, headers = {}) {
    super(code);
    this.status = status;
    this.code = code;
    this.headers = headers;
  }
}

function json(value, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      ...extraHeaders,
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer'
    }
  });
}

function failure(error) {
  if (error instanceof MailboxError) return json({error: error.code}, error.status, error.headers);
  return json({error: 'unavailable'}, 503);
}

function requireMethod(request, expected) {
  if (request.method !== expected) throw new MailboxError(405, 'method_not_allowed', {Allow: expected});
}

function waitSeconds(url) {
  const keys = [...url.searchParams.keys()];
  if (keys.some(key => key !== 'wait') || keys.length > 1) throw new MailboxError(400, 'invalid_query');
  const raw = url.searchParams.get('wait');
  if (raw === null) return LIMITS.MAX_WAIT_SECONDS;
  if (!/^(?:0|[1-9][0-9]?)$/.test(raw) || Number(raw) > LIMITS.MAX_WAIT_SECONDS) {
    throw new MailboxError(400, 'invalid_query');
  }
  return Number(raw);
}

function bodyHeaders(request) {
  if (!/^application\/json(?:\s*;\s*charset=utf-8)?\s*$/i.test(request.headers.get('content-type') || '')) {
    throw new MailboxError(415, 'unsupported_media_type');
  }
  if (request.headers.has('content-encoding')) throw new MailboxError(415, 'unsupported_media_type');
  const length = request.headers.get('content-length');
  if (length !== null) {
    if (!/^(?:0|[1-9][0-9]*)$/.test(length)) throw new MailboxError(400, 'invalid_length');
    if (Number(length) > LIMITS.MAX_BODY_BYTES) throw new MailboxError(413, 'body_too_large');
  }
}

async function readEnvelope(request) {
  if (!request.body) throw new MailboxError(400, 'invalid_envelope');
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  let timer;
  const timeout = new Promise((_resolve, reject) => {
    timer = setTimeout(() => reject(new MailboxError(408, 'body_timeout')), LIMITS.BODY_READ_TIMEOUT_MS);
  });
  try {
    for (;;) {
      const {done, value} = await Promise.race([reader.read(), timeout]);
      if (done) break;
      total += value.byteLength;
      if (total > LIMITS.MAX_BODY_BYTES) throw new MailboxError(413, 'body_too_large');
      chunks.push(value);
    }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    let envelope;
    try { envelope = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes)); }
    catch { throw new MailboxError(400, 'invalid_envelope'); }
    return validateEnvelope(envelope);
  } catch (error) {
    // Cancellation must not wait for an uncooperative upload source.
    void reader.cancel().catch(() => {});
    throw error;
  } finally {
    clearTimeout(timer);
    reader.releaseLock();
  }
}

function validBase64url(value, minimum, maximum) {
  if (typeof value !== 'string' || value.length > Math.ceil(maximum * 4 / 3) || !/^[A-Za-z0-9_-]+$/.test(value)) return false;
  if (value.length % 4 === 1) return false;
  let decoded;
  try { decoded = atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)); }
  catch { return false; }
  if (decoded.length < minimum || decoded.length > maximum) return false;
  return btoa(decoded).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '') === value;
}

export function validateEnvelope(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).length !== 4 || !['v', 'id', 'nonce', 'data'].every(key => Object.hasOwn(value, key)) ||
      value.v !== 1 || typeof value.id !== 'string' || !/^[a-fA-F0-9][a-fA-F0-9-]{0,79}$/.test(value.id) ||
      !validBase64url(value.nonce, 12, 12) || !validBase64url(value.data, 16, LIMITS.MAX_DATA_BYTES)) {
    throw new MailboxError(400, 'invalid_envelope');
  }
  return {v: 1, id: value.id, nonce: value.nonce, data: value.data};
}

function hashBytes(hex) {
  return Uint8Array.from(hex.match(/../g), value => Number.parseInt(value, 16));
}

async function authenticate(request, env) {
  const phoneHash = env.PHONE_TOKEN_HASH, laptopHash = env.LAPTOP_TOKEN_HASH;
  if (typeof phoneHash !== 'string' || typeof laptopHash !== 'string' ||
      !/^[a-fA-F0-9]{64}$/.test(phoneHash) || !/^[a-fA-F0-9]{64}$/.test(laptopHash)) {
    throw new MailboxError(503, 'unavailable');
  }
  const phone = hashBytes(phoneHash), laptop = hashBytes(laptopHash);
  // Workers' native primitive, not an early-exit JavaScript string comparison.
  const equal = (a, b) => crypto.subtle.timingSafeEqual(a, b);
  if (equal(phone, laptop)) throw new MailboxError(503, 'unavailable');
  const match = /^Bearer ([A-Za-z0-9_-]{32,256})$/i.exec(request.headers.get('authorization') || '');
  if (!match) throw new MailboxError(401, 'unauthorized');
  const digest = await crypto.subtle.digest('SHA-256', textEncoder.encode(match[1]));
  const isPhone = equal(digest, phone);
  const isLaptop = equal(digest, laptop);
  if (!isPhone && !isLaptop) throw new MailboxError(401, 'unauthorized');
  return isPhone ? 'phone' : 'laptop';
}

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      if (url.protocol !== 'https:') throw new MailboxError(400, 'https_required');
      if (url.pathname === '/health') {
        requireMethod(request, 'GET');
        if (url.search) throw new MailboxError(400, 'invalid_query');
        return json({service: 'storylens-personal-link', version: 1});
      }
      let wait = 0;
      if (url.pathname === '/v1/push') {
        requireMethod(request, 'POST');
        if (url.search) throw new MailboxError(400, 'invalid_query');
        bodyHeaders(request);
      } else if (url.pathname === '/v1/pull') {
        requireMethod(request, 'GET');
        wait = waitSeconds(url);
      } else {
        throw new MailboxError(404, 'not_found');
      }
      const role = await authenticate(request, env);
      const envelope = url.pathname === '/v1/push' ? await readEnvelope(request) : null;
      if (!env.PERSONAL_MAILBOX) throw new MailboxError(503, 'unavailable');
      const id = env.PERSONAL_MAILBOX.idFromName('personal-v1');
      const stub = env.PERSONAL_MAILBOX.get(id);
      const internal = new Request(`https://mailbox.internal${url.pathname}${envelope ? '' : `?wait=${wait}`}`, {
        method: request.method,
        headers: {'x-mailbox-role': role, ...(envelope ? {'Content-Type': 'application/json'} : {})},
        body: envelope ? JSON.stringify(envelope) : undefined,
        signal: request.signal
      });
      return await stub.fetch(internal);
    } catch (error) {
      return failure(error);
    }
  }
};

export class PersonalMailbox {
  constructor(_state, env, clock = runtimeClock) {
    this.clock = clock;
    this.queues = {phone: [], laptop: []};
    this.bytes = {phone: 0, laptop: 0};
    this.receipts = {phone: new Map(), laptop: new Map()};
    this.nonces = {phone: new Map(), laptop: new Map()};
    this.requests = {phone: [], laptop: []};
    this.waiters = {phone: null, laptop: null};
    this.expiryTimer = null;
    const raw = env.RATE_LIMIT_PER_MINUTE ?? '600';
    this.rate = /^(?:[1-9][0-9]{0,2})$/.test(String(raw)) ? Number(raw) : 0;
    if (this.rate > LIMITS.MAX_RATE_PER_MINUTE) this.rate = 0;
  }

  prune() {
    const now = this.clock.now();
    for (const role of ROLES) {
      this.queues[role] = this.queues[role].filter(entry => entry.expiresAt > now);
      this.bytes[role] = this.queues[role].reduce((total, entry) => total + entry.bytes, 0);
      for (const [id, receipt] of this.receipts[role]) {
        if (receipt.expiresAt <= now) {
          this.receipts[role].delete(id);
          this.nonces[role].delete(receipt.nonce);
        }
      }
    }
  }

  scheduleExpiry() {
    if (this.expiryTimer !== null) this.clock.clearTimeout(this.expiryTimer);
    this.expiryTimer = null;
    let next = Infinity;
    for (const role of ROLES) {
      for (const receipt of this.receipts[role].values()) next = Math.min(next, receipt.expiresAt);
    }
    if (next !== Infinity) {
      this.expiryTimer = this.clock.setTimeout(() => {
        this.expiryTimer = null;
        this.prune();
        this.scheduleExpiry();
      }, Math.max(0, next - this.clock.now()));
    }
  }

  admit(role) {
    if (!this.rate) throw new MailboxError(503, 'unavailable');
    const now = this.clock.now();
    const recent = this.requests[role].filter(time => time > now - 60000);
    this.requests[role] = recent;
    if (recent.length >= this.rate) {
      throw new MailboxError(429, 'rate_limited', {'Retry-After': String(Math.max(1, Math.ceil((recent[0] + 60000 - now) / 1000)))});
    }
    recent.push(now);
  }

  take(role) {
    const entries = this.queues[role].splice(0, LIMITS.MAX_PULL);
    for (const entry of entries) {
      this.bytes[role] -= entry.bytes;
      entry.receipt.status = 'delivered';
    }
    return entries.map(entry => entry.envelope);
  }

  completeWaiter(role, response) {
    const waiter = this.waiters[role];
    if (!waiter) return;
    this.waiters[role] = null;
    this.clock.clearTimeout(waiter.timer);
    waiter.signal.removeEventListener('abort', waiter.abort);
    waiter.resolve(response);
  }

  async push(request, role) {
    bodyHeaders(request);
    const envelope = await readEnvelope(request);
    const serialized = JSON.stringify(envelope);
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', textEncoder.encode(serialized)));
    // Everything from duplicate check through enqueue/drain is synchronous.
    this.prune();
    const existing = this.receipts[role].get(envelope.id);
    if (existing) {
      if (!crypto.subtle.timingSafeEqual(existing.digest, digest)) throw new MailboxError(409, 'id_conflict');
      return json({id: envelope.id, status: existing.status, duplicate: true, expires_at: existing.expiresAt});
    }
    if (this.nonces[role].has(envelope.nonce)) throw new MailboxError(409, 'nonce_conflict');
    const target = role === 'phone' ? 'laptop' : 'phone';
    const bytes = textEncoder.encode(serialized).byteLength;
    if (this.queues[target].length >= LIMITS.MAX_FRAMES || this.bytes[target] + bytes > LIMITS.MAX_QUEUE_BYTES) {
      throw new MailboxError(429, 'mailbox_full', {'Retry-After': '1'});
    }
    const receipt = {digest, nonce: envelope.nonce, expiresAt: this.clock.now() + LIMITS.TTL_MS, status: 'queued'};
    this.receipts[role].set(envelope.id, receipt);
    this.nonces[role].set(envelope.nonce, envelope.id);
    this.queues[target].push({envelope, bytes, expiresAt: receipt.expiresAt, receipt});
    this.bytes[target] += bytes;
    if (this.waiters[target]) this.completeWaiter(target, json({messages: this.take(target)}));
    this.scheduleExpiry();
    return json({id: envelope.id, status: receipt.status, duplicate: false, expires_at: receipt.expiresAt});
  }

  pull(request, role, wait) {
    if (this.waiters[role]) throw new MailboxError(409, 'pull_in_progress');
    if (request.signal.aborted) throw new MailboxError(499, 'request_cancelled');
    if (this.queues[role].length || wait === 0) return json({messages: this.take(role)});
    return new Promise(resolve => {
      const abort = () => this.completeWaiter(role, json({error: 'request_cancelled'}, 499));
      const timer = this.clock.setTimeout(() => this.completeWaiter(role, json({messages: []})), wait * 1000);
      this.waiters[role] = {resolve, timer, abort, signal: request.signal};
      request.signal.addEventListener('abort', abort, {once: true});
    });
  }

  async fetch(request) {
    try {
      const role = request.headers.get('x-mailbox-role');
      if (!ROLES.includes(role)) throw new MailboxError(403, 'forbidden');
      const url = new URL(request.url);
      if (url.pathname !== '/v1/push' && url.pathname !== '/v1/pull') throw new MailboxError(404, 'not_found');
      requireMethod(request, url.pathname === '/v1/push' ? 'POST' : 'GET');
      this.admit(role);
      this.prune();
      if (url.pathname === '/v1/push') return await this.push(request, role);
      return await this.pull(request, role, waitSeconds(url));
    } catch (error) {
      return failure(error);
    }
  }
}
