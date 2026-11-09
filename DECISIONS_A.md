# Decisions (Person A)

Short entries: date, decision, reason. Phase A1 (pipeline foundations).

**2026-11-07, scope.** Built Phase A1 only: `pipeline/{ingest,pitch,cleanup,key_bpm,midi_export,run}.py`, `tests/pipeline/`, `samples/README.md`, `requirements/engine.txt`, plus empty `app/__init__.py`. Phase 0 files (CODEOWNERS, main.py, Dockerfile, ...) are assumed to exist in the real repo and were not touched. If `requirements/engine.txt` already exists, merge the lines.

**2026-11-07, notes are plain dicts** with the contract keys (`pitch,start,end,velocity,confidence`). Reason: they go into the payload and JSON unchanged; `Note` is only a TypedDict for type hints.

**2026-11-07, ingest.** ffmpeg decodes to mono 22.05 kHz 16-bit WAV, capped at max+1 s so a huge file cannot exhaust memory. Length rule: decoded length must be 1 to 60 s (`audio_too_short` / `audio_too_long`, contract 3); in addition at least 0.3 s must remain after trimming (also `audio_too_short`). A silent file is `validation_error`. Trim: frames more than 40 dB below the loudest 20 ms frame, 100 ms padding kept. Peak normalised to -1 dBFS. The 16 kHz Prisma copy is made with `scipy.signal.resample_poly`. Audio lives only in a temp `workdir` that the caller removes after uploading to GridFS. Reason for 16 kHz mono WAV: bible 6.2; still unverified with Gnani (OPEN_QUESTIONS_A 3).

**2026-11-07, pitch.** pYIN only (`librosa.pyin`, C2 to C6, hop 256, frame 2048). `PITCH_ENGINE=basicpitch` is not implemented; it falls back to pYIN and adds warning `pitch_engine_fallback` (Basic Pitch is "only if it installs cleanly", bible 13.5, not yet tried). Segmentation: median filter (5 frames) on the semitone track, a new note after 3 consecutive frames more than 50 cents from the current note's median, same-pitch notes within 40 ms merged, notes under 80 ms dropped. Pitch is the integer median per note. Velocity is 45 to 115 from loudness relative to the loudest note. All thresholds are constants at the top of `pitch.py` for tuning on real hums. "No melody found" is a `validation_error`.

**2026-11-07, key.** Krumhansl-Schmuckler with duration-weighted pitch classes of the **raw** notes (cleanup needs the key, so it cannot use cleaned notes). `confidence` is an uncalibrated heuristic (best correlation, scaled down when the runner-up key is close). It means "how clear-cut", not "probability correct".

**2026-11-07, BPM.** Order: user override (accepted 20 to 300) -> `librosa.beat.beat_track` (needs 4+ beats) -> note-onset estimator -> 100 BPM placeholder with warning `bpm_low_confidence`. Auto results are folded by doubling/halving into 60 to 160. The onset estimator cannot tell a tempo from its half or double, so it picks the one closer to 95 BPM when scores are within 10%. On synthetic onsets with 30 ms jitter it was within 4 BPM for 72 to 130 BPM, and 66 and 150 BPM sometimes come out as 132 and 75. Real hums are not measured yet; the UI should keep BPM editable.

**2026-11-07, cleanup.** Order: octave fix -> snap to scale -> quantise -> merge touching same-pitch notes. `cleanup` switch = octave fix + quantise + merge; `snap_to_scale` switch = snapping only; both off returns an unchanged copy. The first and last note use their single neighbour for the octave test. Snap ties go downward. Grid is 1/16 note (4 steps per beat) starting at t=0 of the trimmed clip; a hum that starts off the beat is rounded to the nearest grid point, not re-aligned. Scale for snapping is the major or natural minor of the detected key; raga/Sa-based scales arrive with `scale.py` in A3.

**2026-11-07, stage order.** `key_bpm` executes before `cleanup` because cleanup needs key and BPM. Progress events come in execution order. See OPEN_QUESTIONS_A 1.

