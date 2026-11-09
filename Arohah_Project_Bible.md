# Arohah: Project Bible (source of truth for all AI agents)

Read this whole file before writing any code. If anything here conflicts with an instruction in a later chat message, ask the human which wins. If something is unspecified, choose the simplest option, note it in `DECISIONS.md`, and move on.

---

## 0. One-paragraph summary

Arohah is a voice-first creative assistant for Indian-language music directors and composers. The director hums, sings, or speaks a musical idea into the browser. The system returns editable lyrics (Gnani Prisma), the melody as notes and MIDI, key, BPM, closest raga or scale, suggested chords, bassline, and a genre/tala-aware percussion pattern, plays the arrangement back in the browser, and speaks a short explanation (Gnani Timbre). Projects can be saved and exported as MIDI and JSON. The whole session can be driven by voice commands in an Indian language, input and lyrics work in regional Indian languages (native script), and a project can be started from a new recording, an upload, or a pre-loaded sample.

**Tagline:** "Hum it. Hear it arranged."

## 1. Context and constraints

- Internship project, submitted to Gnani.ai. It must make visible, meaningful use of Gnani models.
- **Build window: 3 days, one human developer plus AI agents.** Scope discipline matters more than feature count.
- Audience for the demo: Gnani reviewers. They care about Indic voice AI, a working end-to-end flow, honesty about limits, and polish.
- The core loop must work flawlessly. Everything else is optional.

### The core loop (P0, never compromised)
`Record/upload hum → extract notes → clean up → detect key/BPM → suggest arrangement → play back in browser → export MIDI`

If this loop is not working by the **end of Day 1**, stop all other work and fix it.

## 2. Non-negotiable rules for agents

1. **Never invent Gnani API endpoints, parameters, language codes, or response shapes.** Read the official docs or the credentials/README the human provides. If a detail is unknown, stop, list the question in `OPEN_QUESTIONS.md`, and build against a mock adapter (see section 5).
2. Every external service (Prisma, Timbre, LLM) sits behind an adapter interface with a **mock implementation** so the app runs fully offline for dev and demo fallback.
3. No secrets in the repo. Use `.env` and provide `.env.example`. Section 14 is the complete list of keys and credentials; do not add any other external service or key without asking the human.
4. Do not add features outside this document. Stretch items are listed in section 4 and only start after all P0 and P1 acceptance criteria pass.
5. Do not claim accuracy you have not measured. Show confidence and limitations in the UI.
6. Keep dependencies small. Avoid heavy models (no Demucs, no large generative music models, no big sample banks).
7. Every endpoint and pipeline stage has at least one test or a runnable sample script.
8. Keep a running `DECISIONS.md` (short entries: date, decision, reason).
9. Regional-language input (F33) and the New project flow (F32) are core, not optional; see sections 16 and 17. Sample (seed) data must come from real pipeline runs on real recordings: never hand-write analysis values or Gnani responses, and never present mock-adapter output as a real Gnani result.

## 3. Honest limits (must appear in the UI and README)

- Gnani's models are speech models. **Melody extraction, pitch, MIDI and arrangement are done with music-processing libraries and rules, not by Gnani.**
- Prisma is trained on speech, not singing. Sung lyrics may be wrong or empty, so lyrics are always editable and show confidence.
- Raga detection is an **approximate scale-matching**, not full raga grammar. Label it "closest raga/scale match".
- Humming from a laptop mic produces octave errors and unstable note boundaries; the cleanup step reduces but does not eliminate this.
- Language support is whatever Gnani confirms for each model (section 16.2). Mixed-language (code-switched) singing is the hardest case; report results as measured.

## 4. Feature list

### P0: Core (must ship)

| ID | Feature | Notes |
|---|---|---|
| F1 | Record from mic (MediaRecorder) and upload audio (wav/mp3/m4a/webm) | Max 60 s; show a countdown |
| F2 | Input mode selector: **Hum** / **Sing with words** / **Speak lyrics** | Hum skips Prisma |
| F3 | Waveform display with playhead | wavesurfer.js |
| F4 | Pitch extraction and note segmentation | pYIN (librosa) baseline; Basic Pitch if it installs cleanly |
| F5 | Melody cleanup: snap to detected scale, quantize to tempo grid, merge tiny notes | Toggle in UI; keep raw version for A/B |
| F6 | Key and mode detection | Krumhansl-Schmuckler on duration-weighted pitch classes |
| F7 | BPM detection with manual override | librosa beat tracking; user can type BPM or tap tempo |
| F8 | Prisma lyrics (editable), with per-word confidence if the API provides it | Mode-gated, see section 6.3 |
| F9 | Chord suggestion per bar | Section 6.6 |
| F10 | Bassline suggestion | Chord roots with rhythmic patterns |
| F11 | Beat/percussion suggestion by genre **and tala** | Pattern library, section 6.7 |
| F12 | Browser playback of melody + chords + bass + percussion | Tone.js with synthesized sounds |
| F13 | Piano-roll view of detected notes | Simple canvas |
| F14 | Export MIDI (melody, chords, bass, drums on separate tracks) and JSON analysis report | pretty_midi |
| F15 | Save/load projects (with versions) | MongoDB; audio in GridFS |
| F32 | **New project flow**: Record, Upload (drag-and-drop), or Start from a sample, always available | Section 17.5 |
| F33 | **Regional-language input** (P0 part): language selector, lyrics in native script, editable, round-trips correctly | Section 16; acceptance criteria in 16.3 |

### P1: Should ship (after P0 passes)

| ID | Feature | Notes |
|---|---|---|
| F16 | Raga/scale match (top 3 with scores) and user-overridable Sa (tonic) | Section 6.5 |
| F17 | Spoken explanation via **Gnani Timbre** in a chosen Indian language | Template-based text first; LLM polish optional |
| F18 | Voice commands (about 6 fixed intents, plus the Prisma transcript) | Section 6.9 |
| F19 | Spectrogram view | librosa mel spectrogram rendered server-side to PNG, or canvas client-side |
| F20 | Mood tag derived from mode, tempo and note density, with a one-line explanation | Rule-based; LLM sentence optional |
| F21 | A/B playback: raw hum vs cleaned melody vs full arrangement | Big demo moment |
| F22 | Instrument recommendations by genre/mood | Lookup table plus LLM commentary |
| F23 | Lyric-to-note alignment (approximate) | Section 6.4 |
| F24 | LLM commentary: alternative arrangement ideas and "ways to fix repetitive sections" | Aion or Evon if accessible; JSON-validated |
| F25 | Intensity-build suggestion: a simple 4-bar to 8-bar layering plan (add percussion, add bass, add pad) | Rule-based |
| F31 | **Sample library**: a handful of pre-loaded projects built from real recordings and real pipeline output, listed with normal projects | Section 17 |
| F34 | **Regional-language voice commands and code-switching** (P1 part of F33): commands and spoken explanations in the demo languages, mixed-language handling | Sections 16.3 to 16.6 |

