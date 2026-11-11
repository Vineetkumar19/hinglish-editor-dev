import test from "node:test";
import assert from "node:assert/strict";
import { apiFetch } from "../src/api.js";

test("JSON and audio are transferred through the bridge without exposing a token", async () => {
  let request;
  globalThis.window = { cortana: {
    request: async (...args) => {
      request = args;
      return { status: 200, contentType: "application/json", bytes: new TextEncoder().encode('{"ok":true}') };
    },
    abortRequest: async () => {},
  } };
  const json = await apiFetch("/api/chat", { method: "POST", body: JSON.stringify({ message: "नमस्ते" }) });
  assert.deepEqual(await json.json(), { ok: true });
  assert.equal(request[1], "/api/chat");
  assert.equal(JSON.parse(request[2].body).message, "नमस्ते");
  assert.equal(request[2].headers, undefined);
  const audio = new FormData();
  audio.append("audio", new Blob(["audio"], { type: "audio/webm" }), "recording.webm");
  await apiFetch("/api/stt", { method: "POST", body: audio });
  assert.equal(request[2].form[0].type, "audio/webm");
  assert.equal(new TextDecoder().decode(request[2].form[0].bytes), "audio");
});

test("abort rejects promptly and forwards cancellation to main", async () => {
  let cancelled = null;
  globalThis.window = { cortana: { request: () => new Promise(() => {}), abortRequest: async (id) => { cancelled = id; } } };
  const controller = new AbortController();
  const pending = apiFetch("/api/chat", { method: "POST", body: "{}", signal: controller.signal });
  controller.abort();
  await assert.rejects(pending, { name: "AbortError" });
  assert.match(cancelled, /^[a-z0-9-]+$/);
});

test("browser preview fails closed without a desktop bridge", async () => {
  globalThis.window = {};
  await assert.rejects(apiFetch("/api/status"), /desktop launcher/);
});
