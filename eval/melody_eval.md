# Melody pipeline evaluation (Phase A1)

Evidence from the five real recordings in `backend/samples/` (run on Windows, Python 3.13.3, librosa 1.0.0,
pretty_midi 0.2.11, ffmpeg) plus an independent cross-check in a sandbox. The cross-check used a separate YIN
pitch tracker on the same audio. It is evidence about tracker agreement, not about musical correctness.

## What was measured

| Recording | Raw | Clean | Key (conf.) | BPM (beat_track) | Onset estimate | Junk notes (<0.10) |
|---|---:|---:|---|---:|---:|---:|
| hum_01_short | 23 | 20 | C major (0.89) | 152.0 | 111.5 | 2 |
| hum_02_clean | 41 | 30 | G major (0.19) | 112.3 | 121.5 | 2 |
| hum_03_noisy | 50 | 38 | G# minor (0.60) | 121.5 | 121.5 | 9 |
| hum_04_pauses | 47 | 42 | E major (0.85) | 117.5 | 118.5 | 8 |
| hum_05_long | 94 | 60 | B minor (0.37) | 69.8 | 121.5 | 0 |

- Pitch agreement (pYIN vs YIN on frames both call voiced): 90 to 95% within half a semitone; octave-apart
  frames at most 0.3%. No octave error is demonstrated.
- False notes: 21 of 255 raw notes had confidence below 0.10 and none had independent pitch support
  (hum_04_pauses has three at C2, the lowest pitch the tracker allows). Fixed by the 0.10 floor.
- Missed notes: 1 to 5% of each clip, always short fragments below the 80 ms minimum. Minor.
- Tuning: no consistent offset from A440 (concentration 0.06 to 0.33); 20 to 32% of voiced frames sit within
  15 cents of a semitone boundary, so some per-note semitone labels are uncertain.
- Cleanup loss: see OPEN_QUESTIONS_A item 2 (quantise grid) and item 3 (snapping).
- The `*.json` and `*.mid` files in your results zip came from the code before the 0.10 floor. Regenerate them
  before listening (commands below).

## Listening procedure (pending when the earlier evaluation was written; since carried out, see "A1 closure" at the end)

```powershell
cd backend
New-Item -ItemType Directory -Force out | Out-Null
foreach ($f in "hum_01_short","hum_02_clean","hum_03_noisy","hum_04_pauses","hum_05_long") {
  python -m app.pipeline.run "samples\$f.mp4" --mode hum --midi "out\$f.mid" --json "out\$f.json" 2> "out\$f.log"
}
```

For each recording, play `samples\<name>.mp4`, then `out\<name>.mid` in a DAW or MIDI player (or MuseScore):

1. Does the MIDI follow the same up/down contour of the hum? (yes / mostly / no)
2. Are there notes where you were silent? (none / a few / many)
3. Are there hummed notes missing? (none / a few / many)
4. Is the rhythm recognisable? Pauses kept? (yes / mostly / no)
5. Do any notes sound an octave off? (none / some)
6. Re-run with `--no-cleanup --no-snap` and compare: does cleanup make it better or worse?
7. Do you agree with the key and the BPM? What did you hum, and at what tempo?

| Recording | Contour | False notes | Missing | Rhythm | Octave | Cleanup better? | Key ok? | BPM ok? |
|---|---|---|---|---|---|---|---|---|
| hum_01_short | | | | | | | | |
| hum_02_clean | | | | | | | | |
| hum_03_noisy | | | | | | | | |
| hum_04_pauses | | | | | | | | |
| hum_05_long | | | | | | | | |

## A1 melody-preservation re-evaluation (2026-11-09)

> Update 2026-11-09 (closure): the listening checks and the real run described below were still pending when this section was written. They were completed afterwards, locally; individual MuseScore assessments exist for `hum_02_clean` and `hum_05_long` only. The final results are in "A1 closure" at the end of this file. The text in this section is left as written.

