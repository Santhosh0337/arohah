# Arohah API Contract (v0.1, draft for the Day 0 session)

This file is the agreement between **Person A** (backend and music engine) and **Person B** (frontend, Gnani adapters, voice). Build against this file, not against each other's code.

- Where this file and `Arohah_Project_Bible.md` disagree, **this file wins** for shapes and routes; fix the bible afterwards.
- Anything marked **[confirm]** must be settled in the Day 0 session and the marker removed.
- Changes happen only through a PR that edits this file and is **approved by both of you**. Add a line to the changelog (section 11) in the same PR.

## 0. Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://localhost:8000` (dev), Render URL when deployed. All routes start with `/api`. |
| Format | JSON, UTF-8, no ASCII escaping. Text is Unicode **NFC** (bible 16.5). Uploads are `multipart/form-data`. |
| IDs | MongoDB ObjectId as a 24-character hex string (`"id"`, `"audio_file_id"`, `"version_id"`). |
| Time | Positions and durations in **seconds** (float). Timestamps (`created_at`) are ISO 8601 UTC strings. |
| Bars | 1-indexed integers. Bar length in seconds = `60 / bpm * arrangement.meter.beats_per_bar`. |
| Pitch | MIDI note numbers (integers). Middle C = 60. |
| Velocity | Integer 1 to 127. |
| Confidence | Float 0 to 1, or `null` when unknown. |
| Auth | None. CORS allows only `ALLOWED_ORIGINS`. |
| Rate limit | Pipeline and voice routes: `RATE_LIMIT_PER_MIN` per IP. Over the limit returns `429` with error code `rate_limited`. |
| Key names | Tonic names use sharps: `C, C#, D, D#, E, F, F#, G, G#, A, A#, B`. |

### Fixed vocabularies

| Name | Values |
|---|---|
| `mode` (input) | `hum`, `sing`, `speak` |
| `key.mode` | `major`, `minor` |
| `bpm_source` | `auto`, `user` |
| `mood.label` | `calm`, `romantic`, `joyful`, `tense`, `melancholic`, `energetic` |
| `style.variation` | `simple`, `busy` |
| `style.name` (ids) | `teen-taal`, `keherwa`, `dadra`, `rupak`, `jhaptal`, `adi-talam`, `pop`, `cinematic`, `folk`, `electronic`, `romantic`, `classical` |
| `origin` | `user`, `sample` |
| `chord.quality` | `maj`, `min`, `dim` |
| Layers | `melody`, `chords`, `bass`, `percussion`, `pad` |
| Percussion voices | `kick`, `snare`, `hat`, `dayan`, `bayan`, `shaker`, `clap` |

## 1. Project payload (the main data object)

Matches bible 6.11, with **additions** marked `(new)`. TypeScript shown for B; A implements the same shape with Pydantic.

```ts
interface Project {
  id: string;
  name: string;
  origin: "user" | "sample";
  seed_id?: string;                 // samples only
  derived_from_seed_id?: string;    // forks of samples
  created_at: string;
  updated_at: string;
  version_id: string;               // current version
  payload: Payload;
}

interface Payload {
  input: {
    mode: "hum" | "sing" | "speak";
    language: string | null;        // e.g. "hi-IN"; null in hum mode
    mixed_language: boolean;
    audio_file_id: string;          // stream via GET /api/audio/{id}
    duration_s: number;
  };
  lyrics: LyricWord[];              // empty array in hum mode or when unclear
  notes_raw: Note[];
  notes_clean: Note[];
  analysis: {
    bpm: number;
    bpm_source: "auto" | "user";
    key: { tonic: string; mode: "major" | "minor"; confidence: number | null };
    scale_matches: { name: string; score: number }[];   // top 3, approximate
    sa_override: string | null;     // tonic name chosen by the user
    mood: { label: string; reason: string };
  };
  arrangement: {
    style: { name: string; variation: "simple" | "busy" };
    style_suggestions: { name: string; kind: "tala" | "genre"; score: number; reason: string }[]; // (new) top 3
    meter: { beats_per_bar: number; grouping: number[] };   // (new) e.g. {7, [3,2,2]}
    chords: Chord[];
    bass: Note[];
    percussion: Percussion;
    instruments: { name: string; reason: string }[];
    intensity_plan: { from_bar: number; to_bar: number; layers: string[] }[];
    commentary: string;             // empty string if no LLM available
  };
  tts: { language: string; text: string; audio_file_id: string } | null;   // null until explain is requested
  warnings: { code: string; message: string; stage: string }[];            // (new)
}

interface Note { pitch: number; start: number; end: number; velocity: number; confidence: number | null; }

interface LyricWord {
  text: string;
  start: number | null;             // null when no timestamps are available
  end: number | null;
  note_index: number | null;        // index into notes_clean, null if unaligned
  confidence: number | null;
}

interface Chord {
  bar: number; start: number; end: number;
  root: string; quality: "maj" | "min" | "dim";
  alternatives: { root: string; quality: string }[];
}

interface Percussion {              // (new) pattern is inline so the UI needs no second fetch
  pattern_id: string;               // e.g. "keherwa-simple"
  name: string;
  steps_per_beat: number;           // e.g. 2 or 4
  bar_events: { voice: string; step: number; velocity: number }[];  // one bar, loop it
}
```

