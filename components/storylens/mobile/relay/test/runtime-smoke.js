import assert from 'node:assert/strict';
import {createHash, randomBytes} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {Miniflare, Log, LogLevel, convertV4MiniflareOptions} from 'miniflare';

const tokens = {phone: randomBytes(32).toString('base64url'), laptop: randomBytes(32).toString('base64url')};
const digest = value => createHash('sha256').update(value).digest('hex');
const runtime = new Miniflare(convertV4MiniflareOptions({
  rootPath: fileURLToPath(new URL('..', import.meta.url)),
  scriptPath: fileURLToPath(new URL('../src/index.js', import.meta.url)),
  modules: true,
  compatibilityDate: '2026-10-01',
  host: '127.0.0.1',
  port: 0,
  log: new Log(LogLevel.NONE),
  bindings: {PHONE_TOKEN_HASH: digest(tokens.phone), LAPTOP_TOKEN_HASH: digest(tokens.laptop), RATE_LIMIT_PER_MINUTE: '600'},
  durableObjects: {PERSONAL_MAILBOX: {className: 'PersonalMailbox', useSQLite: true}},
  durableObjectsPersist: false
}));
const request = (path, role, body) => runtime.dispatchFetch(`https://relay.example${path}`, {
  method: body ? 'POST' : 'GET',
  headers: {Authorization: `Bearer ${tokens[role]}`, ...(body ? {'Content-Type': 'application/json'} : {})},
  body: body ? JSON.stringify(body) : undefined
});
try {
  assert.equal((await runtime.dispatchFetch('https://relay.example/health')).status, 200);
  assert.equal((await runtime.dispatchFetch('http://relay.example/health')).status, 400);
  assert.equal((await runtime.dispatchFetch('https://relay.example/v1/pull?wait=0')).status, 401);
  const frame = {v: 1, id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', nonce: randomBytes(12).toString('base64url'), data: randomBytes(24).toString('base64url')};
  const push = await request('/v1/push', 'phone', frame);
  assert.equal(push.status, 200, await push.clone().text());
  assert.deepEqual(await (await request('/v1/pull?wait=0', 'phone')).json(), {messages: []});
  assert.deepEqual(await (await request('/v1/pull?wait=0', 'laptop')).json(), {messages: [frame]});
  assert.equal((await (await request('/v1/push', 'phone', frame)).json()).duplicate, true);
  const waiting = request('/v1/pull?wait=1', 'phone');
  await new Promise(resolve => setTimeout(resolve, 50));
  assert.equal((await request('/v1/pull?wait=0', 'phone')).status, 409);
  const reply = {...frame, nonce: randomBytes(12).toString('base64url')};
  assert.equal((await request('/v1/push', 'laptop', reply)).status, 200);
  assert.deepEqual(await (await waiting).json(), {messages: [reply]});
  assert.deepEqual(await (await request('/v1/pull?wait=1', 'laptop')).json(), {messages: []});
  process.stdout.write('Local workerd smoke passed: native constant-time auth, SQLite-class binding, role routing, dedup, longpoll, conflict and timeout. No deployment.\n');
} finally {
  await runtime.dispose();
}