Status when this section was written: **the listening checks were NOT done (pending).** They were completed afterwards; see "A1 closure" at the end of this file. Figures below are from tests and replays; none of them says the
melody sounds like the hum. See DECISIONS_A (2026-11-09) for what changed and OPEN_QUESTIONS_A for open items. The
cross-references above ("OPEN_QUESTIONS_A item 2 / 3") describe the findings that this change addresses.

### Evidence already in hand (observations, not accuracy measurements)

Cleanup on the exact saved raw notes (deterministic, so exact):

| Recording | Raw | Old A (default) | Old B (no snap) | Old C (none) | New default | Key conf. | Snap now |
|---|---:|---:|---:|---:|---:|---:|---|
| hum_01_short | 21 | 18 | 21 | 21 | 21 | 0.89 | on (1 pitch moved) |
| hum_02_clean | 39 | 28 | 37 | 39 | 39 | 0.23 | skipped |
| hum_03_noisy | 41 | 30 | 35 | 41 | 41 | 0.56 | skipped |
| hum_04_pauses | 39 | 35 | 36 | 39 | 39 | 0.86 | on (1 pitch moved) |
| hum_05_long | 94 | 60 | 66 | 94 | 94 | 0.37 | skipped |

New default: no onset or end moved, no note merged (no touching same-pitch pairs in any of the five), no pitch moved on
the three weak-key recordings. `hum_05_long`, old A: 34 pitches changed (all down), 13 transitions collapsed, 20 notes
deleted by quantising. New, even with a confident key forced onto it: 5 pitches changed (4 up, 1 down), 0 collapsed.

Short notes and the full chain (replay of the new extraction on the saved f0 dumps; approximate, see DECISIONS_A):

| Recording | Old raw | New raw | Short (<80 ms) now kept | New clean |
|---|---:|---:|---:|---:|
| hum_01_short | 21 | 23 | 3 | 23 |
| hum_02_clean | 39 | 40 | 3 | 40 |
| hum_03_noisy | 41 | 52 | 8 | 52 |
| hum_04_pauses | 39 | 40 | 2 | 40 |
| hum_05_long | 94 | 107 | 13 | 107 |

MIDI, executed on the two MIDI files in your A1 results (read at tick level, 220 ticks per beat):

| Recording | JSON clean | MIDI notes | Header tempo vs `analysis.bpm` | Largest time error | Overlaps | Pitch and velocity |
|---|---:|---:|---|---|---:|---|
| hum_02_clean | 28 | 28 | 112.3 = 112.3 | 0.02 tick (0.05 ms) | 0 | equal |
| hum_05_long | 60 | 60 | 69.8 = 69.8 | 0.01 tick (0.04 ms) | 0 | equal |

These are the OLD exports. The same check for the new code is `CleanedMelodyMidiTests` in `test_midi.py` (needs
`pretty_midi`; not run where this was built).

### Re-run with the new code (you must do this)

```powershell
cd backend
python -m pytest tests/pipeline -v
New-Item -ItemType Directory -Force out_a1 | Out-Null
foreach ($f in "hum_01_short","hum_02_clean","hum_03_noisy","hum_04_pauses","hum_05_long") {
  python -m app.pipeline.run "samples\$f.mp4" --mode hum --midi "out_a1\$f.mid" --json "out_a1\$f.json" 2> "out_a1\$f.log"
  python -m app.pipeline.run "samples\$f.mp4" --mode hum --no-cleanup --no-snap --midi "out_a1\${f}_raw.mid" --json "out_a1\${f}_raw.json" 2> $null
}
```

`*_raw.mid` is the raw extraction (what the old "C" was), for comparison. To try quantising on a part that really is
rhythmic, hum to a metronome and add `--bpm <tempo> --quantize`; on free-form hums it will refuse and say why.

Then follow the listening procedure above for every recording, **and write explicit assessments for `hum_02_clean` and
`hum_05_long`**, also opening each `.mid` in MuseScore Studio (it must open without errors and show your notes).
Extra questions this time: (a) does the added short-note material sound like your ornaments, or like noise? (b) with
`snap_skipped` present, are the pitches as you hummed them? (c) is the rhythm still your rhythm?

