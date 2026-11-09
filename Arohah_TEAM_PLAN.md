# Arohah: Team Plan (two people, one repo, no overlapping files)

**Person A = Engine and Backend core. Person B = Frontend, Gnani and Voice.**
Decide who is who in the first five minutes. Replace `@A-github-username` and `@B-github-username` below with your real GitHub usernames.

Read `Arohah_Project_Bible.md` (repo root) first. This plan only says **who builds what, in which order, in which files**. The bible says what to build.

## The one rule
**Every file has exactly one owner. You only edit files you own.** If you need a change in the other person's files, ask them or open a PR that they must approve. Brand-new files in your own folders are always fine.

---

## 1. Final repo structure (changes from the bible are marked)

Owner tags: **[A]**, **[B]**, **[shared]** (shared files: edit only your own block or section, keep edits small, pull first).

```
arohah/
  README.md                         [A] assembled at the end; B links docs from docs/
  Arohah_Project_Bible.md           [shared] changes only by PR both approve
  AGENTS.md                         [shared] each person edits only their own block
  DECISIONS_A.md                    [A]  CHANGED: DECISIONS.md split in two
  DECISIONS_B.md                    [B]  CHANGED
  OPEN_QUESTIONS_A.md               [A]  CHANGED: OPEN_QUESTIONS.md split in two
  OPEN_QUESTIONS_B.md               [B]  CHANGED
  .env.example                      [shared] A edits the DB/app block, B edits the Gnani block
  .gitignore                        [A]  must include .env
  .gitattributes                    [A]  NEW: "* text=auto"
  docker-compose.yml                [A]
  .github/
    CODEOWNERS                      [A]  NEW (snippet in section 6)
  backend/
    Dockerfile                      [A]
    requirements.txt                [A]  CHANGED: only contains "-r requirements/engine.txt" and "-r requirements/gnani.txt"
    requirements/                         NEW folder
      engine.txt                    [A]
      gnani.txt                     [B]
    app/
      main.py                       [A]  CHANGED: auto-loads every router found in api/, so B never edits it
      db.py                         [A]
      models.py                     [A]
      models_gnani.py               [B]  NEW: schemas for voice, explain, languages
      repositories.py               [A]  get_project() signature must stay stable (B's explain depends on it)
      pipeline/                     [A]  ingest.py pitch.py cleanup.py key_bpm.py scale.py chords.py arrange.py midi_export.py run.py
      providers/                    [B]  base.py gnani_prisma.py gnani_timbre.py gnani_llm.py mock.py registry.py (registry.py is NEW)
      voice/                        [B]  intents.py keywords/*.json
      api/
        projects.py                 [A]
        export.py                   [A]
        health.py                   [A]
        voice.py                    [B]
        explain.py                  [B]
        languages.py                [B]
      data/
        patterns/*.json             [A]
        scales.json                 [A]
        languages.json              [B]
    tests/
      pipeline/                     [A]
      api/                          [A]
      providers/                    [B]
      intents/                      [B]
    seed/                           [A]  audio/ projects/ tts/ BUILD_LOG.md
      audio/s1-*.wav, s6-*.wav      [A]  hum clips
      audio/s2-*.wav ... s5-*.wav   [B]  language clips (B adds only these files)
    samples/                        [A]  test recordings for the melody pipeline
  frontend/                         [B]  everything inside: package.json, lockfile, vite/tailwind config
    public/fonts/                   [B]
    src/
      pages/ components/ audio/ api/
      mocks/                        [B]  NEW: dev-only fixtures so the UI can be built before the API exists
  scripts/
    build_seed.py                   [A]
  eval/
    melody_eval.md                  [A]  CHANGED: eval split in two
    prisma_eval.md                  [B]  languages, Prisma, voice intents, code-switching
  docs/
    API_CONTRACT.md                 [shared] NEW: the contract; changes only by PR both approve
    architecture.png                [A]
    demo_script.md                  [A]  written together on Day 3
    backend.md                      [A]  NEW
    frontend.md                     [B]  NEW
    languages.md                    [B]  NEW
```

---

## 2. Git rules (keep these and conflicts disappear)

