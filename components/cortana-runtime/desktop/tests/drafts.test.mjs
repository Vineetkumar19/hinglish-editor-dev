import test from "node:test";
import assert from "node:assert/strict";
import { connectionLabel, draftLabel, draftRequest, previewParts, stoppedDraft } from "../src/draftState.js";

test("draft preparation preserves exact message content and subject", () => {
  const body = "  Namaste Maa! 👋\nI'll be there at 7:30.\n";
  assert.deepEqual(draftRequest({ platform: "whatsapp", recipient: " Mom ", body, subject: "ignored" }), {
    platform: "whatsapp", recipient: "Mom", body,
  });
  assert.deepEqual(draftRequest({ platform: "gmail", recipient: "person@example.com", body, subject: "  A subject  " }), {
    platform: "gmail", recipient: "person@example.com", body, subject: "  A subject  ",
  });
});

test("empty or unsupported draft requests fail before any request", () => {
  assert.throws(() => draftRequest({ platform: "unknown", recipient: "a", body: "b" }), /Choose/);
  assert.throws(() => draftRequest({ platform: "instagram", recipient: " ", body: "b" }), /recipient/);
  assert.throws(() => draftRequest({ platform: "whatsapp", recipient: "a", body: "\n " }), /exact message/);
  assert.throws(() => draftRequest({ platform: "whatsapp", recipient: "a", body: "कल मिलते हैं" }), /Roman letters/);
  assert.throws(() => draftRequest({ platform: "gmail", recipient: "a", body: "Hello", subject: "नमस्ते" }), /English/);
});

test("unknown app and draft states are never presented as successful", () => {
  assert.equal(connectionLabel("unknown"), "Not checked");
  assert.equal(connectionLabel("needs_login"), "Sign in required");
  assert.equal(draftLabel("draft_ready"), "Draft ready for your review");
  assert.equal(draftLabel("sent"), "Draft status not verified");
  assert.deepEqual(previewParts({ preview: { body: "<script>x</script>", subject: "Hi" } }), { body: "<script>x</script>", subject: "Hi" });
});

test("stopping invalidates expired draft actions while preserving exact preview", () => {
  const body = "  Keep this message\n";
  const stopped = stoppedDraft({ draft_id: "old-id", status: "draft_ready", candidates: [{ id: "c1" }], preview: { body } });
  assert.equal(stopped.draft_id, "");
  assert.equal(stopped.status, "error");
  assert.equal(stopped.preview.body, body);
  assert.deepEqual(stopped.candidates, []);
  assert.equal(stoppedDraft(null), null);
});
