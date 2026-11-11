const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { validateRequest, trustedUrl, resolveAsset, loginOptions, loginEntryEnabled } = require("../electron/security.cjs");

test("the bridge accepts only exact local route and verb pairs", () => {
  assert.equal(validateRequest("/api/chat", { method: "POST", body: '{"message":"hello"}' }).method, "POST");
  assert.equal(validateRequest("/api/audit/log?limit=60").pathname, "/api/audit/log");
  assert.equal(validateRequest("/api/tasks/a-f-123/cancel", { method: "POST" }).pathname, "/api/tasks/a-f-123/cancel");
  for (const route of ["http://127.0.0.1:8000/api/chat", "//evil.test", "/api/chat/../status", "/api/%63hat", "/api/chat#x", "/api/chat\\x", "/docs", "/api/screen/capture"]) {
    assert.throws(() => validateRequest(route, { method: "POST" }));
  }
  assert.throws(() => validateRequest("/api/chat", { method: "DELETE" }));
  assert.throws(() => validateRequest("/api/audit/log?limit=60&url=https://evil.test"));
  assert.throws(() => validateRequest("/api/chat", { method: "POST", body: "x".repeat(100_001) }));
});

test("audio uploads cannot be sent to unrelated endpoints", () => {
  assert.equal(validateRequest("/api/stt", { method: "POST", form: [] }).pathname, "/api/stt");
  assert.equal(validateRequest("/api/stt-preview", { method: "POST", form: [] }).pathname, "/api/stt-preview");
  assert.throws(() => validateRequest("/api/chat", { method: "POST", form: [{}] }));
});

test("communication bridge permits drafts and connection setup but no send endpoint", () => {
  assert.equal(validateRequest("/api/integrations/status").pathname, "/api/integrations/status");
  assert.equal(validateRequest("/api/integrations/gmail/open", { method: "POST" }).method, "POST");
  assert.equal(validateRequest("/api/drafts/prepare", { method: "POST", body: "{}" }).method, "POST");
  assert.equal(validateRequest("/api/drafts/cancel", { method: "POST" }).method, "POST");
  assert.throws(() => validateRequest("/api/drafts/cancel", { method: "GET" }));
  assert.equal(validateRequest("/api/drafts/abc-123/resume", { method: "POST" }).method, "POST");
  assert.equal(validateRequest("/api/drafts/abc-123/select", { method: "POST", body: '{"candidate_id":"c1"}' }).method, "POST");
  for (const route of ["/api/drafts/abc-123/send", "/api/integrations/gmail/send", "/api/integrations/other/open", "/api/drafts/abc-123/delete"]) {
    assert.throws(() => validateRequest(route, { method: "POST" }));
  }
});

test("main and floating pages have distinct sender identities", () => {
  assert.equal(trustedUrl("app://cortana/index.html"), true);
  assert.equal(trustedUrl("app://cortana/floating.html"), false);
  assert.equal(trustedUrl("app://cortana/floating.html", false, "floating"), true);
  for (const url of ["https://cortana/index.html", "app://cortana.evil/index.html", "app://user@cortana/index.html", "file:///D:/Cortana/desktop/dist/index.html", "http://localhost:5173"]) {
    assert.equal(trustedUrl(url), false);
  }
  assert.equal(trustedUrl("http://localhost:5173", true), true);
  assert.equal(trustedUrl("http://localhost:5173.evil.test", true), false);
});

test("custom protocol only resolves files within its UI roots", () => {
  const dist = path.resolve("dist");
  const shell = path.resolve("electron");
  assert.equal(resolveAsset("app://cortana/assets/main.js", dist, shell), path.join(dist, "assets", "main.js"));
  assert.equal(resolveAsset("app://cortana/floating.html", dist, shell), path.join(shell, "floating.html"));
  for (const url of ["app://evil/index.html", "app://cortana/%2f..%2f..%2fsecret.json", "app://cortana/%5c..%5csecret.json", "app://cortana/%00", "app://cortana/index.html?path=C:/secret"]) {
    assert.equal(resolveAsset(url, dist, shell), null);
  }
});

test("unpackaged login arguments leave quoting to Electron and preserve the background flag", () => {
  assert.deepEqual(loginOptions("C:\\Electron\\electron.exe", "D:\\My App\\desktop", false), {
    path: "C:\\Electron\\electron.exe", args: ["D:\\My App\\desktop", "--background"],
  });
  assert.deepEqual(loginOptions("C:\\Cortana.exe", "", true).args, ["--background"]);
});

test("startup status checks Cortana's exact named entry and Windows enabled state", () => {
  const entry = { name: "Cortana", path: "C:\\Electron\\electron.exe", args: ["D:\\My App\\desktop"], scope: "user", enabled: true };
  const check = (item) => loginEntryEnabled({ openAtLogin: false, launchItems: [item] }, entry.path, entry.args[0], false);
  assert.equal(check(entry), true);
  assert.equal(check({ ...entry, enabled: false }), false);
  assert.equal(check({ ...entry, name: "Another Electron app" }), false);
  assert.equal(check({ ...entry, args: ['"D:\\My App\\desktop"'] }), false);
  assert.equal(check({ ...entry, path: "C:\\Other\\electron.exe" }), false);
});