**2026-11-07, partial payload.** `run_pipeline` returns only what A1 produces: `input`, `lyrics`, `notes_raw`, `notes_clean`, `analysis` (`bpm`, `bpm_source`, `key`, `scale_matches: []`, `sa_override: null`) and `warnings`. `mood`, `arrangement` and `tts` are not invented. `input.audio_file_id` is `null`; the API layer (A2) fills it after the GridFS upload. Stages `scale` and `arrange` report `skipped` until A3.

**2026-11-07, lyrics stage.** Calls `app.providers.registry.get_stt()` lazily. If that import fails (B has not pushed yet) the stage is `skipped` with warning `providers_unavailable`; any other exception is `failed` with warning `provider_error`; the project always completes (contract section 1). `speak` and `sing` run the same pipeline. Word handling: NFC-normalise, then align (bible 6.4: closest onset within 150 ms, one word per note first, leftovers to the nearest note, even spread when there are no timestamps). Warnings: `lyrics_empty`, `lyrics_unclear` (text under 3 characters or every word confidence under 0.4), `lyrics_alignment_approximate`.

**2026-11-07, MIDI.** First version writes the melody track only (program 0, tempo from the analysis). Chords, bass and drums come in A3.

**2026-11-07, tests.** `unittest`-style classes so they run with `pytest` and with plain `python -m unittest`. Pure logic (segmentation, key, BPM, cleanup, alignment) is tested on its own. The pyin call is the one thing replaced by a fake in the end-to-end test. Synthetic signals are fixtures, not sample recordings.

## 2026-11-08: Phase A2 MongoDB repositories

- **No multi-document transactions.** They need a replica set; the local
  Docker MongoDB is a standalone server. Writes use a safe order instead:
  insert the `versions` document first (ids are generated client-side), then
  insert/update the `projects` document, and delete the version again if the
  second write fails. Readers go project -> `current_version_id` -> version,
  so a crash between the two writes can only leave an unreferenced version,
  never a project that points at nothing.
- **Validate before writing.** `create_project` and `create_version`
  re-validate the payload with `Payload` and build the `Project` object before
  the first write, so invalid input stores nothing. `origin` is typed as
  `Literal["user", "sample"]`.
- **UTC timestamps.** The Mongo client is created with `tz_aware=True`,
  repositories truncate timestamps to milliseconds (what MongoDB stores), and
  `_project_from_documents` forces UTC. Result: `created_at` returned by
  `create_project` equals what `get_project` returns later, and JSON output
  carries a UTC marker (API_CONTRACT section 0).
- **IDs.** Only 24-character hex strings are accepted. Anything else makes
  `get_project` return `None` (no exception, no database call).
- **`get_project_versions` follows API_CONTRACT 2.11.** Entries are
  `{version_id, label, created_at}` (the first draft returned `id` and
  `project_id`). Payloads are not loaded. Newest first, ties broken by newest
  `_id`. Returns `None` for an invalid or unknown project so the route can
  answer 404; `[]` means the project exists without versions.
- **`list_projects()` added** because API_CONTRACT 2.6 needs it. It reads only
  the few payload fields it needs, in one extra query, and skips (with a log
  warning) projects whose current version is missing.
- **Signatures kept stable:** `get_project(project_id)`,
  `create_version(project_id, payload, label) -> str | None`.
- **Tests:** an in-memory async fake (`tests/api/fake_mongo.py`) covers the
  logic and failure paths; `test_db.py` mocks the PyMongo client;
  `test_repositories_integration.py` runs against a real MongoDB only when
  `MONGODB_TEST_URI` is set.
- **`requirements/engine.txt`:** added `pydantic` (used directly) and
  `pytest-asyncio` (the async tests need it).


## 2026-11-08: Amendment, ambiguous write outcomes (replaces the cleanup rule above)

- **A raised error does not prove a write failed.** A network error can occur
  after MongoDB committed the write but before the reply arrived. The first
  version deleted the new `versions` document on any project-write error,
  which could leave a project pointing at a deleted version.
