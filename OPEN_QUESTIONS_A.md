# Open questions (Person A)

Things that need a change or an answer outside A's files. Phase A1 stopped here and did not touch them.

## For B and the contract (needs a PR both approve)

1. **Stage order.** Contract 2.5 lists the stages as `ingest, pitch, cleanup, key_bpm, ...`, but cleanup needs the key and BPM, so A runs `key_bpm` first. Either reorder the list in 2.5 to `ingest, pitch, key_bpm, cleanup, ...` (A's preference), or B's progress UI must not assume stages finish in list order.
2. **New warning codes** A emits, for B's UI: `lyrics_alignment_approximate` (show the "approximate alignment" badge when present), `providers_unavailable`, `provider_error`, `pitch_engine_fallback`, `bpm_low_confidence`. Existing ones used as in the contract: `lyrics_empty`, `lyrics_unclear`, `low_pitch_confidence`. Suggest listing them in contract section 1.
3. **Prisma audio format.** A hands `stt.transcribe()` a mono 16 kHz 16-bit WAV path. If Gnani needs a different rate or format, tell A and `ingest.py` changes. (Bible 14.2 question 1.)
4. **Speak mode.** A1 treats `speak` like `sing`: if no pitch can be tracked in a spoken clip the whole project fails with "No melody found". Should speak mode instead complete with empty notes and a warning? Needs a decision from both because the UI and payload rules for empty notes are not in the contract.

## For the human

5. **Real samples.** The A1 "Done when" (plausible notes and key from a real hum, MIDI opens in a DAW) needs 3 to 5 real recordings in `backend/samples/` (see its README) and a machine with `pip install -r backend/requirements.txt`. None exist yet.
6. **Basic Pitch** (bible 13.5): not tried. pYIN only for now.

## 2026-11-08: Phase A2 open questions

1. **Empty config files.** In the review ZIP, `pyproject.toml` and
   `.env.example` are 0 bytes. I wrote code for Ruff's defaults (88 columns)
   and did not edit those shared files. Please confirm the real Ruff and
   pytest settings.
2. **Sample read-only rule.** Repositories do not stop `create_version` on an
   `origin: "sample"` project. The fork-on-edit rule (API_CONTRACT "Editing
   routes") is planned for `api/projects.py`. Should the repository also
   refuse to write versions to samples as a second safety net?
3. **For B (explain):** the contract says explain "also stores `payload.tts`".
   The only write path today is `create_version`, which adds a new version
   per call. Should explain create a version each time, or do we want an
   in-place "update current version payload" function? Needs agreement with B
   before `explain.py` is written.
4. **For B (`tts_cache`, `external_calls`):** no repository helpers were
   added for these. B can use `get_database().tts_cache` and
   `get_database().external_calls` directly, or ask for helpers.
5. **Orphan versions.** A crash between the two writes of `create_project`
   leaves an invisible, unreferenced version. No cleanup job exists. Is that
   acceptable for the hackathon, or should `build_seed.py` sweep them?
6. **`engine.txt` lacks `fastapi` and `uvicorn`**, which `main.py` imports.
   I left them out because A2 repository code does not need them; they must
   be added in the `api/projects.py` step.
7. **Not verified here:** the sandbox had no network, so PyMongo, Pydantic and
   pytest were not installed and the tests were NOT run. In particular please
   confirm that `from gridfs import AsyncGridFSBucket` works with your
   installed PyMongo version.


## 2026-11-08: Amendment to the Phase A2 questions

- **Question 5 (orphan versions) is now more relevant:** unclear write
  outcomes intentionally keep the version and log "possible orphan". There is
  still no sweeper. Do we want one in `build_seed.py` or a small maintenance
  script, or is logging enough?
- **New behaviour to confirm:** when a project write raised but is verified as
  committed, `create_project`/`create_version` return success (with a warning
  log) instead of re-raising. Callers (`api/projects.py`) will therefore see
  success for writes that did land. Say if you prefer to re-raise instead.
- **Test status:** see the hand-off message; the pytest suite has still not
  been run against real PyMongo/Pydantic or a real MongoDB.


## 2026-11-09: A1 melody preservation

### Needs a human (A1 acceptance 3, 8, 9, 10, 11 are NOT done)

1. **Listening and MuseScore.** Nothing here says the melody sounds faithful. Regenerate the five recordings with the
   new code, listen, open the `.mid` files in MuseScore Studio, and fill in the table in `eval/melody_eval.md`
   (explicit rows for `hum_02_clean` and `hum_05_long`). The earlier `out/` files are from the old code.
2. **Real run.** The pipeline could not be run on the `.mp4` files where this was built (no `librosa`, no
   `pretty_midi`). Run `python -m pytest tests/pipeline -v` and the commands in `eval/melody_eval.md` on your machine.
   The 4 tests in `test_real_samples.py` and the 10 `pretty_midi` MIDI tests were skipped here and are untested.

### Needs approval

3. **Short notes: transition fragments are still rejected.** The approval said not to discard short valid notes and to
   keep reliability-based rejection. Removing the 80 ms cut outright would have added about 125 glide fragments over
   the five hums (84% of the short segments that pass the confidence floor). I kept rejecting segments that are
   continuous with both neighbours, between their pitches, and still moving or too short to show a pitch (details and
   evidence in DECISIONS_A). It adds 29 notes on the replay and loses none that were kept before. Is this the intended
   reading? If every above-floor segment should be kept, set `FRAGMENT_TEST_MAX_S = 0` in `pitch.py`. Only a listening
   test can say whether the added notes are real ornaments or noise (`hum_03_noisy` gains 8).
4. **"Neutral nearest-pitch" for snapping.** In a 7-note scale every out-of-scale pitch is exactly between two scale
   pitches, so there is no nearest one. I used: move toward the side the neighbours are on; otherwise keep the pitch;
   never collapse two different neighbouring pitches. This makes snapping rare (5 of 94 notes on `hum_05_long` even if
   the key were confident). Doing better needs the fractional pitch (cents) of each note, which would have to travel
   with the raw note. `Note` has no field for it, so that is a contract and `models.py` change.
5. **New warning codes** `snap_skipped` and `quantise_skipped` (stage `cleanup`). Please list them in contract section 1
   with the other A1 codes (earlier item 2). `snap_skipped` appears on 3 of the 5 real hums (key confidence under 0.70);
   B may want to show it quietly or not at all.

### Not decided here

6. **BPM.** `hum_05_long` is reported as 69.8 BPM (beat tracker) while the note onsets suggest about 122. The MIDI tempo
   header must equal `analysis.bpm`, and note times are absolute, so playback is right, but MuseScore will show the notes
   at a very fine rhythmic resolution. With quantising off the BPM only affects notation and the metronome. Options: let
   the user set it (already possible), prefer the onset estimate when the two disagree, or show both. A1 only added
   `trusted`; the choice itself is unchanged.
7. **Key confidence is unstable.** `hum_02_clean` is 0.227 in the saved run and 0.477 in the replay (one-frame boundary
   differences). The 0.70 snapping threshold and every other threshold below are initial engineering values, not
   calibrated on a labelled set. `SNAP_MIN_KEY_CONFIDENCE`, `GRID_MIN_RESULTANT`, `GRID_MAX_RAYLEIGH_P`,
   `QUANTISE_MIN_KEPT_DURATION` (cleanup.py), `DRIFT_SEMITONES_PER_S`, `FRAGMENT_TEST_MAX_S`, `MIN_FRAMES_FOR_SLOPE`
   (pitch.py) came from five recordings by one speaker.

### Existing behaviour I kept but want you to know about

8. **Octave fix at the ends.** The first and last note have one neighbour, so a leap of 10 or more semitones at the very
   start or end is treated as an octave error and moved by 12 (`[60, 70, 70]` becomes `[72, 70, 70]`). It is the
   documented A1 behaviour and the approval said to keep it; it changed no note on the five real hums (0 octave fixes
   in the replay). Tests now pin it down.
9. **Extraction merge.** `pitch.py` still merges same-pitch segments up to 40 ms apart (`MERGE_GAP_S`): 1 to 3 frames of
   pYIN dropout inside a note. I did not change it and did not test it against real re-articulations; raw same-pitch
   neighbours on `hum_05_long` were 70 ms or more apart, so it did not affect the observed cases.

## 2026-11-09: A1 closure, remaining known limitations

**Status of earlier items.** Resolved by the closure: "Needs a human" items 1 and 2 of the A1 melody-preservation list
(listening and MuseScore check; run on the real files, results in `eval/melody_eval.md`; individual assessments for `hum_02_clean` and `hum_05_long` only) and the first list's item 5
(real samples; five recordings exist). Still open exactly as written above: items 3 to 9 of the melody-preservation
list (fragment rule, neutral snapping and fractional pitch, new warning codes, BPM conflict, unstable key confidence and
uncalibrated thresholds, octave fix at the ends, extraction merge) and items 1, 2, 3, 4 and 6 of the first list (stage
order, warning codes, Prisma format, speak mode, Basic Pitch). The owner approved A1 closure with the behaviour as
implemented; anything that needs a contract or `models.py` change still needs a PR both people approve.

### Known limitations carried out of A1

1. **`hum_05_long` plays back faster than the hum (owner's listening in MuseScore Studio). Cause not established.**
   Facts on record: the beat tracker gave 69.8 BPM while the note onsets suggest about 122; MIDI note times are absolute
   seconds, so the header tempo changes only the notation, not how long the file plays; an earlier audit of the old
   A/B/C exports found the same header and the same end time (about 33.3 s) in all three; the new default keeps the
   hummed timings (no quantising) and keeps short notes (the f0 replay estimated 13 extra short notes on this clip, an
   estimate, not a real-run count). Not checked: the total playback time MuseScore shows against the roughly 35 s
   recording. That one number separates the two explanations. If MuseScore ends near 33 s, the file is not
   time-scaled and "faster" is note density or notation. If it ends much earlier, the MuseScore import is re-timing the
   notes. `--bpm` will not change playback time for the same reason. Options if wanted, none implemented and each needs
   a decision: prefer the onset estimate when the two tempos disagree; report both; or leave the user BPM override as
   the remedy (item 6 above).
2. **`hum_02_clean` is slightly off but acceptable (owner's listening). Cause not diagnosed.** Facts on record: key
   confidence was 0.227 in the saved run and 0.477 in the replay, so it is unstable; snapping is skipped below 0.70, so
   the pitches are the tracker's per-note medians rounded to whole semitones; 20 to 32% of voiced frames in the five
   recordings lie within 15 cents of a semitone boundary, so some per-note labels are uncertain. There is no per-note
   ground truth, so which notes deviate is unknown. A real improvement needs the fractional pitch (cents) to travel
   with each note, which `Note` has no field for (item 4 above: contract and `models.py` change). Not scheduled.
3. **Evidence is thin.** Five recordings, one speaker, one microphone. Individual listening results exist only for
   `hum_02_clean` and `hum_05_long`; `hum_01_short`, `hum_03_noisy` and `hum_04_pauses` have none recorded. The final
   raw and clean note counts of the closing real run were not supplied, so the replay figures in `eval/melody_eval.md`
   stay estimates.
4. **Temp-directory cleanup on failure is not confirmed in the closed A1 code.** During A1 verification a failing stage
   after ingest, with no `workdir` passed, left the temp directory with the processed audio on disk (reproduced). A fix
   with tests was offered in `arohah-a1-validation-rev1.zip`; it is not known whether it was imported. Check with
   `Select-String -Path backend\app\pipeline\run.py -Pattern "own_workdir"`. No match means the leak is still there, and
   A2 (which calls `run_pipeline` from the API) needs it settled or its own cleanup.
5. **For A2, not started:** the real recordings are `.mp4` (AAC). FFmpeg decodes them and the pipeline accepted them, but
   the contract lists "wav, mp3, m4a or webm" for uploads. A2 needs a decision on accepting `.mp4`.
