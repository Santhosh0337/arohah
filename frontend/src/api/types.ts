// Types for docs/API_CONTRACT.md (v0.1). Keep in step with the contract:
// change the contract by PR first, then update this file.

// ---- Fixed vocabularies (contract section 0) ----
export type InputMode = "hum" | "sing" | "speak";
export type KeyMode = "major" | "minor";
export type BpmSource = "auto" | "user";
export type MoodLabel =
  | "calm"
  | "romantic"
  | "joyful"
  | "tense"
  | "melancholic"
  | "energetic";
export type Variation = "simple" | "busy";
export type StyleName =
  | "teen-taal"
  | "keherwa"
  | "dadra"
  | "rupak"
  | "jhaptal"
  | "adi-talam"
  | "pop"
  | "cinematic"
  | "folk"
  | "electronic"
  | "romantic"
  | "classical";
export type Origin = "user" | "sample";
export type ChordQuality = "maj" | "min" | "dim";
export type Layer = "melody" | "chords" | "bass" | "percussion" | "pad";
export type PercussionVoice =
  | "kick"
  | "snare"
  | "hat"
  | "dayan"
  | "bayan"
  | "shaker"
  | "clap";

// ---- Project payload (contract section 1) ----
export interface Note {
  pitch: number; // MIDI note number, middle C = 60
  start: number; // seconds
  end: number;
  velocity: number; // 1 to 127
  confidence: number | null;
}

export interface LyricWord {
  text: string;
  start: number | null;
  end: number | null;
  note_index: number | null;
  confidence: number | null;
}

export interface Chord {
  bar: number; // 1-indexed
  start: number;
  end: number;
  root: string;
  quality: ChordQuality;
  alternatives: { root: string; quality: string }[];
}

export interface Percussion {
  pattern_id: string;
  name: string;
  steps_per_beat: number;
  bar_events: { voice: string; step: number; velocity: number }[];
}

export interface Warning {
  code: string;
  message: string;
  stage: string;
}

export interface Payload {
  input: {
    mode: InputMode;
    language: string | null;
    mixed_language: boolean;
    audio_file_id: string;
    duration_s: number;
  };
  lyrics: LyricWord[];
  notes_raw: Note[];
  notes_clean: Note[];
  analysis: {
    bpm: number;
    bpm_source: BpmSource;
    key: { tonic: string; mode: KeyMode; confidence: number | null };
    scale_matches: { name: string; score: number }[];
    sa_override: string | null;
    mood: { label: string; reason: string };
  };
  arrangement: {
    style: { name: string; variation: Variation };
    style_suggestions: {
      name: string;
      kind: "tala" | "genre";
      score: number;
      reason: string;
    }[];
    meter: { beats_per_bar: number; grouping: number[] };
    chords: Chord[];
    bass: Note[];
    percussion: Percussion;
    instruments: { name: string; reason: string }[];
    intensity_plan: { from_bar: number; to_bar: number; layers: string[] }[];
    commentary: string;
  };
  tts: { language: string; text: string; audio_file_id: string } | null;
  warnings: Warning[];
}

export interface Project {
  id: string;
  name: string;
  origin: Origin;
  seed_id?: string;
  derived_from_seed_id?: string;
  created_at: string;
  updated_at: string;
  version_id: string;
  payload: Payload;
}

// ---- Routes (contract section 2) ----
export interface HealthResponse {
  status: string;
  mongo: string;
  providers: { prisma: "live" | "mock"; timbre: "live" | "mock"; llm: "live" | "mock" };
}

export type SupportStatus = "confirmed" | "unconfirmed" | "unsupported";

export interface Language {
  code: string;
  name: string;
  native_name: string;
  script: string;
  font_family: string;
  prisma: SupportStatus;
  timbre: SupportStatus;
  command_keywords: boolean;
  demo: boolean;
  tested: boolean;
}

export interface StyleInfo {
  name: string;
  label: string;
  kind: "tala" | "genre";
  beats_per_bar: number;
  grouping: number[];
}

export interface CreateProjectInput {
  audio: Blob | File;
  mode: InputMode;
  language?: string; // required unless mode is "hum"
  mixed_language?: boolean;
  name?: string;
}

export interface CreateProjectResponse {
  id: string;
  status: "running"; // [confirm] in the contract: async with polling
}

export type StageName =
  | "ingest"
  | "pitch"
  | "cleanup"
  | "key_bpm"
  | "scale"
  | "lyrics"
  | "arrange";
export type StageState = "pending" | "running" | "done" | "skipped" | "failed";

export interface ProjectStatus {
  status: "running" | "done" | "error";
  stage: StageName | null;
  stages: { name: StageName; state: StageState }[];
  error: string | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  origin: Origin;
  mode: InputMode;
  language: string | null;
  duration_s: number;
  bpm: number;
  key: string; // e.g. "C major"
  updated_at: string;
}

export interface ReanalyzeInput {
  bpm?: number;
  sa?: string;
  cleanup?: boolean;
  snap_to_scale?: boolean;
}

export interface ArrangeInput {
  style?: StyleName;
  variation?: Variation;
  mood?: MoodLabel;
}

export interface VersionInfo {
  version_id: string;
  label: string;
  created_at: string;
}

export interface ExplainInput {
  language: string;
  voice?: string | null;
}

export interface ExplainResponse {
  text: string;
  language: string;
  audio_url: string; // path such as "/api/audio/<file_id>"
  cached: boolean;
}

// ---- Voice (contract sections 2.14 and 4) ----
export type VoiceIntent =
  | { name: "play_stop"; params: { action: "play" | "stop" } }
  | {
      name: "tempo_change";
      params: { mode: "faster" | "slower" | "set"; amount?: number };
    }
  | { name: "change_style"; params: { style: StyleName } }
  | { name: "change_mood"; params: { mood: MoodLabel } }
  | { name: "explain"; params: Record<string, never> }
  | { name: "save_project"; params: { label?: string } };

export type ParsedIntent = VoiceIntent & {
  confidence: number;
  source: "keyword" | "llm";
};

export interface VoiceCommandInput {
  audio: Blob | File;
  language: string;
  project_id?: string;
}

export interface VoiceCommandResponse {
  transcript: string;
  language: string;
  intent: ParsedIntent | null; // null when nothing matches
  needs_confirmation: boolean;
  suggestions?: string[]; // example commands, present when intent is null
}

// ---- Errors (contract section 3) ----
export type ErrorCode =
  | "validation_error"
  | "audio_too_short"
  | "audio_too_long"
  | "unsupported_format"
  | "not_found"
  | "rate_limited"
  | "provider_unavailable"
  | "provider_timeout"
  | "internal";

export interface ApiErrorBody {
  error: { code: ErrorCode | string; message: string; details?: Record<string, unknown> };
}