- **New rule:** after a project insert/update raises, the project is read back
  (by its pre-generated `_id`, projecting only `current_version_id`):
  - points at the new version -> the write committed; the version is kept and
    `create_project` returns the project / `create_version` returns the id
    (a warning is logged);
  - project missing, or (for `create_version`) still pointing at the version
    it had before our write -> not committed; the version is deleted and the
    original error is re-raised;
  - read-back fails, or the project points at some other version (concurrent
    writer) -> unknown; the version is KEPT, "possible orphan" is logged and
    the original error is re-raised.
- **Definite outcomes skip the read-back:** `DuplicateKeyError` on the
  project insert (server rejection) and `matched_count == 0` on the update.
- **Known limit:** the read-back is a point-in-time check; a write still in
  flight inside the server could in theory commit after it. Keeping the
  version in unclear cases is the safe direction (an orphan is invisible and
  harmless; a dangling `current_version_id` is not).
- If the *version* insert itself is ambiguous, at most an unreferenced
  version remains (no project exists yet), so no extra handling was added.


## 2026-11-09: Phase A1 melody preservation (amends the A1 `pitch` and `cleanup` entries above)

Aim: a hummed melody comes out as that melody, not as a cleaned-up different one. The A1 acceptance
checks that need a human (listening, MuseScore) are NOT done; see OPEN_QUESTIONS_A and `eval/melody_eval.md`.

**What the real recordings showed (all reproduced exactly with the old code from the saved raw notes).**
`hum_05_long`: A 94 raw -> 60 clean, B 66, C 94. Snapping changed 34 of 94 pitches, all downward, and all 34
were exact ties: in any 7-note scale every out-of-scale pitch lies exactly between two scale pitches, so
"ties go downward" was the whole snapping behaviour. 13 neighbouring pairs with different raw pitches ended up
equal. Quantising deleted 20 notes on grid collisions. The raw sequence has 4 same-pitch neighbours and none touch
(gaps 70, 128, 383, 418 ms), so the merges in B joined real re-articulations. Key confidence was 0.37 and the
beat tracker said 69.8 BPM against an onset estimate of 121.5. These are observations, not accuracy figures.

**Changes** (approved table implemented as specified; thresholds are initial engineering values, not calibrated):

| Feature | Now |
|---|---|
| Quantisation | OFF by default. `quantize=True` / `--quantize` asks for it. Done only if the tempo is trusted AND the onsets fit a grid (>= 8 notes, resultant length R >= 0.50 and Rayleigh p <= 0.01 on the phase-fitted 1/16 grid). Never deletes or reorders notes; each note moves as a whole (length kept), an overlap is trimmed off the earlier note's end. Otherwise the timing is left as hummed and warning `quantise_skipped` says why (`tempo_not_trusted`, `too_few_notes`, `no_grid_evidence`, `grid_collision`, `would_shorten_notes`, `invalid_tempo`). |
| Scale snapping | Only if key confidence >= 0.70 (unknown confidence also skips). Below it: warning `snap_skipped`, pitches as hummed. Ties are no longer resolved downward: the note moves toward the side its neighbours are on; undecidable notes keep their pitch. Two neighbouring notes with different pre-snap pitches never end up equal (both revert, repeatedly). |
| Merging | Same raw pitch AND touching in the raw data (edges within 0.2 ms, the rounding of note times), decided before snapping, octave fixing and quantising. Never across a gap, never because of snapping or octave correction. |
| Short notes | No minimum length. `pitch.py` no longer drops segments under 80 ms (`MIN_NOTE_S` removed). Rejected instead: (1) mean voicing probability < 0.10 (the existing floor, unchanged), (2) transition fragments, see below. |
| Octave correction | Unchanged. Now covered by tests (see OPEN_QUESTIONS_A on the first/last note). |