| Recording | Contour | False notes | Missing | Short notes: real or noise | Rhythm | Octave | MuseScore opens | New vs old better? | Key ok? | BPM ok? |
|---|---|---|---|---|---|---|---|---|---|---|
| hum_01_short | NOT DONE | | | | | | | | | |
| hum_02_clean | NOT DONE | | | | | | | | | |
| hum_03_noisy | NOT DONE | | | | | | | | | |
| hum_04_pauses | NOT DONE | | | | | | | | | |
| hum_05_long | NOT DONE | | | | | | | | | |

"NOT DONE" in this table means pending when it was written. Completed since: individual MuseScore assessments for `hum_02_clean` and `hum_05_long` only (results in "A1 closure" below). No individual listening assessment was recorded for `hum_01_short`, `hum_03_noisy` or `hum_04_pauses`.

Your earlier listening to the OLD `hum_05_long` outputs, for the record: A poor melody resemblance, robotic rhythm,
many missing notes; B better than A; C extremely fast-sounding. The new default is equivalent to C plus the extra short
notes, with no quantising and no weak-key snapping, so the "extremely fast-sounding" impression of C may remain
(the tempo conflict in OPEN_QUESTIONS_A item 6 is the likely cause, not the notes).

### Remaining limitations

- Five recordings, one speaker, one microphone; no ground truth. Every threshold is an initial engineering value.
- The new short-note and fragment figures come from a replay of saved f0 data, not from the real pipeline.
- Whether the retained short notes are musically right is unknown until you listen.
- Snapping is now rare and quantising refuses on free-form hums by design; neither can improve a hum that is
  merely out of tune. BPM disagreement (`hum_05_long`) is unresolved.

## A1 closure: local verification and listening results (2026-11-09)

Source: reported by the project owner from the local Windows run and the MuseScore Studio listening. This section was
written from those reports; nothing was re-run when writing it. It supersedes the "NOT DONE" (pending) status above for the
listening checks and the real run; the figures above are left as they were written.

### Verification

| Check | Result |
|---|---|
| Five real recordings through the pipeline | All five processed successfully |
| Pipeline test suite | 211 tests and 154 subtests passed |
| MIDI export against the JSON, all five | Note counts, pitches and timings match |
| MuseScore Studio listening | Completed; individual assessments for `hum_02_clean` and `hum_05_long` only |

### Listening results (MuseScore Studio)

| Recording | Result as reported |
|---|---|
| hum_01_short | No individual assessment supplied |
| hum_02_clean | Slightly off, acceptable |
| hum_03_noisy | No individual assessment supplied |
| hum_04_pauses | No individual assessment supplied |
| hum_05_long | Significantly better than the earlier output, resembles the original; playback is faster |

For comparison, the owner's listening to the OLD `hum_05_long` outputs (recorded above): A poor resemblance, robotic
rhythm, many missing notes; B better than A; C extremely fast-sounding. The new default is the raw timing plus the extra
short notes, with no quantising and no weak-key snapping, so some speed impression remaining was expected (see the
2026-11-09 note above). The per-column table above (contour, false notes, missing, octave and so on) was not filled in
beyond what is stated here.

### What this does and does not show

- It shows the pipeline runs end to end on five real hums, the exports are faithful to the cleaned notes, and in the
  owner's listening the two assessed melodies are recognisable.
- It is not a pitch-accuracy measurement: there is no ground-truth melody, and the evidence is five recordings by one
  speaker on one microphone, with every threshold an initial engineering value.
- Open and not diagnosed: why `hum_05_long` plays back faster, and why `hum_02_clean` is slightly off. Facts and
  options are in OPEN_QUESTIONS_A.md (2026-11-09 closure, items 1 and 2).
- The final raw and clean note counts of the closing run were not supplied, so the replay-based counts above remain
  estimates.

A1 is accepted as complete (DECISIONS_A.md, 2026-11-09).
