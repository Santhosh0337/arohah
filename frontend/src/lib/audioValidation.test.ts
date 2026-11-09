import test from "node:test";
import assert from "node:assert/strict";
import {
  extensionForMime,
  fileExtension,
  validateDuration,
  validateFileFormat,
  MAX_UPLOAD_BYTES,
} from "./audioValidation.ts";

const file = (name: string, type = "", size = 1000) => ({ name, type, size });

test("accepts wav, mp3, m4a and webm, in any letter case", () => {
  assert.equal(validateFileFormat(file("a.wav", "audio/wav")), null);
  assert.equal(validateFileFormat(file("a.MP3", "audio/mpeg")), null);
  assert.equal(validateFileFormat(file("a.m4a", "audio/x-m4a")), null);
  assert.equal(validateFileFormat(file("a.webm", "audio/webm;codecs=opus")), null);
});

test("accepts a valid extension when the browser reports no type", () => {
  assert.equal(validateFileFormat(file("hum.wav", "")), null);
});

test("rejects other extensions, no extension, and non-audio types", () => {
  assert.match(validateFileFormat(file("a.ogg", "audio/ogg"))!, /Unsupported file type/);
  assert.match(validateFileFormat(file("a.flac"))!, /Unsupported/);
  assert.match(validateFileFormat(file("noext"))!, /Unsupported/);
  assert.match(validateFileFormat(file("a.wav", "text/plain"))!, /not WAV, MP3, M4A or WebM/);
});

test("rejects empty and oversized files", () => {
  assert.match(validateFileFormat(file("a.wav", "audio/wav", 0))!, /empty/);
  assert.match(validateFileFormat(file("a.wav", "audio/wav", MAX_UPLOAD_BYTES + 1))!, /limit/);
});

test("duration must be 1 to 60 seconds inclusive", () => {
  assert.equal(validateDuration(1), null);
  assert.equal(validateDuration(30), null);
  assert.equal(validateDuration(60), null);
  assert.match(validateDuration(0.5)!, /at least 1 s/);
  assert.match(validateDuration(60.01)!, /60 s or less/);
});

test("unreadable durations are errors", () => {
  for (const bad of [0, -3, NaN, Infinity]) assert.match(validateDuration(bad)!, /Could not read/);
});

test("extension and mime helpers", () => {
  assert.equal(fileExtension("My.Song.WAV"), "wav");
  assert.equal(fileExtension("x"), "");
  assert.equal(extensionForMime("audio/webm;codecs=opus"), "webm");
  assert.equal(extensionForMime("audio/mp4"), "m4a");
  assert.equal(extensionForMime("audio/ogg;codecs=opus"), null);
});