**Transition fragments (a judgement beyond the approval wording; please confirm).** Evidence, 5 hums, f0 replay
(approximate, see below): the old cut removed 282 of 537 segments. 148 of those passed the confidence floor and 125 of
them (84%) were continuous with both neighbours and lay between their pitches. Their pitch slope had median 0.22
semitones per frame (92% above 12 semitones per second) against median 0.018 for the 255 steady notes of 80 ms or more
(99% below). Pitch spread did not separate them, so it is not used. Dropping the duration cut without a guard would add
about 125 glide fragments as notes. Rule (`pitch.transition_fragments`): a segment shorter than 80 ms that touches both
neighbours, lies between their pitches, and is still moving (|slope| >= 12 semitones per second) or has too few frames
(< 3) to show a steady pitch, is a glide passing through, not a note. Steady short notes and isolated short notes are kept.
Segments of 80 ms or more are never tested, so every note the old code kept is still kept (tested on all 5 recordings).
Effect on the replay: 233 -> 262 notes, 0 old notes lost, 29 added (23 isolated, 6 inside a run). To keep every
above-floor segment instead, set `FRAGMENT_TEST_MAX_S = 0` in `pitch.py`.

**Interfaces.** `cleanup_notes(...)` keeps its name and arguments; new keyword-only `quantize`, `key_confidence`,
`tempo_trusted`. New `clean_notes(...)` returns `(notes, CleanupReport)`; `run.py` uses it for the warnings.
`nearest_in_scale` no longer breaks ties downward (returns `prefer` if given, otherwise the pitch itself).
`run_pipeline(..., quantize=False)` and CLI `--quantize` are new; `--no-cleanup` and `--no-snap` are unchanged.
`detect_bpm` info gains `trusted` (True for a user BPM or when beat tracking and onset timing agree; never changes the
BPM). New warning codes: `snap_skipped`, `quantise_skipped`. `models.py`, `midi_export.py`, the API contract and all
B files are untouched. Cleanup order is now merge -> octave fix -> snap -> quantise (was octave -> snap -> quantise -> merge).

**Results.** Cleanup on the exact saved raw notes of the five recordings, default settings: every raw note kept
(21/39/41/39/94), no onset or end moved, snapping skipped on `hum_02_clean`, `hum_03_noisy`, `hum_05_long` (key 0.23,
0.56, 0.37). With a confident key forced onto `hum_05_long`, 5 pitches change (4 up, 1 down, 0 collapsed transitions)
against 34 (all down, 13 collapsed). Explicit quantising with a forced-trusted tempo is refused on all five
(`no_grid_evidence`; R 0.08 to 0.27, random onsets 95th percentile 0.18 to 0.36, a metronomic test part 0.72).
Full-pipeline replay (new extraction -> cleanup, approximate): 171 -> 262 clean notes over the five recordings.

**Method limits.** `librosa` and `pretty_midi` were not available where this was built, so the pipeline could not be
run on the `.mp4` files. Cleanup figures are exact (deterministic from the saved raw notes). Extraction figures replay
`segment_notes` on the saved f0 dumps, which come from a slightly different pYIN run than the saved JSONs (about 80% of
notes identical, f0 stored to 0.01 Hz); treat them as an estimate and re-run the real pipeline (commands in
`eval/melody_eval.md`). The key estimate moved from 0.227 to 0.477 on `hum_02_clean` between the two runs, so key confidence
is itself unstable on these hums.

**Tests.** `test_cleanup.py` rewritten (57 tests); `test_pitch.py`, `test_key_bpm.py`, `test_run.py`,
`test_midi.py`, `test_real_samples.py` extended; new `test_melody_preservation_real.py` (18 tests on fixtures of the
supplied real outputs in `tests/pipeline/data/`, properties only, no invented ground truth) and `smf_reader.py`
(stdlib MIDI reader, tick-exact). Nine old tests were replaced because they asserted the replaced behaviour: default
quantising (`test_snap_and_quantize`, `test_everything_lands_on_grid`, `test_no_overlaps_and_sorted`,
`test_tiny_note_gets_one_step`, `test_bpm_override`), downward ties (`test_nearest`), merge after quantising
(`test_touching_same_pitch_merge`, `test_toggles`), and the 80 ms drop (`test_short_note_dropped`).

