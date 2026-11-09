import test from "node:test";
import assert from "node:assert/strict";
import { hitTest, layoutNotes, pitchRange, selectNotes, timeSpan } from "./pianoRollModel.ts";
import { MOCK_PROJECT } from "../mocks/exampleProject.ts";
import { formatTime, isBlackKey, noteName } from "./music.ts";

const { payload } = MOCK_PROJECT;

test("raw view reads notes_raw and clean view reads notes_clean", () => {
  assert.equal(selectNotes(payload, "raw"), payload.notes_raw);
  assert.equal(selectNotes(payload, "clean"), payload.notes_clean);
  assert.notDeepEqual(selectNotes(payload, "raw"), selectNotes(payload, "clean"));
});

test("pitch range includes every note, spans an octave, stays within MIDI", () => {
  const r = pitchRange(payload.notes_raw);
  for (const n of payload.notes_raw) assert.ok(n.pitch >= r.low && n.pitch <= r.high);
  assert.ok(r.high - r.low >= 12);
  const edge = pitchRange([{ pitch: 126, start: 0, end: 1, velocity: 80, confidence: null }]);
  assert.ok(edge.high <= 127 && edge.low >= 0);
  assert.equal(pitchRange([]).high - pitchRange([]).low, 12);
});

test("time span is at least the clip, the last note, and 1 s", () => {
  assert.equal(timeSpan(payload.notes_clean, 8), 8);
  assert.equal(timeSpan([{ pitch: 60, start: 0, end: 9, velocity: 80, confidence: null }], 8), 9);
  assert.equal(timeSpan([], 0), 1);
});

test("layout puts higher pitches higher and later notes further right", () => {
  const notes = payload.notes_clean;
  const range = pitchRange(notes);
  const rects = layoutNotes(notes, { width: 800, height: 240, range, span: 8 });
  assert.equal(rects.length, notes.length);
  const c = rects[0]; // pitch 60
  const g = rects[4]; // pitch 67
  assert.ok(g.y < c.y);
  assert.ok(g.x > c.x);
  for (const r of rects) assert.ok(r.alpha >= 0.35 && r.alpha <= 1);
});

test("velocity maps to opacity and null confidence is preserved", () => {
  const range = { low: 58, high: 70 };
  const [soft, loud] = layoutNotes(
    [
      { pitch: 60, start: 0, end: 1, velocity: 1, confidence: null },
      { pitch: 62, start: 1, end: 2, velocity: 127, confidence: 0.4 },
    ],
    { width: 100, height: 130, range, span: 2 },
  );
  assert.ok(soft.alpha < loud.alpha);
  assert.equal(soft.confidence, null);
  assert.equal(loud.confidence, 0.4);
});

test("hit test finds the note under a point and -1 elsewhere", () => {
  const range = pitchRange(payload.notes_clean);
  const rects = layoutNotes(payload.notes_clean, { width: 800, height: 240, range, span: 8 });
  const r = rects[2];
  assert.equal(hitTest(rects, r.x + 1, r.y + 1), 2);
  assert.equal(hitTest(rects, -5, -5), -1);
});

test("note names: middle C is C4", () => {
  assert.equal(noteName(60), "C4");
  assert.equal(noteName(69), "A4");
  assert.equal(noteName(61), "C#4");
  assert.equal(isBlackKey(61), true);
  assert.equal(isBlackKey(60), false);
  assert.equal(formatTime(65.34), "1:05.3");
  assert.equal(formatTime(NaN), "0:00.0");
});

test("fixture notes follow the contract ranges", () => {
  for (const n of [...payload.notes_raw, ...payload.notes_clean]) {
    assert.ok(Number.isInteger(n.pitch));
    assert.ok(Number.isInteger(n.velocity) && n.velocity >= 1 && n.velocity <= 127);
    assert.ok(n.end > n.start);
    assert.ok(n.confidence === null || (n.confidence >= 0 && n.confidence <= 1));
  }
});
