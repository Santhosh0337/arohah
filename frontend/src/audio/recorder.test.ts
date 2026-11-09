import test from "node:test";
import assert from "node:assert/strict";
import { describeMicError, describeRecording, pickRecorderMime } from "./recorder.ts";

test("picks the first supported container in preference order", () => {
  assert.equal(pickRecorderMime(() => true), "audio/webm;codecs=opus");
  assert.equal(pickRecorderMime((m) => m === "audio/mp4"), "audio/mp4");
  assert.equal(pickRecorderMime(() => false), undefined);
});

test("WebM and MP4 recordings are accepted as-is; OGG must be converted", () => {
  assert.deepEqual(describeRecording("audio/webm"), { fileName: "recording.webm", accepted: true });
  assert.deepEqual(describeRecording("audio/mp4"), { fileName: "recording.m4a", accepted: true });
  assert.deepEqual(describeRecording("audio/ogg"), { fileName: "recording.wav", accepted: false });
  assert.deepEqual(describeRecording(""), { fileName: "recording.wav", accepted: false });
});

test("microphone errors map to readable messages", () => {
  const err = (name: string) => Object.assign(new Error("x"), { name });
  assert.match(describeMicError(err("NotAllowedError")), /permission was denied/);
  assert.match(describeMicError(err("NotFoundError")), /No microphone/);
  assert.match(describeMicError(err("NotReadableError")), /busy/);
  assert.match(describeMicError("weird"), /Could not start the microphone/);
});
