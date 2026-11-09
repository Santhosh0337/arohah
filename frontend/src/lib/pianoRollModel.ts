// Piano-roll data model: which notes to show and where to draw them. Pure.

import type { Note, Payload } from "../api/types.ts";

export type RollView = "raw" | "clean";

/** Raw view reads notes_raw, clean view reads notes_clean (contract section 1). */
export function selectNotes(
  payload: Pick<Payload, "notes_raw" | "notes_clean">,
  view: RollView,
): Note[] {
  return view === "raw" ? payload.notes_raw : payload.notes_clean;
}

export interface PitchRange {
  low: number;
  high: number;
}

/** Shows at least one octave plus a margin, and always includes every note. */
export function pitchRange(notes: Note[], margin = 2, minSpan = 12): PitchRange {
  if (notes.length === 0) return { low: 55, high: 55 + minSpan };
  let lo = Infinity;
  let hi = -Infinity;
  for (const n of notes) {
    if (n.pitch < lo) lo = n.pitch;
    if (n.pitch > hi) hi = n.pitch;
  }
  lo -= margin;
  hi += margin;
  const missing = minSpan - (hi - lo);
  if (missing > 0) {
    lo -= Math.floor(missing / 2);
    hi += Math.ceil(missing / 2);
  }
  return { low: Math.max(0, Math.floor(lo)), high: Math.min(127, Math.ceil(hi)) };
}

/** Time axis length: the clip length, or the last note end if that is longer. */
export function timeSpan(notes: Note[], durationS: number): number {
  const last = notes.reduce((m, n) => Math.max(m, n.end), 0);
  return Math.max(durationS > 0 ? durationS : 0, last, 1);
}

export interface NoteRect {
  index: number;
  x: number;
  y: number;
  w: number;
  h: number;
  /** 0.35 to 1, from velocity */
  alpha: number;
  /** null confidence is drawn differently from low confidence */
  confidence: number | null;
}

export interface Layout {
  width: number;
  height: number;
  range: PitchRange;
  span: number;
}

export function layoutNotes(notes: Note[], layout: Layout): NoteRect[] {
  const { width, height, range, span } = layout;
  const rows = range.high - range.low + 1;
  const rowH = height / rows;
  return notes.map((n, index) => {
    const x = (n.start / span) * width;
    const w = Math.max(2, ((n.end - n.start) / span) * width);
    const y = (range.high - n.pitch) * rowH;
    const vel = Math.min(127, Math.max(1, n.velocity));
    return {
      index,
      x,
      y,
      w,
      h: Math.max(2, rowH - 1),
      alpha: 0.35 + 0.65 * (vel / 127),
      confidence: n.confidence,
    };
  });
}

/** Topmost note under a point, or -1. */
export function hitTest(rects: NoteRect[], x: number, y: number): number {
  for (let i = rects.length - 1; i >= 0; i--) {
    const r = rects[i];
    if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return r.index;
  }
  return -1;
}

export const confidenceLabel = (c: number | null) =>
  c === null ? "unknown" : `${Math.round(c * 100)}%`;