Rules:
- `warnings` carries non-fatal problems, for example `{ "code": "lyrics_unclear", "stage": "lyrics", ... }`, `lyrics_empty`, `provider_mock`, `low_pitch_confidence`. A provider failure **never fails the whole project**: the pipeline finishes without that stage and adds a warning.
- Seed (sample) projects are read-only. Any change to one creates a fork (see 2.7).
- `notes_raw` is always kept so the UI can offer A/B playback.

## 2. Routes

Owner in brackets: **[A]** or **[B]**.

### 2.1 `GET /api/health` [A]
Response `200`:
```json
{ "status": "ok", "mongo": "up", "providers": { "prisma": "live|mock", "timbre": "live|mock", "llm": "live|mock" } }
```
Provider status comes from `providers.registry.provider_status()` (B).

### 2.2 `GET /api/languages` [B]
Response `200`: `{ "languages": Language[] }` where
```ts
interface Language {
  code: string; name: string; native_name: string;
  script: string; font_family: string;
  prisma: "confirmed" | "unconfirmed" | "unsupported";
  timbre: "confirmed" | "unconfirmed" | "unsupported";
  command_keywords: boolean; demo: boolean; tested: boolean;
}
```
Source: `backend/data/languages.json` (bible 16.2). The UI enables only `prisma === "confirmed"` languages.

### 2.3 `GET /api/styles` [A] (new)
Response `200`: `{ "styles": { "name": string, "label": string, "kind": "tala"|"genre", "beats_per_bar": number, "grouping": number[] }[] }`. The UI builds style chips from this.

### 2.4 `POST /api/projects` [A]
Request (`multipart/form-data`):

| Field | Required | Notes |
|---|---|---|
| `audio` | yes | wav, mp3, m4a or webm; 1 to 60 seconds |
| `mode` | yes | `hum`, `sing`, `speak` |
| `language` | if mode is not `hum` | a code from `/api/languages` |
| `mixed_language` | no | `true` or `false`, default `false` |
| `name` | no | defaults to a timestamped name |

Response `202`: `{ "id": "...", "status": "running" }` **[confirm: async with polling, versus synchronous]**. The pipeline runs in the background; the client polls 2.5, then loads 2.7.

### 2.5 `GET /api/projects/{id}/status` [A] (new)
Response `200`:
```json
{ "status": "running|done|error",
  "stage": "pitch",
  "stages": [ { "name": "ingest", "state": "done" }, { "name": "pitch", "state": "running" } ],
  "error": null }
```
Stage names, in order: `ingest`, `pitch`, `cleanup`, `key_bpm`, `scale`, `lyrics`, `arrange`. States: `pending`, `running`, `done`, `skipped`, `failed`. The `lyrics` stage is `skipped` in hum mode. Poll about once per second.

### 2.6 `GET /api/projects` [A]
Response `200`:
```json
{ "projects": [ { "id": "...", "name": "...", "origin": "user|sample", "mode": "sing", "language": "hi-IN",
                  "duration_s": 12.4, "bpm": 92, "key": "C major", "updated_at": "..." } ] }
```
Sorted by `updated_at`, newest first. Samples appear in the same list; `origin` lets the UI show the quiet "Sample" label.

### 2.7 `GET /api/projects/{id}` [A]
Response `200`: a full `Project`. `404` if missing.

### Editing routes and the sample-fork rule
Routes 2.8 to 2.11 modify a project. **If the target project has `origin: "sample"`, the server forks it first** and applies the change to the new project: the response is `201` and the returned `Project` has a new `id`, `origin: "user"` and `derived_from_seed_id`. For normal projects the response is `200` with the same `id` and a new `version_id`. The UI must always use the `id` from the response.

### 2.8 `POST /api/projects/{id}/reanalyze` [A]
Request (JSON, all optional): `{ "bpm": 100, "sa": "D", "cleanup": true, "snap_to_scale": true }`
Response: `Project` (new version). Does not call Prisma. Synchronous.

### 2.9 `POST /api/projects/{id}/arrange` [A]
Request (JSON, all optional): `{ "style": "keherwa", "variation": "busy", "mood": "romantic" }`
Response: `Project` (new version). Synchronous. `arrangement.style_suggestions` is refreshed.

### 2.10 `PUT /api/projects/{id}/lyrics` [A]
Request: `{ "lyrics": LyricWord[] }` (text in NFC). Response: `Project`.

