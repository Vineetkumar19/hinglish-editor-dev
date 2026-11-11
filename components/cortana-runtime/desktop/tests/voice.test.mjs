import assert from "node:assert/strict";
import { test } from "node:test";
import { isUsableSpeech, recordClip } from "../src/useVoicePipeline.js";

class FakeRecorder {
  state = "inactive";
  mimeType = "audio/webm";
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["spoken command"]) });
    this.onstop?.();
  }
}

test("Hindi, Hinglish, numbers and short confirmations remain usable", () => {
  for (const text of ["हाँ", "नहीं", "रुको", "Chrome kholo", "YouTube खोलो", "no", "5", "y"]) {
    assert.equal(isUsableSpeech(text), true, text);
  }
  for (const text of ["", " ", "...", "।", "?!"]) assert.equal(isUsableSpeech(text), false, text);
});

test("finishing a recording emits one blob and cleans event handlers", async () => {
  const clip = recordClip({}, { Recorder: FakeRecorder, milliseconds: 10000 });
  clip.finish();
  clip.finish();
  const result = await clip.promise;
  assert.equal(await result.text(), "spoken command");
  assert.equal(clip.recorder.state, "inactive");
  assert.equal(clip.recorder.onstop, null);
});

test("Stop aborts active capture and late recorder events cannot submit audio", async () => {
  const controller = new AbortController();
  const clip = recordClip({}, { signal: controller.signal, Recorder: FakeRecorder, milliseconds: 10000 });
  controller.abort();
  clip.finish();
  await assert.rejects(clip.promise, { name: "AbortError" });
  assert.equal(clip.recorder.state, "inactive");
  assert.equal(clip.recorder.ondataavailable, null);
});

test("an already aborted operation never starts microphone recording", async () => {
  const controller = new AbortController();
  controller.abort();
  class NeverStart extends FakeRecorder {
    start() { assert.fail("aborted operation started a recorder"); }
  }
  const clip = recordClip({}, { signal: controller.signal, Recorder: NeverStart });
  await assert.rejects(clip.promise, { name: "AbortError" });
});

test("recorder failures reject promptly without leaving a timer alive", async () => {
  class BrokenRecorder extends FakeRecorder {
    start() { throw new Error("Device disconnected"); }
  }
  const clip = recordClip({}, { Recorder: BrokenRecorder, milliseconds: 10000 });
  await assert.rejects(clip.promise, /Device disconnected/);
  assert.equal(clip.recorder.onstop, null);
});
