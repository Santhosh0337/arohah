// FIXTURE AUDIO. A synthetic sine-wave clip built from fixture notes so the
// waveform can be demonstrated without a recording or a backend. It is not a
// human hum and the UI labels it as a fixture.

import type { Note } from "../api/types.ts";
import { encodeWav } from "./wav.ts";

const midiToHz = (m: number) => 440 * Math.pow(2, (m - 69) / 12);

export function synthesizeFixtureSamples(
  notes: Note[],
  durationS: number,
  sampleRate = 22050,
): Float32Array {
  const out = new Float32Array(Math.max(0, Math.round(durationS * sampleRate)));
  for (const note of notes) {
    const from = Math.floor(note.start * sampleRate);
    const to = Math.min(out.length, Math.floor(note.end * sampleRate));
    const hz = midiToHz(note.pitch);
    const amp = 0.6 * (note.velocity / 127);
    const attack = 0.02 * sampleRate;
    const release = 0.06 * sampleRate;
    for (let i = Math.max(0, from); i < to; i++) {
      const t = (i - from) / sampleRate;
      const env = Math.min(1, (i - from) / attack, (to - i) / release);
      // a little vibrato so it reads as a voice-like line, not a pure beep
      const vib = 1 + 0.004 * Math.sin(2 * Math.PI * 5.5 * t);
      out[i] += amp * Math.max(0, env) * Math.sin(2 * Math.PI * hz * vib * t);
    }
  }
  return out;
}

export function makeFixtureWav(notes: Note[], durationS: number): Blob {
  const bytes = encodeWav(synthesizeFixtureSamples(notes, durationS), 22050);
  return new Blob([bytes.buffer as ArrayBuffer], { type: "audio/wav" });
}
