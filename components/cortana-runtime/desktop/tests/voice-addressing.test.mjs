import assert from "node:assert/strict";
import { test } from "node:test";
import { addressedSpeech, commandWindowOpen, COMMAND_WINDOW_MS } from "../src/voiceAddressing.js";

test("ordinary nearby speech never becomes a standby command", () => {
  assert.equal(addressedSpeech({ detected: false, transcript: "Open Gmail and write a mail" }, false), "");
  assert.equal(commandWindowOpen({ open: false, expiresAt: Infinity }), false);
});

test("wake plus command uses only the addressed remainder", () => {
  assert.equal(addressedSpeech({ detected: true, transcript: "Hey Cortana open WhatsApp", remainder: "open WhatsApp" }, false), "open WhatsApp");
  assert.equal(addressedSpeech({ detected: true, transcript: "Hey Cortana", remainder: "" }, true), "");
});

test("an explicit activation accepts one utterance within its bounded window", () => {
  const activation = { open: true, expiresAt: 1000 + COMMAND_WINDOW_MS };
  assert.equal(commandWindowOpen(activation, 1001), true);
  assert.equal(addressedSpeech({ detected: false, transcript: "open Calculator" }, true), "open Calculator");
  assert.equal(commandWindowOpen(activation, activation.expiresAt), false);
  activation.open = false;
  assert.equal(commandWindowOpen(activation, 1002), false);
});

test('continuous conversation accepts consecutive turns without expiring', () => {
  const conversation = { open: true, continuous: true, expiresAt: 0 };
  for (const now of [0, 12000, 86400000]) {
    assert.equal(commandWindowOpen(conversation, now), true);
    assert.equal(addressedSpeech({ transcript: 'next question' }, true), 'next question');
  }
  conversation.open = false;
  assert.equal(commandWindowOpen(conversation), false);
});