### 2.11 `POST /api/projects/{id}/versions` [A] (new)
Request: `{ "label": "chorus idea" }`. Response `201`: `Project`. Used by the save button and the `save_project` voice intent.
`GET /api/projects/{id}/versions` returns `{ "versions": [ { "version_id", "label", "created_at" } ] }`.

### 2.12 `POST /api/projects/{id}/duplicate` [A]
No body. Response `201`: a new `Project` (`origin: "user"`; `derived_from_seed_id` set when the source is a sample).

### 2.13 `POST /api/projects/{id}/explain` [B]
Request: `{ "language": "hi-IN", "voice": null }`
Response `200`:
```json
{ "text": "…", "language": "hi-IN", "audio_url": "/api/audio/<file_id>", "cached": true }
```
The text is built from the project's analysis values (bible 6.10). Reads the project through `repositories.get_project(id)` **[A keeps this signature stable]**. Also stores `payload.tts`.

### 2.14 `POST /api/voice/command` [B]
Request (`multipart/form-data`): `audio` (short clip), `language`, optional `project_id`.
Response `200`:
```json
{ "transcript": "…", "language": "hi-IN",
  "intent": { "name": "tempo_change", "params": { "mode": "faster", "amount": 10 },
              "confidence": 0.9, "source": "keyword|llm" },
  "needs_confirmation": false }
```
`intent` is `null` and `suggestions` lists example commands when nothing matches. **The endpoint only parses.** The UI shows the transcript and parsed intent, then performs the action (table in section 4).

### 2.15 `GET /api/audio/{file_id}` [A] (new)
Streams a GridFS file (original hum, processed audio, TTS audio) with the correct `Content-Type`. Supports `Range` requests so the waveform and player can seek.

### 2.16 Exports [A]
`GET /api/projects/{id}/export/midi` returns `audio/midi` (tracks: melody, chords, bass, drums).
`GET /api/projects/{id}/export/json` returns the analysis report as JSON (authoritative lyrics export, UTF-8).

## 3. Errors

All errors use this body:
```json
{ "error": { "code": "audio_too_long", "message": "Audio must be 60 seconds or less.", "details": {} } }
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `validation_error` | missing or invalid field |
| 400 | `audio_too_short` / `audio_too_long` | outside 1 to 60 seconds |
| 415 | `unsupported_format` | file type not accepted |
| 404 | `not_found` | unknown id |
| 429 | `rate_limited` | too many requests |
| 502 | `provider_unavailable` | Gnani call failed on a route that cannot degrade (voice, explain) |
| 504 | `provider_timeout` | Gnani call timed out on such a route |
| 500 | `internal` | anything else |

In the **project pipeline**, provider errors do not produce these codes: the project completes with a `warnings` entry instead (section 1).

## 4. Voice intents (six groups)

Keyword rules first, LLM fallback second (bible 16.6). Parameters are the same for every language; only the phrases differ.

| Intent | `params` | Example (English) | UI action |
|---|---|---|---|
| `play_stop` | `{ "action": "play" \| "stop" }` | "play", "stop" | client-side transport |
| `tempo_change` | `{ "mode": "faster" \| "slower" \| "set", "amount": number? }` | "make it faster", "set tempo to 100" | `reanalyze` with `bpm` (±10 for faster/slower unless `amount` is given) |
| `change_style` | `{ "style": "<style id>" }` | "switch to keherwa", "make it cinematic" | `arrange` with `style` |
| `change_mood` | `{ "mood": "<mood label>" }` | "make it romantic", "something calmer" | `arrange` with `mood` |
| `explain` | `{}` | "explain this" | `explain` in the current language |
| `save_project` | `{ "label": string? }` | "save this" | `POST …/versions` |

## 5. Provider interfaces (B owns `providers/`; A only calls them)

```python
class Word(TypedDict):  text: str; start: float | None; end: float | None; confidence: float | None
class Transcript(TypedDict):  text: str; words: list[Word]; language: str; raw: dict

class STTProvider(Protocol):
    def transcribe(self, wav_path: str, language: str, mixed_language: bool = False) -> Transcript: ...

class TTSProvider(Protocol):
    def synthesize(self, text: str, language: str, voice: str | None = None) -> tuple[bytes, str]: ...  # (audio bytes, mime type)

class LLMProvider(Protocol):
    def complete_json(self, system: str, user: str, schema: dict) -> dict: ...