- `main` is protected: no direct pushes, 1 approving review (from the other person), squash merge only. Do **not** enable "Require review from Code Owners" (the author owns their own files, so it would block you).
- Branch names: `feat/a/<topic>` and `feat/b/<topic>`. Keep branches under half a day and PRs small.
- Pull and rebase on `main` every morning and before every PR. Never force-push `main`.
- Review each other's PRs within a couple of hours so nobody is blocked.
- Python formatter (ruff or black) and frontend formatter (prettier) configs are committed on Day 0, so there are no whitespace-only diffs.
- Never touch the other person's lockfile or requirements file.
- Share keys privately (never through Git). A shares `MONGODB_URI`, whoever receives the Gnani keys shares them with the other.
- A merges only green PRs. If `main` breaks, whoever merged last fixes it right away.

---

## 3. Phase 0: Setup (together, Day 0)

| Step | Who | What |
|---|---|---|
| 0.1 | A | Create the GitHub repo and push the structure from section 1 (empty folders with `.gitkeep`), plus `.gitignore`, `.gitattributes`, formatter configs, `.env.example`, `docker-compose.yml`, `.github/CODEOWNERS`. |
| 0.2 | A | Invite B. Turn on branch protection as in section 2. |
| 0.3 | A | `main.py` with the auto-router loader, `requirements.txt` with the two includes, MongoDB Atlas free cluster, share `MONGODB_URI`. |
| 0.4 | Both, 30 min | Agree the contract and commit `docs/API_CONTRACT.md`: project payload (bible 6.11), API routes (6.12), `languages.json` shape (16.2), the six voice intents (6.9). A writes, B reviews. |
| 0.5 | Both | Decide the 2 or 3 demo languages (bible 16.2). Ask Gnani the questions in bible 14.2. |

---

## 4. Person A phases (Engine and Backend core)

### Phase A1: Pipeline foundations (Day 1 morning)
**Goal:** a hum becomes clean notes, key, BPM and a MIDI file, from the command line.
- [x] `pipeline/ingest.py`: ffmpeg convert, trim silence, normalize, length checks (F1 backend side)
- [x] `pipeline/pitch.py`: pYIN notes (Basic Pitch only if it installs cleanly) (F4)
- [x] `pipeline/cleanup.py`: snap to scale, octave-jump fix, quantize, keep raw notes (F5)
- [x] `pipeline/key_bpm.py`: key/mode, BPM with override (F6, F7)
- [x] `pipeline/midi_export.py`: first version (F14)
- [x] `pipeline/run.py`: orchestrator with stage progress; the lyrics stage calls B's `providers/registry.py` (stub it until B pushes `base.py` and `mock.py`)
- [x] Test with 3 to 5 recordings in `backend/samples/`

**Files:** `backend/app/pipeline/*`, `backend/samples/`, `backend/tests/pipeline/`
**Done when:** a sample hum gives plausible notes and key, and the MIDI opens in a DAW or player.

### Phase A2: Platform core (Day 1 afternoon)
**Goal:** the frontend can create and fetch projects.
- [ ] `db.py`: Mongo client, GridFS, startup indexes (bible 6.11)
- [ ] `models.py`, `repositories.py` (`get_project()` signature frozen early)
- [ ] `api/projects.py`: `POST /api/projects`, `GET /api/projects`, `GET /api/projects/{id}` (F15)
- [ ] `api/health.py`: adapters live/mock, Mongo status
- [ ] Progress events for pipeline stages

**Files:** `db.py`, `models.py`, `repositories.py`, `api/projects.py`, `api/health.py`, `tests/api/`
**Done when:** B's UI can upload a clip and show the returned analysis.

### Checkpoint 1 (end of Day 1, with B, 30 min)
The real UI talks to the real API: record, notes, key, BPM, MIDI. If this doesn't work, nothing else starts.

### Phase A3: Arrangement engine (Day 2)
**Goal:** the full arrangement comes out of the API.
- [ ] `pipeline/scale.py`: raga/scale match, Sa override (F16)
- [ ] `pipeline/chords.py`: chords per bar (F9); bass (F10)
- [ ] `data/patterns/*.json` and tala/genre library (F11)
- [ ] `pipeline/arrange.py`: styles, variations, instruments (F22), intensity plan (F25), mood (F20)
- [ ] `api/projects.py`: `reanalyze`, `arrange`, `duplicate`, versions
- [ ] `api/export.py`: MIDI and JSON export, streamed from GridFS (F14)
- [ ] Sync with B at midday: the `arrange` payload matches what B's panel reads