### P2: Stretch (only if time remains)

| ID | Feature | Notes |
|---|---|---|
| F26 | FX preview buttons (reverb, delay, filter) on playback | Tone.js effects; this is the "sound design lite" |
| F27 | Transliteration (native script and Roman side by side for lyrics) | LLM or a small library |
| F28 | Shareable project card (image or HTML summary) | |
| F29 | Markdown/PDF analysis report export | |
| F30 | Compare two saved versions (BPM, key, chords, note count diff) | Text diff only, no audio alignment |

### Explicitly cut (do not build)
Instrument identification by timestamp, vocal/instrumental section detection, song-structure detection, full music-comparison module, full sound-design studio, true generative music from text, Warp speech-to-speech, searchable audio library, bookmarks, multi-user accounts.

## 5. Gnani integration spec

| Model | Role in Arohah | Status notes |
|---|---|---|
| **Prisma** (speech-to-text, v2.5 publicly announced) | Lyrics from sung/spoken audio; transcription of voice commands | Verify: supported language codes, word timestamps, audio format/sample rate, sung-audio behavior |
| **Timbre** (text-to-speech, v2.x) | Spoken explanation of the analysis, spoken command confirmations | Gnani's site shows a REST example (`/timbre/v2/synthesize`, bearer token, `language` such as `hi-IN`, a `voice` field). Verify against the real docs before use |
| **Aion / Evon** (language models) | Arrangement commentary, intent fallback, mood sentence | **Confirm which one the issued credentials cover.** Keep behind `LLMProvider` |
| **Warp** (speech-to-speech) | Not used | Out of scope |

### Adapter interfaces (backend)

```python
class STTProvider(Protocol):
    def transcribe(self, wav_path: str, language: str) -> Transcript: ...
# Transcript: {text, words: [{text, start, end, confidence|None}], language, raw}

class TTSProvider(Protocol):
    def synthesize(self, text: str, language: str, voice: str|None) -> bytes: ...  # returns audio bytes

class LLMProvider(Protocol):
    def complete_json(self, system: str, user: str, schema: dict) -> dict: ...
```

Implementations: `GnaniPrisma`, `GnaniTimbre`, `GnaniLLM` (default); `Mock*` for offline; optionally `FallbackLLM` for dev only. **Any non-Gnani fallback used in the final demo must be disclosed in the README.**

Behavior requirements:
- Cache TTS output by hash of (text, language, voice) in the MongoDB `tts_cache` collection (audio bytes in GridFS).
- Timeouts of 20 s with a clear UI error and a mock fallback toggle.
- Log every external call (service, latency, status) to stdout and to the MongoDB `external_calls` collection with a 7-day TTL index (no audio, no secrets).

## 6. Technical design

### 6.1 Recommended stack
- **Backend:** Python 3.11, FastAPI, librosa, numpy, scipy, pretty_midi, pydantic, ffmpeg for conversion. Optional: `basic-pitch` (local only, see section 15 for why).
- **Database:** **MongoDB** (Atlas free M0 cluster, or a local MongoDB container for dev) with the official **PyMongo** driver. Use PyMongo's async API if the installed version supports it, otherwise sync calls from FastAPI's threadpool; check the current PyMongo docs rather than assuming Motor. Audio files (uploads, processed audio, TTS output) live in **GridFS**, not on local disk. Collections and indexes are described in section 6.11.
- **Frontend:** React + Vite + TypeScript, Tailwind, wavesurfer.js, Tone.js, a small canvas piano-roll component.
- **Run (default):** `docker compose up` (MongoDB + backend) plus `npm run dev` for the frontend, or `uvicorn` directly against a local or Atlas MongoDB. The submission must work from a local run.
- **Deployment (optional, done last, see section 15):** frontend on **Vercel**, backend on **Render**, database on MongoDB Atlas. Do not start deployment work until all P0 and P1 acceptance criteria pass.

