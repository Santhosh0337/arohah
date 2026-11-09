// MOCK FIXTURE. Development only. NOT real pipeline or Gnani output.
//
// Shape follows docs/API_CONTRACT.md section 9 ("shape only; not real data").
// The real sample library comes from real pipeline runs (bible 17.3), never
// from this file. Nothing in production code should import from src/mocks
// except the dev fixture view in App.tsx.

import type { Project } from "../api/types";

export const MOCK_FIXTURE_NOTICE =
  "Mock fixture: shape-only example data, not a real recording or analysis.";

export const MOCK_PROJECT: Project = {
  id: "650000000000000000000001",
  name: "MOCK fixture: example hum",
  origin: "user",
  created_at: "2026-11-08T09:00:00Z",
  updated_at: "2026-11-08T09:00:05Z",
  version_id: "650000000000000000000002",
  payload: {
    input: {
      mode: "sing",
      language: "hi-IN",
      mixed_language: false,
      audio_file_id: "650000000000000000000003",
      duration_s: 8.0,
    },
    lyrics: [
      { text: "चाँद", start: 0.4, end: 1.2, note_index: 0, confidence: 0.62 },
      { text: "रात", start: 1.4, end: 2.0, note_index: 2, confidence: 0.31 },
      { text: "गीत", start: 2.2, end: 3.0, note_index: 4, confidence: null },
    ],
    notes_raw: [
      { pitch: 60, start: 0.4, end: 0.9, velocity: 80, confidence: 0.8 },
      { pitch: 62, start: 1.0, end: 1.4, velocity: 78, confidence: 0.7 },
      { pitch: 64, start: 1.5, end: 2.1, velocity: 82, confidence: 0.75 },
      { pitch: 65, start: 2.2, end: 2.6, velocity: 76, confidence: 0.6 },
      { pitch: 67, start: 2.7, end: 3.4, velocity: 84, confidence: 0.72 },
      { pitch: 64, start: 3.5, end: 4.2, velocity: 80, confidence: 0.55 },
    ],
    notes_clean: [
      { pitch: 60, start: 0.5, end: 1.0, velocity: 80, confidence: 0.8 },
      { pitch: 62, start: 1.0, end: 1.5, velocity: 78, confidence: 0.7 },
      { pitch: 64, start: 1.5, end: 2.0, velocity: 82, confidence: 0.75 },
      { pitch: 65, start: 2.0, end: 2.5, velocity: 76, confidence: 0.6 },
      { pitch: 67, start: 2.5, end: 3.5, velocity: 84, confidence: 0.72 },
      { pitch: 64, start: 3.5, end: 4.0, velocity: 80, confidence: 0.55 },
    ],
    analysis: {
      bpm: 92,
      bpm_source: "auto",
      key: { tonic: "C", mode: "major", confidence: 0.7 },
      scale_matches: [
        { name: "Bilawal / Shankarabharanam", score: 0.81 },
        { name: "Khamaj", score: 0.66 },
        { name: "Yaman / Kalyani", score: 0.58 },
      ],
      sa_override: null,
      mood: { label: "romantic", reason: "major key, moderate tempo" },
    },
    arrangement: {
      style: { name: "keherwa", variation: "simple" },
      style_suggestions: [
        { name: "keherwa", kind: "tala", score: 0.8, reason: "moderate tempo, folk feel" },
        { name: "pop", kind: "genre", score: 0.62, reason: "major key, steady pulse" },
        { name: "romantic", kind: "genre", score: 0.55, reason: "mood match" },
      ],
      meter: { beats_per_bar: 8, grouping: [4, 4] },
      chords: [
        { bar: 1, start: 0.0, end: 5.2, root: "C", quality: "maj", alternatives: [] },
        { bar: 2, start: 5.2, end: 10.4, root: "G", quality: "maj", alternatives: [{ root: "E", quality: "min" }] },
      ],
      bass: [
        { pitch: 36, start: 0.0, end: 1.3, velocity: 90, confidence: null },
        { pitch: 43, start: 5.2, end: 6.5, velocity: 90, confidence: null },
      ],
      percussion: {
        pattern_id: "keherwa-simple",
        name: "Keherwa",
        steps_per_beat: 2,
        bar_events: [
          { voice: "bayan", step: 0, velocity: 100 },
          { voice: "dayan", step: 2, velocity: 80 },
        ],
      },
      instruments: [{ name: "Harmonium", reason: "folk style" }],
      intensity_plan: [{ from_bar: 1, to_bar: 2, layers: ["melody", "bass"] }],
      commentary: "",
    },
    tts: null,
    warnings: [
      {
        code: "provider_mock",
        message: "Fixture data. No provider was called.",
        stage: "lyrics",
      },
    ],
  },
};