**Files:** `pipeline/*`, `data/patterns/`, `data/scales.json`, `api/projects.py`, `api/export.py`, `tests/`
**Done when:** one hum returns chords, bass, percussion and instruments, switchable by style, and exports a multi-track MIDI.

### Phase A4: Hardening and sample library (Day 3 morning)
**Goal:** the sample library exists and the backend is stable.
- [ ] Rate limiting, clear error responses, timeouts
- [ ] Seed loader (idempotent, read-only samples, fork on edit), `build_seed.py`, `seed/BUILD_LOG.md` (F31)
- [ ] Record `s1` and `s6` (hum clips); collect B's `s2` to `s5`
- [ ] Run `build_seed.py` with live Gnani providers once B's adapters work, then commit the generated seed JSON

**Files:** `scripts/build_seed.py`, `backend/seed/*`, rate-limit code
**Done when:** a fresh database with no API keys shows the samples and they play.

### Phase A5: Eval, docs, release (Day 3 afternoon)
- [ ] `eval/melody_eval.md`: 5 hums, expected vs observed key/BPM, octave or timing errors
- [ ] `docs/backend.md`, `docs/architecture.png`, final `README.md` (links B's docs)
- [ ] Bug-fix freeze 3 hours before submission
- [ ] With B: write `docs/demo_script.md`, record the 60 to 90 second demo video

### Phase A6 (optional, last): Render deploy
Only after P0 and P1 pass. Dockerfile deploy, env vars, Atlas network access, `/api/health` check, cold-start note in README (bible section 15).

---

## 5. Person B phases (Frontend, Gnani and Voice)

### Phase B1: Contracts and scaffolding (Day 1 first hours)
**Goal:** A is unblocked and the UI can be built without the API.
- [ ] **First hour:** push `providers/base.py` (STT, TTS and LLM interfaces), `providers/mock.py`, `providers/registry.py` (picks live or mock from config)
- [ ] Vite + React + TypeScript + Tailwind scaffold in `frontend/`
- [ ] `frontend/src/api/` client and TypeScript types from `docs/API_CONTRACT.md`
- [ ] `frontend/src/mocks/`: dev-only fixtures (the real sample library comes later from real pipeline runs)
- [ ] Draft `data/languages.json` from the bible's matrix; send the Gnani questions (bible 14.2); get keys

**Files:** `providers/*`, `frontend/*`, `data/languages.json`
**Done when:** A can code against the interfaces and the UI renders a fixture project.

### Phase B2: Capture and visualize (Day 1 afternoon)
**Goal:** the user can start a project and see their audio and notes.
- [ ] New project flow (F32): Record with countdown, Upload with drag-and-drop, mode selector, language dropdown, "mixed language" checkbox
- [ ] `api/languages.py` serving `languages.json` (F33)
- [ ] Waveform (F3), piano-roll with raw/clean toggle (F13)
- [ ] Self-hosted Noto Sans Indic fonts in `public/fonts/`, `lang` attributes (bible 16.5)
- [ ] Start the Prisma adapter against the real API as soon as keys arrive

**Files:** `frontend/src/*`, `api/languages.py`, `providers/gnani_prisma.py`
**Done when:** a recording shows its waveform and notes from fixtures.

### Checkpoint 1 (end of Day 1, with A, 30 min)
Switch the UI from fixtures to A's real API and confirm the full path works.

### Phase B3: Playback and studio (Day 2)
**Goal:** the Studio is complete for the core loop.
- [ ] Tone.js playback of melody, chords, bass, percussion (F12)
- [ ] A/B playback: raw hum, cleaned melody, full arrangement (F21)
- [ ] Analysis cards (BPM, key, closest scale with Sa dropdown, mood)
- [ ] Arrangement panel: style chips, variation, chord strip, instruments, intensity plan
- [ ] Lyrics panel in native script: editable, confidence underlining, alignment badge (F8, F23, F33)
- [ ] Live Prisma in the lyrics stage (mode-gated, bible 6.3)
- [ ] Projects list, save/load UI (F15), "Sample" chip, Duplicate to edit
- [ ] Spectrogram view (F19), export buttons
- [ ] **By end of Day 2:** record the language clips `s2` to `s5` (original melodies, no copyrighted songs)

**Files:** `frontend/*`, `providers/gnani_prisma.py`
**Done when:** record, hear the cleaned melody and the arrangement, and edit lyrics in native script.

### Phase B4: Voice, Timbre and languages (Day 3 morning)
**Goal:** regional-language voice features meet the acceptance criteria.
- [ ] `voice/keywords/*.json`: native-script and romanised keywords for English and each demo language
- [ ] `voice/intents.py` and `api/voice.py`: keywords first, LLM fallback second, show transcript and parsed intent before acting (F18)
- [ ] `tests/intents/{language}.json`: at least 10 utterances each, 80% accuracy bar on the real provider (bible 16.6)
- [ ] `providers/gnani_timbre.py` and `api/explain.py`: spoken explanation per demo language, cached (F17)
- [ ] `providers/gnani_llm.py`: arrangement commentary and intent fallback (F24)
- [ ] Code-switching tests (at least 5 clips or utterances) (F34)
- [ ] Complete the language matrix; update `languages.json` with confirmed/tested flags

**Files:** `voice/*`, `api/voice.py`, `api/explain.py`, `providers/*`, `tests/providers/`, `tests/intents/`
**Done when:** commands work in English plus every demo language and the explanation speaks in each demo language.

### Phase B5: Eval and polish (Day 3 afternoon)
- [ ] `eval/prisma_eval.md`: spoken, slowly sung, fast sung, code-switched; at least 2 languages; real results, including failures
- [ ] `docs/frontend.md`, `docs/languages.md`
- [ ] UI polish: loading states per stage, readable errors, mock/live badges, "Limitations" link, laptop-width layout
- [ ] Bug-fix freeze 3 hours before submission; then demo video and script with A

### Phase B6 (optional, last): Vercel deploy
Only after P0 and P1 pass. Root `frontend`, build `npm run build`, output `dist`, `VITE_API_BASE_URL` pointing to the Render URL, SPA rewrite (bible section 15).

---

## 6. Sync points (the only times you wait on each other)

| When | What | Who waits |
|---|---|---|
| Day 0 | Contract agreed and committed | both |
| Day 1, hour 1 | B pushes `base.py`, `mock.py`, `registry.py` | A (until then, A uses a stub) |
| End of Day 1 | Checkpoint 1: UI on real API, hum to MIDI works | both |
| Day 2 midday (15 min) | `arrange` payload matches B's panel | both |
| End of Day 2 | B's clips `s2` to `s5` and live Prisma/Timbre adapters ready | A (seed build) |
| Day 3, 3 hours before submission | Bug-fix freeze, no new features | both |

## 7. CODEOWNERS (`.github/CODEOWNERS`)

Put `*` first, because later lines win. This auto-requests the owner's review when someone edits their files.
```
* @A-github-username
/frontend/                       @B-github-username
/backend/app/providers/          @B-github-username
/backend/app/voice/              @B-github-username
/backend/app/models_gnani.py     @B-github-username
/backend/app/api/voice.py        @B-github-username
/backend/app/api/explain.py      @B-github-username
/backend/app/api/languages.py    @B-github-username
/backend/data/languages.json     @B-github-username
/backend/requirements/gnani.txt  @B-github-username
/backend/tests/providers/        @B-github-username
/backend/tests/intents/          @B-github-username
/backend/seed/audio/s2-*         @B-github-username
/backend/seed/audio/s3-*         @B-github-username
/backend/seed/audio/s4-*         @B-github-username
/backend/seed/audio/s5-*         @B-github-username
/eval/prisma_eval.md             @B-github-username
/DECISIONS_B.md                  @B-github-username
/OPEN_QUESTIONS_B.md             @B-github-username
/docs/frontend.md                @B-github-username
/docs/languages.md               @B-github-username
```

## 8. Prompt for each person's AI agents

> You are working as **Person A** (or **Person B**) on Arohah. First read `Arohah_Project_Bible.md`, `Arohah_TEAM_PLAN.md` and `docs/API_CONTRACT.md`. You may create or edit files **only** under the paths owned by your person in the repo structure (section 1 of the team plan). Never edit files you don't own; if you need a change elsewhere, write it in your own `OPEN_QUESTIONS_<A|B>.md` and stop. Write decisions to your own `DECISIONS_<A|B>.md`. Work on a `feat/<a|b>/<topic>` branch, keep PRs small, and do not touch lockfiles or requirements files you don't own. Follow the current phase in the team plan and stop at its "Done when" line.