### 6.2 Audio ingest
1. Accept upload or MediaRecorder blob (webm/opus is common).
2. Convert with ffmpeg to mono WAV, 16 kHz for Prisma and 22.05 kHz for music analysis (verify Prisma's required format).
3. Trim leading and trailing silence; normalize peak to -1 dBFS; reject files over 60 s or under 1 s.
4. Store the original and processed audio in MongoDB GridFS (not on local disk), so storage works unchanged on hosts with ephemeral filesystems such as Render. A local temp directory may be used only while processing.

### 6.3 Mode-gated lyrics (Prisma)
- **Hum:** do not call Prisma. Lyrics panel shows "No lyrics (hum mode)" with an optional "add lyrics" text box.
- **Sing with words / Speak lyrics:** call Prisma with the selected language (language, mixed-language and script rules are in section 16).
- **Result handling:** empty or very short text, or all-low confidence → show "Lyrics unclear, please edit" and keep the box editable. Never fabricate lyrics.
- Display confidence per word if available; underline low-confidence words.

### 6.4 Lyric-to-note alignment (approximate)
- If Prisma returns word timestamps: assign each word to the note whose onset is closest within a tolerance (150 ms). Unassigned words attach to the nearest note.
- If not: distribute words evenly across note onsets in order, and label "approximate alignment" in the UI.
- Output: `lyrics[] = {text, start, end, note_index|null, confidence|null}`.

### 6.5 Melody, key, BPM, raga/scale

**Pitch and notes**
- `librosa.pyin` with fmin about C2 and fmax about C6 (tune on samples). Or Basic Pitch if installed.
- Smooth with a median filter; segment voiced frames into notes; drop notes under about 80 ms; merge adjacent frames within ±50 cents.
- Note record: `{pitch_midi, start, end, velocity, confidence}`.

**Cleanup (toggle)**
- Snap each note to the nearest pitch class in the detected scale.
- Octave-jump fix: if a note jumps more than 9 semitones from both neighbors, shift by an octave toward the local median.
- Quantize starts and ends to a 1/8 or 1/16 grid at the detected BPM.
- Always keep the raw notes for A/B playback.

**Key/mode:** Krumhansl-Schmuckler profiles on duration-weighted pitch classes; report tonic, major/minor and a confidence.

**BPM:** `librosa.beat.beat_track` on the audio; fall back to onset-interval estimation from notes; clamp to 60-160 BPM; user override always wins.

**Raga/scale match (approximate)**
- Sa = detected tonic unless the user sets it.
- Compute the pitch-class set (semitones above Sa) from duration-weighted notes above a 5% weight threshold.
- Score each candidate by weighted overlap minus a penalty for out-of-scale notes.
- Candidate table (Hindustani / Carnatic names, semitone sets):

| Scale | Semitones from Sa |
|---|---|
| Bilawal / Shankarabharanam | 0,2,4,5,7,9,11 |
| Yaman / Kalyani | 0,2,4,6,7,9,11 |
| Khamaj | 0,2,4,5,7,9,10 |
| Kafi / Kharaharapriya | 0,2,3,5,7,9,10 |
| Asavari / Natabhairavi | 0,2,3,5,7,8,10 |
| Bhairavi | 0,1,3,5,7,8,10 |
| Bhairav / Mayamalavagowla | 0,1,4,5,7,8,11 |
| Todi / Hanumatodi | 0,1,3,6,7,8,11 |
| Bhoopali / Mohanam | 0,2,4,7,9 |
| Durga / Shuddha Saveri | 0,2,5,7,9 |
| Malkauns / Hindolam | 0,3,5,8,10 |
| Kirwani / Keeravani | 0,2,3,5,7,8,11 |
| Charukesi | 0,2,4,5,7,8,10 |

Return the top 3 with score and the label "closest match (approximate)". Do not assert time-of-day, rasa, or other raga grammar.

### 6.6 Chord suggestion
- Choose the chord vocabulary from the detected key/mode (diatonic triads; for pentatonic or raga matches use the nearest major or minor key).
- Split the melody into bars using BPM and 4/4 by default (6/8 for Dadra tala, 7 for Rupak, and so on, see section 6.7).
- For each bar, score each diatonic triad by duration-weighted overlap with melody pitch classes (chord tones get full weight, scale tones partial).
- Smooth with a preference for I at the start, V or IV before the end, and I at the end; penalize changing chords more than twice per bar.
- Output: `chords[] = {bar, start, end, root, quality, alternatives[]}`.

### 6.7 Percussion and tala library
Pattern files in `backend/data/patterns/*.json`: step grids with named voices (`kick`, `snare`, `hat`, `dayan`, `bayan`, `shaker`, `clap`). Tabla is approximated with synthesized membrane sounds; do not download large sample banks.

| Style | Beats | Grouping |
|---|---|---|
| Teen taal | 16 | 4+4+4+4 |
| Keherwa | 8 | 4+4 |
| Dadra | 6 | 3+3 |
| Rupak | 7 | 3+2+2 |
| Jhaptal | 10 | 2+3+2+3 |
| Adi talam | 8 | 4+2+2 |
| Pop (4/4) | 4 | 4 |
| Cinematic (4/4 with sparse hits and a build) | 4 | 4 |
| Folk (dholak-style) | 8 | 4+4 |
| Electronic (four-on-the-floor) | 4 | 4 |
| Romantic (soft 6/8 or 4/4) | 4 or 6 | 3+3 or 4 |
| Classical (tala-based, light) | 8 | 4+4 |

Each style has 2 variations (simple, busy). Suggest the top 3 styles using mood, tempo, and detected scale; the user can switch styles instantly.

### 6.8 Bassline, instruments, intensity, mood
- **Bass:** root on beat 1 of each chord; busy variant adds the fifth and passing octave notes in a fixed rhythmic pattern.
- **Instrument recommendations:** lookup by genre and mood, for example Romantic → flute, strings, soft santoor; Folk → dholak, harmonium, sarangi; Cinematic → strings, low brass, taiko-like percussion; Electronic → pad, pluck, sub-bass. Output a ranked list with a one-line reason each.
- **Intensity plan (F25):** a layering schedule over the bars: bar 1-2 melody only, bar 3-4 add bass, bar 5-6 add percussion, bar 7+ add chords or pad and an octave double.
- **Mood:** rule-based from mode (major/minor), tempo band, note density and pitch range; output one of {calm, romantic, joyful, tense, melancholic, energetic} plus a one-line reason. An LLM may rephrase the reason but never override the label without a rule match.

### 6.9 Voice commands
Flow: record command (push-to-talk) → Prisma transcript → intent parse → action → Timbre spoken confirmation (optional).

Fixed intents (keyword rules first, LLM JSON fallback second):
1. `play` / `stop`
2. `tempo_change` (faster/slower, plus a number)
3. `change_style` (a genre or tala by name)
4. `change_mood` (romantic, cinematic, folk, and so on) → re-rank styles and instruments
5. `explain` → generate and speak the analysis summary
6. `save_project`

Rules:
- Support English plus every demo language from the section 16.2 matrix. Keep a keyword table per language with both native-script and romanised variants. The LLM intent fallback must handle every demo language (section 16.6).
- Show the transcript and the parsed intent in the UI before executing; unknown intents say "Sorry, try one of these commands" and list examples.

### 6.10 Spoken explanation (Timbre)
- Build the explanation text from a template filled with analysis values (key, BPM, closest scale, chords used, suggested style, one arrangement tip), 4-6 sentences.
- Optional LLM polishing; the facts must come from analysis JSON, never from the LLM.
- Language dropdown (matching Timbre's supported list); play via an HTML audio element; cache. Confirm per language whether Timbre expects native-script or romanised text (section 16.5).

### 6.11 Data model

MongoDB database (name from `MONGODB_DB`), collections:

| Collection | Document shape | Indexes |
|---|---|---|
| `projects` | `{_id, name, created_at, updated_at, current_version_id, origin: "user"\|"sample", seed_id?, derived_from_seed_id?}` | `updated_at` descending; unique sparse index on `seed_id` |
| `versions` | `{_id, project_id, created_at, label, payload}` (payload is the object below) | `(project_id, created_at desc)` |
| `tts_cache` | `{_id: hash(text, language, voice), audio_file_id, created_at}` | none beyond `_id` |
| `external_calls` | `{service, latency_ms, status, created_at}` | TTL index on `created_at`, 7 days |
| GridFS (`fs.files`, `fs.chunks`) | uploaded audio, processed audio, TTS audio | default |

Keep each `payload` well under MongoDB's 16 MB document limit: never store audio bytes in it, only GridFS file ids. Create indexes at app startup (idempotent). Tests may use `mongomock` or a throwaway local database.

`payload` shape:
```json
{
  "input": {"mode": "hum|sing|speak", "language": "hi-IN", "mixed_language": false, "audio_file_id": "<GridFS ObjectId>", "duration_s": 0},
  "lyrics": [{"text": "", "start": 0, "end": 0, "note_index": null, "confidence": null}],
  "notes_raw": [{"pitch": 60, "start": 0, "end": 0, "velocity": 80, "confidence": 0.0}],
  "notes_clean": [],
  "analysis": {
    "bpm": 0, "bpm_source": "auto|user",
    "key": {"tonic": "C", "mode": "major", "confidence": 0.0},
    "scale_matches": [{"name": "", "score": 0.0}],
    "sa_override": null,
    "mood": {"label": "", "reason": ""}
  },
  "arrangement": {
    "style": {"name": "", "variation": "simple|busy"},
    "chords": [], "bass": [], "percussion": {"pattern_id": ""},
    "instruments": [{"name": "", "reason": ""}],
    "intensity_plan": [],
    "commentary": ""
  },
  "tts": {"language": "", "text": "", "audio_file_id": ""}
}
```

### 6.12 API (all JSON unless noted)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/projects` (multipart: audio, mode, language, name) | Create + run pipeline, return project id and payload |
| GET | `/api/projects` | List |
| GET | `/api/projects/{id}` | Latest version payload |
| POST | `/api/projects/{id}/reanalyze` | Options: bpm, sa, snap, cleanup |
| POST | `/api/projects/{id}/arrange` | Options: style, variation, mood |
| PUT | `/api/projects/{id}/lyrics` | Save edited lyrics |
| POST | `/api/projects/{id}/explain` | Returns text plus TTS audio URL |
| POST | `/api/voice/command` (multipart audio) | Transcript → intent → result |
| GET | `/api/projects/{id}/export/midi` | `.mid` file |
| GET | `/api/projects/{id}/export/json` | Report |
| GET | `/api/health` | Includes which adapters are live vs mock and MongoDB connectivity |
| GET | `/api/languages` | Language matrix from `data/languages.json` (section 16.2) |
| POST | `/api/projects/{id}/duplicate` | Fork any project, including a sample, into a new editable user project |

Pipeline stages return progress events (poll or SSE): `ingest → pitch → cleanup → key/bpm → scale → lyrics → arrange → done`.

`{id}` in paths is the MongoDB ObjectId as a string. Audio and export endpoints stream from GridFS.

### 6.13 Frontend

Single main **Studio** page plus a **Projects** list.

Studio layout:
1. Top bar: project name, mode selector, language dropdown, "mixed language" checkbox, mock/live badge for each Gnani service.
2. Input panel: **New project** options (Record, Upload with drag-and-drop, Start from a sample), waveform with playhead, spectrogram toggle.
3. Analysis cards: BPM (editable), key, closest scale (top 3, Sa dropdown), mood.
4. Melody: piano-roll with raw vs cleaned toggle, "Cleanup" and "Snap to scale" switches.
5. Lyrics panel: editable text in native script (section 16.5) with confidence underlining and the alignment badge.
6. Arrangement panel: style chips (genres and talas), variation toggle, chord strip, instrument list, intensity plan, commentary.
7. Transport: play/stop, A/B selector (Raw hum / Cleaned melody / Full arrangement), tempo, optional FX buttons (P2).
8. Voice: push-to-talk button, shows transcript and parsed intent.
9. Footer actions: Explain (speak), Save, Export MIDI, Export JSON.

UX rules: responsive at laptop width; clear loading state per stage; every error is human-readable; a visible "Limitations" link that opens the section 3 text.

## 7. Repository layout

```
arohah/
  README.md
  AGENTS.md            # copy of key rules from this bible
  DECISIONS.md
  OPEN_QUESTIONS.md
  .env.example
  docker-compose.yml   # local MongoDB + backend (optional)
  backend/
    app/
      main.py
      pipeline/ (ingest.py, pitch.py, cleanup.py, key_bpm.py, scale.py, chords.py, arrange.py, midi_export.py)
      providers/ (base.py, gnani_prisma.py, gnani_timbre.py, gnani_llm.py, mock.py)
      voice/ (intents.py, keywords/*.json)
      data/patterns/*.json, data/scales.json, data/languages.json
      db.py (Mongo client, GridFS, index setup), models.py (Pydantic), repositories.py, api/*.py
    Dockerfile          # optional: used for Render deployment (installs ffmpeg)
    tests/
    seed/               # sample library: audio + real pipeline snapshots (section 17)
    samples/            # 5+ hum/sing/speak recordings with expected notes
  frontend/
    src/ (pages, components, audio/, api/)
    public/fonts/       # self-hosted Noto Sans Indic subsets for the demo languages
  scripts/
    build_seed.py       # builds the sample library from real pipeline runs
  eval/
    prisma_eval.md      # table of measured results (see section 9)
  docs/
    architecture.png
    demo_script.md
```

## 8. Build plan and kill-switches

### Day 1: Core pipeline (no UI polish)
- Repo skeleton, MongoDB connection (local container or Atlas free cluster), ffmpeg ingest, mock providers. Draft `data/languages.json` from Gnani's answers (section 16.2).
- pYIN notes → cleanup → key → BPM → MIDI export, run from a CLI on sample files.
- Minimal frontend: record/upload, waveform, show note list and BPM/key.
- **Checkpoint (end of Day 1):** a sample hum produces correct-sounding cleaned notes and key; MIDI opens in a DAW. If not, no other work starts.

### Day 2: Arrangement, playback, Gnani lyrics
- Chords, bass, tala/genre patterns, Tone.js playback, piano-roll, A/B playback.
- Prisma adapter live, mode gating, lyrics panel, approximate alignment.
- Scale match with Sa override. Save/load projects in MongoDB (audio in GridFS).
- Regional-language input P0 (F33) and the New project flow (F32). Record the sample audio files (section 17.2).
- **Checkpoint (end of Day 2):** full core loop in the UI with at least one live Prisma call.

### Day 3: Voice, Timbre, polish, submission
- Timbre explanation, voice commands, mood, instruments, intensity plan.
- Multilingual voice commands and code-switching tests (F34), build the sample library (F31), complete the language matrix.
- Prisma evaluation table, README, architecture diagram, demo video.
- Bug-fix freeze at least 3 hours before submission. No new features after that.
- **Optional, last:** deployment (section 15), only once P0 and P1 pass and the local demo is stable. Skip it if there is any doubt; the submission must work from a local run regardless.

### Cut order if time runs short (cut from the top)
Deployment (section 15) → P2 features → F25 → F22 → F20 → F19 → F24 → F18 (keep only play/stop) → F23 → F17 (keep text explanation only). **Never cut F32 or F33.**

## 9. Evaluation (required for submission)

Create `eval/prisma_eval.md` with measured results:
- 3 test conditions: spoken lines, slowly sung lines, fast sung lines.
- The demo languages from the section 16.2 matrix (at least 2), 3 clips per cell if possible, plus a code-switched condition.
- Columns: language, condition, reference text, Prisma output, rough word accuracy, notes.

Also record for the melody pipeline: 5 sample hums with the expected key and your observed key/BPM, and any octave or timing errors.

Report these numbers honestly in the README "Known limitations" section.

## 10. Definition of Done

**P0 done when:**
- A new user can record or upload a hum, and within 15 seconds (for a clip under 30 s) see notes, BPM, key and a suggested arrangement, then play and export MIDI.
- Raw and cleaned melody can be played back for comparison.
- Projects save and reload from MongoDB.
- A user can start a new project by recording or uploading, and lyrics in at least two Indian languages display and edit correctly in native script (F32, F33).

**P1 done when:**
- Lyrics via Prisma work in every demo language and are editable.
- Closest scale/raga match and Sa override work on the sample hums.
- Timbre speaks an explanation in each demo language.
- Voice commands work for the fixed intents in English plus every demo language, meeting the accuracy bar in section 16.6.
- The app runs with all providers mocked (offline demo mode) and with live Gnani providers when keys are present.
- The sample library loads on first start without any API keys and its projects appear in the Projects list next to user projects (F31).

**Quality bar:** no unhandled exceptions in the happy path; clear UI errors; tests pass; the README lets a new person run the project in under 10 minutes.

## 11. Demo script (about 90 seconds)

1. Open the Studio. Speak or hum a short phrase (a prepared sample is available as a fallback).
2. Show Prisma lyrics (editable), notes in the piano-roll, BPM, key, and closest raga match.
3. Toggle A/B: raw hum, then cleaned melody, then the full arrangement.
4. Say a voice command in an Indian language, for example "make it romantic" or "switch to Keherwa", and hear the arrangement change.
5. Press Explain and listen to the Timbre summary.
6. Export MIDI; open it in a DAW or player.
7. Close with the architecture diagram and the Known Limitations slide.

## 12. Submission checklist

- [ ] Repo with README (run instructions, architecture diagram, feature list, known limitations)
- [ ] `.env.example` and a working offline/mock mode (providers mocked; MongoDB still required, the docker compose file provides a local one)
- [ ] (Optional) Live URLs for the Vercel frontend and Render backend, with the cold-start note in the README
- [ ] Demo video (60-90 s) plus 3 prepared sample recordings
- [ ] `eval/prisma_eval.md` with real results
- [ ] Completed language matrix (section 16.2) with the Tested column filled
- [ ] Sample library built from real pipeline runs and described in the README
- [ ] A table in the README showing which Gnani model does what (Prisma, Timbre, Aion/Evon) and which parts use non-Gnani music libraries
- [ ] Disclosure of any fallback provider used

## 13. Open questions to resolve first (write answers in `OPEN_QUESTIONS.md`)

1. Prisma: language codes, audio format/sample rate, word timestamps, rate limits, behavior on sung audio.
2. Timbre: available languages and voices, output format, rate limits.
3. Aion vs Evon: which does the issued key cover, and what is the JSON-output reliability?
4. Which two or three Indian languages will the demo use? They become the demo languages in the section 16.2 matrix.
5. Does Basic Pitch install cleanly on the dev machine? If not, use pYIN only.
6. Demo environment: local laptop by default; hosted deployment (section 15) is optional and decided at the end.
7. MongoDB: Atlas free cluster or local container for dev, and which Atlas region?
8. Who records the sample audio? Use original melodies and recordings only (no copyrighted songs).

---

## 14. API keys, credentials and configuration

This section is the complete list of secrets the project needs. **No other external API key is required.** If an agent proposes adding another service (a music API, a cloud speech API, a hosted ML model, analytics), it must ask the human first and record the answer in `DECISIONS.md`.

### 14.1 Secrets (backend only, never in the frontend or the repo)

| Variable | Service | Required? | Used by | Where to get it | Notes |
|---|---|---|---|---|---|
| `GNANI_PRISMA_API_KEY` | Gnani Prisma (speech-to-text) | **Yes** | Lyrics (F8), voice commands (F18) | Gnani developer access or your internship contact | Confirm the auth scheme (the Gnani site's Timbre example uses a bearer token; verify for Prisma) |
| `GNANI_TIMBRE_API_KEY` | Gnani Timbre (text-to-speech) | **Yes** for F17 and spoken confirmations | Spoken explanation | Same | May be the same key as Prisma |
| `GNANI_LLM_API_KEY` | Gnani Aion or Evon (language model) | Recommended (F20, F22, F24, intent fallback) | Arrangement commentary, intent fallback | Same | Confirm which model the key covers; all features degrade to rule-based output if absent |
| `GNANI_API_KEY` | Gnani (shared default) | Optional | All three Gnani adapters | Same | If Gnani issues one key for everything, set only this; per-service variables override it |
| `MONGODB_URI` | MongoDB (Atlas or local) | **Yes** | All persistence and GridFS | Atlas: create a free M0 cluster and a database user, copy the connection string. Local: `mongodb://localhost:27017` | Contains a username and password, so treat it as a secret |
| `FALLBACK_LLM_API_KEY` | A non-Gnani LLM provider | **No**, dev only | `FallbackLLM` adapter | Your own account with any provider | Must be disclosed in the README if used in the final demo. Leave unset for the submission build if Aion/Evon works |

### 14.2 What to ask Gnani for before Day 1
1. Prisma: key, base URL, supported language codes, accepted audio format and sample rate, whether word timestamps and confidence are returned, rate limits, and behavior on sung audio.
2. Timbre: key, base URL, available languages and voices, output audio format, rate limits.
3. Aion vs Evon: which one your credentials cover, the model name string, whether structured/JSON output is reliable, rate limits.
4. Whether one key covers all three services.
5. A usage quota for the internship and demo, so test runs can be budgeted (cache aggressively and use mocks for most development).
6. Prisma: how to declare mixed-language input (Hinglish, Tanglish) if supported, and whether word-level language tags are returned.
7. Timbre: whether text must be in native script or romanised for each language.

### 14.3 Non-Gnani services and accounts

| Service | Needs a key in the app? | Purpose |
|---|---|---|
| MongoDB Atlas | Connection string (`MONGODB_URI`) | Database and GridFS (free M0 tier is enough) |
| Vercel account | No | Optional: hosts the frontend (dashboard or Git integration deploy) |
| Render account | No | Optional: hosts the backend |
| GitHub | No | Source repository (Vercel and Render can deploy from it) |
| Fallback LLM provider | Optional, dev only | See 14.1 |

Account-level tokens for Vercel or Render (for CLI or CI automation) are not needed for dashboard deploys and must never be placed in the app's environment.

**Deliberately not used (do not add):** speech APIs from other vendors, music-metadata or music-generation APIs, sample-pack or sound-library APIs, analytics, authentication providers, payment services. Pitch, key, BPM, MIDI, scale matching, arrangement and playback all run locally in the backend and the browser.

### 14.4 Non-secret configuration

| Variable | Where | Purpose / default |
|---|---|---|
| `MONGODB_DB` | Backend | Database name, for example `arohah` |
| `USE_MOCKS` | Backend | `true` forces all Gnani adapters to mocks (offline demo and tests); default `false` |
| `PITCH_ENGINE` | Backend | `pyin` (default and required on small hosts) or `basicpitch` (local only) |
| `MAX_AUDIO_SECONDS` | Backend | Default `60` |
| `ALLOWED_ORIGINS` | Backend | Comma-separated CORS origins, for example `http://localhost:5173` and the Vercel URL |
| `RATE_LIMIT_PER_MIN` | Backend | Per-IP limit on pipeline and voice endpoints, protects Gnani quota; default `10` |
| `LOG_LEVEL` | Backend | Default `INFO` |
| `SEED_ON_STARTUP` | Backend | `true` loads the sample library on first start (section 17); default `true` |
| `VITE_API_BASE_URL` | Frontend (public, build-time) | Backend URL, for example `http://localhost:8000` or the Render URL. **Never put a secret in a `VITE_` variable: it ships to the browser** |

### 14.5 `.env.example` (backend)

```bash
# --- Gnani (get from Gnani; confirm base URLs in their docs) ---
GNANI_API_KEY=
GNANI_PRISMA_API_KEY=
GNANI_PRISMA_BASE_URL=
GNANI_TIMBRE_API_KEY=
GNANI_TIMBRE_BASE_URL=
GNANI_LLM_API_KEY=
GNANI_LLM_BASE_URL=
GNANI_LLM_MODEL=            # aion or evon, as confirmed with Gnani

# --- Database ---
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=arohah

# --- Optional, dev only (must be disclosed if used in the final demo) ---
FALLBACK_LLM_PROVIDER=
FALLBACK_LLM_API_KEY=
FALLBACK_LLM_MODEL=

# --- App config (not secret) ---
USE_MOCKS=false
PITCH_ENGINE=pyin
MAX_AUDIO_SECONDS=60
ALLOWED_ORIGINS=http://localhost:5173
RATE_LIMIT_PER_MIN=10
LOG_LEVEL=INFO
SEED_ON_STARTUP=true
```

Frontend `.env.example`:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

### 14.6 Key-handling rules
- Keys live only in the backend environment. **All Gnani and LLM calls go through the backend**; the browser never sees a Gnani key.
- `.env` is in `.gitignore` from the first commit. If a key is ever committed, rotate it immediately.
- Use separate Atlas database users and databases for dev and demo; give the user only the permissions it needs.
- The backend must start with missing Gnani keys by falling back to mock adapters and showing the "mock" badge in the UI; it must fail fast with a clear message only if `MONGODB_URI` is missing or unreachable.
- Never log keys, `Authorization` headers, connection strings or audio content.
- On Render and Vercel, set variables in each dashboard; do not commit platform config files that contain secrets.

---

## 15. Deployment (optional, do last)

Deployment is **not** part of the core build and not required for submission. Start it only after P0 and P1 pass and the local demo is stable. Target setup: **frontend on Vercel, backend on Render, database on MongoDB Atlas.** Check each platform's current docs and free-tier limits before relying on them.

### 15.1 Database (Atlas)
- Free M0 cluster, a dedicated database user, and a network access rule. Render's outbound IPs are not fixed on the free tier, so a demo typically needs `0.0.0.0/0` in the Atlas allow-list; use a strong generated password and remove or tighten the rule after the demo.
- Use the Atlas `mongodb+srv://` connection string as `MONGODB_URI` in Render.

### 15.2 Backend on Render
- Deploy as a **Docker** web service from `backend/Dockerfile`, which installs `ffmpeg` and `libsndfile` (the safest way to get the audio tooling onto the host).
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; health check path: `/api/health`.
- Set all variables from 14.1 and 14.4 in the Render dashboard. Set `PITCH_ENGINE=pyin`: heavy dependencies such as TensorFlow (used by Basic Pitch) are likely to exceed a small instance's memory.
- Set `ALLOWED_ORIGINS` to the Vercel production URL (and preview URL if used).
- The filesystem is ephemeral, which is why audio lives in GridFS. Do not rely on local disk persistence.
- Free instances typically spin down when idle and take a while to wake. **Hit `/api/health` a few minutes before any live demo**, and mention the cold start in the README.
- Anyone with the public URL can trigger Gnani calls: keep `RATE_LIMIT_PER_MIN` on, and consider switching the hosted backend to `USE_MOCKS=true` when not demonstrating.

### 15.3 Frontend on Vercel
- Vite static build: build command `npm run build`, output directory `dist`, root directory `frontend`.
- Set `VITE_API_BASE_URL` to the Render service URL (HTTPS). Microphone recording requires HTTPS (or localhost), and Vercel and Render both provide it.
- If the app uses client-side routing, add a rewrite so all paths serve `index.html`.

### 15.4 Deployment acceptance check
- Record in the deployed app, get the full result, play back and export MIDI.
- A deliberately wrong or missing Gnani key shows the mock badge, not a crash.
- CORS works from the Vercel URL and nowhere else.
- The README lists live URLs, the cold-start warning, and the fact that a local run is the primary supported mode.

---

## 16. Regional-language input

### 16.1 What "multilingual" means here
- **In scope:** the director sings, speaks or hums with lyrics in a regional Indian language; lyrics are shown and edited in the native script; voice commands work in the demo languages; the spoken explanation (Timbre) is delivered in a chosen language.
- **Out of scope:** translating the app's own interface. Buttons, labels and error messages stay in English. User content (lyrics, transcripts, spoken output) is multilingual.
- Humming has no language. The language setting only matters in **Sing with words** and **Speak lyrics** modes, and for voice commands and spoken output.

### 16.2 Language support matrix

`backend/data/languages.json` is the single source of truth. The backend serves it at `GET /api/languages` and the frontend builds every language dropdown from it. The table below is the starting point: Prisma and Timbre entries come from Gnani's public pages and are **unverified until Gnani confirms**. Codes follow the pattern Gnani shows for Hindi (`hi-IN`); confirm the real code for every language. The human fills the last three columns after talking to Gnani.

| Language | Code | Prisma STT | Timbre TTS | Command keywords | Script / font | Demo language | Tested |
|---|---|---|---|---|---|---|---|
| English (India) | en-IN (confirm) | ? | ? | to write | Latin / Noto Sans | [ ] | [ ] |
| Hindi | hi-IN (seen on Gnani site) | Listed, verify | Listed, verify | to write | Devanagari / Noto Sans Devanagari | [ ] | [ ] |
| Tamil | ta-IN (confirm) | Listed, verify | Listed, verify | to write | Tamil / Noto Sans Tamil | [ ] | [ ] |
| Telugu | te-IN (confirm) | Listed, verify | Listed, verify | to write | Telugu / Noto Sans Telugu | [ ] | [ ] |
| Kannada | kn-IN (confirm) | Listed, verify | Listed, verify | to write | Kannada / Noto Sans Kannada | [ ] | [ ] |
| Malayalam | ml-IN (confirm) | Listed, verify | Listed, verify | to write | Malayalam / Noto Sans Malayalam | [ ] | [ ] |
| Bengali | bn-IN (confirm) | Listed, verify | Listed, verify | to write | Bengali / Noto Sans Bengali | [ ] | [ ] |
| Marathi | mr-IN (confirm) | Listed, verify | Listed, verify | to write | Devanagari / Noto Sans Devanagari | [ ] | [ ] |
| Gujarati | gu-IN (confirm) | Listed, verify | Listed, verify | to write | Gujarati / Noto Sans Gujarati | [ ] | [ ] |
| Punjabi | pa-IN (confirm) | Listed, verify | Listed, verify | to write | Gurmukhi / Noto Sans Gurmukhi | [ ] | [ ] |
| Odia | or-IN (confirm) | ? | Listed, verify | to write | Odia / Noto Sans Oriya | [ ] | [ ] |
| Hinglish / Tanglish (mixed) | n/a | Claimed, verify how to declare | Listed for Hinglish, Tanglish, verify | to write | Latin and native script | [ ] | [ ] |

Matrix rules:
- Each model's status in `languages.json` is one of `confirmed`, `unconfirmed`, `unsupported`. Only `confirmed` Prisma languages are selectable for lyrics. `unconfirmed` entries appear disabled with the label "not verified".
- A language can be a **demo language** only if Prisma is `confirmed`, Timbre is `confirmed` (or the language is explicitly marked "text explanation only"), command keywords are written, and the intent tests in 16.6 pass.
- Choose **2 or 3 demo languages**. Every acceptance criterion below applies to each of them.

`languages.json` entry shape:
```json
{
  "code": "hi-IN", "name": "Hindi", "native_name": "हिन्दी",
  "script": "Deva", "font_family": "Noto Sans Devanagari",
  "prisma": "unconfirmed", "timbre": "unconfirmed",
  "command_keywords": false, "demo": false, "tested": false
}
```

### 16.3 Feature F33 and F34 with acceptance criteria

**F33, P0 part: regional-language input**
1. The language dropdown is built from `/api/languages` and lists only languages whose Prisma status is `confirmed` (others disabled with a "not verified" label).
2. The selected language is sent to Prisma, stored in the project (`input.language`) and restored when the project is reopened.
3. Sung or spoken lyrics in each demo language come back from a **live** Prisma call and render in native script with no missing-glyph boxes in current desktop Chrome.
4. Lyrics are editable; typing or pasting native script works; saving and reloading returns byte-identical text after Unicode NFC normalization (covered by an automated test).
5. Empty, very short or all-low-confidence output shows "Lyrics unclear, please edit" in every demo language; nothing is ever fabricated.
6. The language setting does not affect Hum mode (Prisma is not called).

**F34, P1 part: regional-language voice commands, spoken output and code-switching**
1. Voice commands work in English plus every demo language for the six fixed intents (section 6.9), meeting the accuracy bar in 16.6.
2. Timbre speaks the explanation in each demo language; the text is generated in the script or form Timbre expects (confirmed with Gnani).
3. At least 5 code-switched utterances or clips are tested (Hinglish or Tanglish style, per the demo languages); results go in `eval/prisma_eval.md`, including failures.
4. The language matrix is complete: every demo-language row has the Tested box ticked, with the date and the evidence file noted in `DECISIONS.md`.

### 16.4 Code-switching note
Music directors often mix English with a regional language (Hinglish, Tanglish and similar), and lyrics frequently mix scripts. Gnani describes its speech models as handling mixed-language speech, but confirm how to request it.
- Treat the language dropdown as the **primary language**. If Prisma has a way to declare mixed input, use it when the "mixed language" checkbox is ticked and record the setting in `input.mixed_language`; if not, send the primary language and note the limitation.
- Never force-transliterate Prisma's output. Show what Prisma returns, which may contain native script and Latin script together.
- Voice-command keyword tables must contain **both native-script and romanised forms**, and matching must tolerate mixed-script transcripts.
- Report code-switching results honestly. Do not claim support beyond what the tests show.

### 16.5 Unicode and native-script display rules
1. UTF-8 everywhere: API responses, MongoDB documents, files, logs. Never escape or strip non-ASCII text.
2. Normalize all text to **Unicode NFC** on input and before storing or comparing. Do not strip combining marks. Do not remove ZWJ or ZWNJ from displayed text (they affect shaping in some scripts); strip them only inside the keyword-matching normalization copy.
3. Fonts: self-host **Noto Sans** subsets for each demo language's script (listed in 16.2) under `frontend/public/fonts/`, so rendering works offline and on the hosted demo. Use font stacks with fallbacks, for example `"Noto Sans Devanagari", "Noto Sans", system-ui, sans-serif`.
4. Set the `lang` attribute (for example `lang="hi"`) on lyrics, transcripts and any element holding a language's text, so the browser picks correct glyph shapes and line breaking.
5. Use generous line height (about 1.6 or more) and avoid fixed-height containers for lyrics and transcript text, because Indic scripts have tall stacked marks.
6. Never truncate, reverse or split strings by code point. Use `Intl.Segmenter` (grapheme clusters) in the browser, and a grapheme-aware approach in Python, for ellipsis and cursor logic.
7. Lyric input fields must accept paste and IME input; do not apply ASCII-only validation.
8. Exports: the JSON report is the authoritative lyrics export (UTF-8). If lyrics are written into MIDI lyric meta events, write UTF-8 and note in the README that some DAWs display non-Latin lyrics incorrectly.
9. Timbre input: use whichever form (native script or romanised) Gnani confirms per language (question 7 in section 14.2); do not assume.
10. Test fixtures for every demo language include a string with conjuncts and combining vowel signs (for example, a word with a conjunct consonant plus a vowel sign) to catch rendering and normalization bugs.

### 16.6 Intent fallback rule for the demo languages
Voice commands are resolved in this order: **keyword rules first, LLM fallback second, "unknown" last.**
1. **Required:** the LLM intent fallback must handle every demo language and romanised or mixed-script variants. The prompt states the six intents and their parameters, requires JSON-only output validated against a schema, uses a low temperature, and receives the transcript exactly as Prisma returned it.
2. **Test set:** `backend/tests/intents/{language}.json` for English and each demo language, at least **10 utterances** each, covering all six intents, including romanised and mixed-language phrasings and common variations ("make it faster", "a bit slower", a style by name).
3. **Accuracy bar:** at least **80%** of test utterances map to the correct intent and parameters per demo language, measured with the real fallback provider (not mocks). Record the numbers in `eval/prisma_eval.md`. If a language falls below the bar, it is not a demo language until it passes.
4. **Safety:** the UI shows the transcript and the parsed intent before executing (already required in 6.9). Low-confidence or ambiguous parses ask for confirmation; unknown intents list example commands.
5. If the LLM provider is unreachable, the keyword rules still handle the common phrasings in each demo language, and the UI says so.

---

## 17. Sample library and new projects

### 17.1 Principles
- The app should feel populated on first launch: a small **sample library** appears in the Projects list alongside the user's own projects. There is no demo mode, no demo toggle and no banner.
- The user can always start something new: **recording, uploading, or starting from a sample**. Samples never replace or block the new-project flow.
- Sample data is **real**: real recordings run through the real pipeline. Nothing is hand-written or invented.

### 17.2 Sample set (4 to 6 projects)

| Seed id | Mode | Language | Style / tala | What it exercises |
|---|---|---|---|---|
| `s1-folk-hum` | Hum | none | Keherwa, folk | Hum mode, no-Prisma path, tala patterns |
| `s2-romantic-sing` | Sing | demo language 1 | Romantic | Prisma lyrics in native script, chords, A/B playback |
| `s3-classical-sing` | Sing | demo language 2 | Teen taal or Adi talam | Scale/raga match, second language |
| `s4-pop-speak` | Speak | demo language 1 or 2 | Pop | Speak-lyrics mode, alignment |
| `s5-mixed-sing` | Sing, mixed language | Hinglish or Tanglish style | Cinematic or electronic | Code-switching path (F34) |
| `s6-cinematic-hum` | Hum | none | Cinematic, minor key | Chords, intensity plan |

Recordings must be original (made by the human or the team): no copyrighted songs. Keep each clip to 20 seconds or less, mono, small, so the repo stays light.

### 17.3 How the sample library is built
`scripts/build_seed.py` (run by a human with live Gnani keys):
1. Takes each file in `backend/seed/audio/` and runs the **real pipeline** with the live providers.
2. Writes the resulting version payload to `backend/seed/projects/{seed_id}.json` and pre-generates the Timbre explanation audio into `backend/seed/tts/` (so opening a sample and pressing Explain does not spend quota).
3. May include human-corrected lyrics only if flagged `edited_by_human: true` in the payload.
4. Fails loudly instead of producing placeholder output when a live call fails. It never fills gaps with invented data or mock results.

The generated seed JSON files are committed, so the app works with no keys.

### 17.4 Loading and behavior
- On startup, if `SEED_ON_STARTUP=true`, an idempotent loader inserts any missing sample (matched by `seed_id`) into `projects` and `versions` with `origin: "sample"`, and copies its audio files into GridFS.
- In the UI, samples are ordinary project cards in the Projects list and open in the normal Studio with all the usual features (playback, A/B, re-arrange, export). They carry a small, quiet "Sample" label in the card metadata; there is no banner, no mode switch and no special demo screen.
- **Samples are read-only.** Any edit, re-analysis or re-arrangement automatically forks the project into a new user project (`origin: "user"`, `derived_from_seed_id` set) through `POST /api/projects/{id}/duplicate`, so originals stay clean.
- The README states plainly that the sample projects are pre-recorded clips processed with the real pipeline.
- Mock-adapter output is a different thing from sample data and keeps its own "mock" badge. A new upload processed in mock mode must never be shown as a live Gnani result.

### 17.5 New project flow (F32)
- A **New project** button is always visible in the Projects list and the Studio.
- Options: **Record** (microphone, with countdown and a 60 second limit), **Upload** (click or drag-and-drop; wav, mp3, m4a, webm; 60 second and size limits with clear errors), **Start from a sample** (opens a fork of a sample).
- The flow asks for: mode (Hum, Sing with words, Speak lyrics), language (disabled for Hum), and the optional "mixed language" checkbox.
- Processing shows per-stage progress (section 6.12) and lands in the Studio with the new project.

### 17.6 Acceptance criteria
1. A fresh install with an empty database and no API keys shows the sample projects in the Projects list after first start.
2. Opening any sample shows complete results (notes, key, BPM, scale match, arrangement, lyrics where applicable) and plays back.
3. Editing a sample creates a new user project; the original sample is unchanged after a restart.
4. A user can record or upload a new clip from the New project flow and get a full result (live providers if keys exist, mock badge otherwise).
5. Restarting the backend does not create duplicate samples.
6. Every sample's stored output traces back to a real pipeline run (the build script log is kept in `backend/seed/BUILD_LOG.md`).