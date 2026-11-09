import test from "node:test";
import assert from "node:assert/strict";
import { computePeaks, mixToMono, timeToX, xToTime } from "./waveform.ts";
import { encodeWav } from "./wav.ts";
import { synthesizeFixtureSamples, makeFixtureWav } from "./fixtureAudio.ts";
import { MOCK_PROJECT } from "../mocks/exampleProject.ts";

test("peaks: missing or empty audio gives no peaks and does not throw", () => {
  assert.deepEqual(computePeaks(new Float32Array(0), 100), []);
  assert.deepEqual(computePeaks(new Float32Array(10), 0), []);
  assert.deepEqual(computePeaks([], NaN), []);
  assert.deepEqual(mixToMono([]), new Float32Array(0));
});

test("peaks: min and max per bucket", () => {
  const peaks = computePeaks([0, 0.5, -0.25, 1, -1, 0.1], 3);
  assert.equal(peaks.length, 3);
  assert.deepEqual(peaks[0], { min: 0, max: 0.5 });
  assert.deepEqual(peaks[1], { min: -0.25, max: 1 });
  assert.deepEqual(peaks[2], { min: -1, max: 0.1 });
});

test("peaks: more buckets than samples still returns one peak per bucket", () => {
  const peaks = computePeaks([0.2, -0.2], 5);
  assert.equal(peaks.length, 5);
  assert.ok(peaks.every((p) => Number.isFinite(p.min) && Number.isFinite(p.max)));
});

test("mono mix averages channels", () => {
  const m = mixToMono([[1, 0], [0, 1]]);
  assert.deepEqual(Array.from(m), [0.5, 0.5]);
});

test("playhead mapping is clamped and safe for zero duration", () => {
  assert.equal(timeToX(5, 10, 200), 100);
  assert.equal(timeToX(20, 10, 200), 200);
  assert.equal(timeToX(-1, 10, 200), 0);
  assert.equal(timeToX(1, 0, 200), 0);
  assert.equal(xToTime(100, 10, 200), 5);
  assert.equal(xToTime(500, 10, 200), 10);
  assert.equal(xToTime(5, 10, 0), 0);
});

test("WAV encoder writes a valid RIFF header", () => {
  const bytes = encodeWav(new Float32Array([0, 1, -1, 0.5]), 22050);
  const v = new DataView(bytes.buffer);
  const tag = (o: number) => String.fromCharCode(...bytes.slice(o, o + 4));
  assert.equal(tag(0), "RIFF");
  assert.equal(tag(8), "WAVE");
  assert.equal(tag(36), "data");
  assert.equal(v.getUint32(40, true), 8); // 4 samples * 2 bytes
  assert.equal(v.getUint32(24, true), 22050);
  assert.equal(v.getInt16(46, true), 32767);
  assert.equal(v.getInt16(48, true), -32768);
  assert.equal(bytes.length, 44 + 8);
});

test("fixture audio is audible where notes are and silent elsewhere", () => {
  const { notes_clean, } = MOCK_PROJECT.payload;
  const dur = MOCK_PROJECT.payload.input.duration_s;
  const s = synthesizeFixtureSamples(notes_clean, dur, 8000);
  assert.equal(s.length, dur * 8000);
  const peak = (a: number, b: number) =>
    Math.max(...Array.from(s.slice(Math.floor(a * 8000), Math.floor(b * 8000))).map(Math.abs));
  assert.ok(peak(1.1, 1.3) > 0.2); // inside the second note
  assert.equal(peak(6, 7), 0); // after the last note
  assert.ok(Math.max(...Array.from(s).map(Math.abs)) <= 1);
});

test("fixture wav blob has the right type", () => {
  const blob = makeFixtureWav(MOCK_PROJECT.payload.notes_clean, 2);
  assert.equal(blob.type, "audio/wav");
  assert.equal(blob.size, 44 + 2 * 22050 * 2);
});