## 2026-11-09: A1 closure and acceptance decision

**Decision.** Phase A1 (ingest, pitch, cleanup, key/BPM, MIDI export, orchestrator) is accepted as complete by the
project owner on 2026-11-09, with the limitations below and in OPEN_QUESTIONS_A.md. This meets the A1 "Done when" line
in the team plan: a real hum gives plausible notes and key, and the MIDI opens in a player (MuseScore Studio). The
accepted behaviour is the one in the "2026-11-09: Phase A1 melody preservation" entry above. This closure changes no
code, tests, contract or B-owned file. A2 (platform core) is the next phase in the team plan and is not started here.

**Basis.** These results were reported by the owner from the local Windows run. This note was written from those
reports; nothing was re-run or re-measured when writing it.

- All five real recordings were processed successfully.
- 211 pipeline tests and 154 subtests passed.
- All five MIDI exports match their JSON note counts, pitches and timings.
- Individual MuseScore Studio listening assessments were completed for `hum_02_clean` and `hum_05_long` only.
  `hum_05_long`: significantly better than the earlier output and resembles the original, but plays back faster.
  `hum_02_clean`: slightly off, acceptable.
- No individual listening assessment exists for `hum_01_short`, `hum_03_noisy` or `hum_04_pauses`. Those three are
  covered by the processing run and the JSON-to-MIDI match, not by individual listening.

**Acceptance criteria (from the A1 melody-preservation brief).**

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Existing A1 pipeline tests pass | Met | 211 tests and 154 subtests passed (owner's local run) |
| 2 | New regression tests pass | Met | Part of the same run; the count is not split out |
| 3 | Five real recordings can be processed | Met | Owner's local run |
| 4 | Raw melody preserved through cleanup | Met by design and tests | Raw notes kept apart; default cleanup kept every raw note on the saved raw notes of all five |
| 5 | Weak key confidence does not cause aggressive pitch changes | Met by design and tests | Snapping only at key confidence 0.70 or more, else `snap_skipped` |
| 6 | Quantisation off by default | Met by design and tests | `quantize=False`; `--quantize` is opt-in and refuses without grid evidence |
| 7 | Short valid notes retained | Met, with one judgement | The 80 ms cut was removed; transition fragments are still rejected (OPEN_QUESTIONS_A item 3, still open) |
| 8 | MIDI opens in MuseScore Studio | Met for the two listened to; not individually reported for the other three | MuseScore assessments exist for `hum_02_clean` and `hum_05_long` only; all five exports match their JSON |
| 9 | Melody recognisable against the recording | Met for the two individually assessed (`hum_02_clean`, `hum_05_long`); not individually validated for the other three | `hum_05_long` resembles the original; `hum_02_clean` slightly off, acceptable; no individual listening result for `hum_01_short`, `hum_03_noisy`, `hum_04_pauses` |
| 10 | Rhythm not unnecessarily robotic | Not separately reported | The only timing remark is that `hum_05_long` plays back faster |
| 11 | Explicit listening assessments for `hum_02_clean` and `hum_05_long` | Met (these two only; the criterion names only these two) | See `eval/melody_eval.md` |
| 12 | Remaining limitations documented | Met | OPEN_QUESTIONS_A.md and `eval/melody_eval.md` |

**What this acceptance does not claim.** It is not a pitch-accuracy result: there is no ground-truth melody, five
recordings by one speaker on one microphone, and every threshold is an initial engineering value. Only two of the five
recordings (`hum_02_clean`, `hum_05_long`) were individually listening-validated; the other three were not. `hum_05_long` playback
speed and the `hum_02_clean` pitch deviation are known and unresolved (OPEN_QUESTIONS_A). Any later change to A1
behaviour needs its own dated entry here.