class ProviderError(Exception): ...
class ProviderUnavailable(ProviderError): ...
class ProviderTimeout(ProviderError): ...
class ProviderBadResponse(ProviderError): ...
```

`providers/registry.py` exposes `get_stt()`, `get_tts()`, `get_llm()` (live or mock, from config and available keys) and `provider_status() -> {"prisma": "live|mock", ...}`.

Behavior:
- Adapters raise `ProviderError` subclasses and never return fabricated data. Only `mock.py` returns placeholder data, and the registry reports it as `"mock"`.
- A's pipeline catches `ProviderError` in the `lyrics` stage, marks the stage `failed`, and adds a `warnings` entry; the project still completes.
- TTS output format and the exact mixed-language mechanism depend on what Gnani confirms **[confirm]**; the signatures above are fixed, so only B's adapter code changes.

## 6. Time and bar model (so playback matches)

- `start` and `end` are seconds from the start of the cleaned clip.
- `arrangement.meter.beats_per_bar` follows the chosen style (4 for pop, 6 for dadra, 7 for rupak, 8 for keherwa, 16 for teen-taal and so on).
- A chord's `bar`, `start` and `end` are consistent with `analysis.bpm` and the meter.
- `percussion.bar_events[].step` counts from 0 within one bar, in units of `1 / steps_per_beat` beats. The UI loops the bar until the end of the melody.

## 7. Open items to settle on Day 0

1. Create route: async with polling (as written) or synchronous? **[confirm]**
2. Does Prisma return word timestamps and confidence? (changes `LyricWord` nulls)
3. TTS mime type and whether text must be native script or romanised.
4. Final style ids and labels (section 0 list).
5. How to declare mixed-language input to Prisma, if supported.

## 8. Additions to the bible (merge back after Day 0)

New routes: `/api/styles`, `/api/audio/{file_id}`, `/api/projects/{id}/status`, `/api/projects/{id}/versions`. New payload fields: `style_suggestions`, `meter`, `percussion` inline pattern, `warnings`. New rule: editing a sample forks it and returns a new id.

## 9. Example payload (shape only; **not real data**)

For B's dev-only fixtures in `frontend/src/mocks/`. The real sample library must come from real pipeline runs (bible 17.3).

```json
{
  "id": "650000000000000000000001",
  "name": "Example hum",
  "origin": "user",
  "created_at": "2026-11-08T09:00:00Z",
  "updated_at": "2026-11-08T09:00:05Z",
  "version_id": "650000000000000000000002",
  "payload": {
    "input": { "mode": "sing", "language": "hi-IN", "mixed_language": false,
               "audio_file_id": "650000000000000000000003", "duration_s": 8.0 },
    "lyrics": [ { "text": "चाँद", "start": 0.4, "end": 1.2, "note_index": 0, "confidence": 0.62 } ],
    "notes_raw":   [ { "pitch": 60, "start": 0.4, "end": 0.9, "velocity": 80, "confidence": 0.8 } ],
    "notes_clean": [ { "pitch": 60, "start": 0.5, "end": 1.0, "velocity": 80, "confidence": 0.8 } ],
    "analysis": { "bpm": 92, "bpm_source": "auto",
                  "key": { "tonic": "C", "mode": "major", "confidence": 0.7 },
                  "scale_matches": [ { "name": "Bilawal / Shankarabharanam", "score": 0.81 } ],
                  "sa_override": null,
                  "mood": { "label": "romantic", "reason": "major key, moderate tempo" } },
    "arrangement": {
      "style": { "name": "keherwa", "variation": "simple" },
      "style_suggestions": [ { "name": "keherwa", "kind": "tala", "score": 0.8, "reason": "moderate tempo, folk feel" } ],
      "meter": { "beats_per_bar": 8, "grouping": [4, 4] },
      "chords": [ { "bar": 1, "start": 0.0, "end": 5.2, "root": "C", "quality": "maj", "alternatives": [] } ],
      "bass": [ { "pitch": 36, "start": 0.0, "end": 1.3, "velocity": 90, "confidence": null } ],
      "percussion": { "pattern_id": "keherwa-simple", "name": "Keherwa", "steps_per_beat": 2,
                      "bar_events": [ { "voice": "bayan", "step": 0, "velocity": 100 },
                                      { "voice": "dayan", "step": 2, "velocity": 80 } ] },
      "instruments": [ { "name": "Harmonium", "reason": "folk style" } ],
      "intensity_plan": [ { "from_bar": 1, "to_bar": 2, "layers": ["melody", "bass"] } ],
      "commentary": ""
    },
    "tts": null,
    "warnings": []
  }
}
```

## 10. Who must keep what stable

| Item | Owner | Depended on by |
|---|---|---|
| `repositories.get_project(id)` signature | A | B (`explain`) |
| `providers/registry.py` functions and `base.py` types | B | A (pipeline lyrics stage, health) |
| Payload shape (section 1) | A produces, B consumes | both |
| `languages.json` shape | B | A (seed build, validation) |

## 11. Changelog

| Version | Date | Change | Approved by |
|---|---|---|---|
| 0.1 | Day 0 | First draft from the bible | A, B |