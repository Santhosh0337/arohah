"""Melody cleanup (F5): merge, octave-jump fix, optional scale snap, optional quantise.

The aim is to keep the melody that was hummed. Cleanup never deletes a note and never
moves a note onto a different pitch unless the evidence is strong (A1 melody-preservation
decisions, DECISIONS_A.md):

* merge     only same-pitch notes that already TOUCH in the raw data. Never across a gap,
            and never notes that only become equal after snapping or octave correction.
* octave    a note far from both neighbours moves by whole octaves (unchanged behaviour).
* snap      only if the key confidence is at least SNAP_MIN_KEY_CONFIDENCE. Ties between two
            scale pitches are not resolved downward; a note that cannot be decided, or whose
            snapping would make two different neighbouring pitches equal, keeps its pitch.
* quantise  OFF by default. When asked for, it runs only with a trusted tempo AND onsets that
            really cluster on the grid, never deletes or reorders notes, and otherwise leaves
            the timing untouched and says why.

Never mutates its input: the raw notes are kept by the caller for A/B playback.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import NOTE_NAMES, Note
from .pitch import TOUCH_TOLERANCE_S

MAJOR_PCS = [0, 2, 4, 5, 7, 9, 11]
MINOR_PCS = [0, 2, 3, 5, 7, 8, 10]  # natural minor
OCTAVE_JUMP = 9  # semitones

# Initial engineering thresholds, NOT calibrated accuracy figures. On five real hums the key
# confidence was 0.23 to 0.89 (see eval/melody_eval.md); weak keys changed many pitches.
SNAP_MIN_KEY_CONFIDENCE = 0.70

# Grid evidence for explicit quantisation. The onsets' resultant length R (1 = all on one grid
# phase, about 1/sqrt(n) for random timing) must be at least GRID_MIN_RESULTANT and pass a
# Rayleigh test. On five real hums R was 0.08 to 0.27 at the detected tempo; a metronomic test
# part with 15 ms jitter gave 0.72 and with 60 ms jitter 0.22. R = 0.5 means onsets within
# about 23 ms (1 sigma) of a 1/16 grid at 120 BPM.
GRID_MIN_ONSETS = 8
GRID_MIN_RESULTANT = 0.50
GRID_MAX_RAYLEIGH_P = 0.01
# Quantising must leave every note at least this fraction of its original length.
QUANTISE_MIN_KEPT_DURATION = 0.5

# Reasons reported when explicit quantisation is not carried out.
Q_TEMPO_NOT_TRUSTED = "tempo_not_trusted"
Q_TOO_FEW_NOTES = "too_few_notes"
Q_NO_GRID = "no_grid_evidence"
Q_COLLISION = "grid_collision"
Q_SHORTENS = "would_shorten_notes"
Q_BAD_TEMPO = "invalid_tempo"

_Q_MESSAGES = {
    Q_TEMPO_NOT_TRUSTED: "the tempo estimate is not trusted (set the BPM by hand to enable it)",
    Q_TOO_FEW_NOTES: f"fewer than {GRID_MIN_ONSETS} notes, too few to show a rhythmic grid",
    Q_NO_GRID: "the note onsets do not cluster around a rhythmic grid at this tempo",
    Q_COLLISION: "two notes would land on the same grid position",
    Q_SHORTENS: "it would shorten a note by more than half",
    Q_BAD_TEMPO: "the tempo is not a positive number",
}


@dataclass
class CleanupReport:
    """What cleanup did and why it skipped what it skipped."""

    merged: int = 0  # touching same-pitch notes joined (notes removed by merging)
    octave_fixed: int = 0
    snap_requested: bool = False
    snapped: int = 0  # notes whose pitch was moved onto the scale
    snap_kept_pitch: int = 0  # out-of-scale notes left alone (undecidable or transition guard)
    snap_skipped_reason: str | None = None  # "low_key_confidence" | "unknown_key_confidence"
    quantise_requested: bool = False
    quantised: bool = False
    quantise_skipped_reason: str | None = None  # one of the Q_* codes

    def quantise_skipped_text(self) -> str:
        return _Q_MESSAGES.get(self.quantise_skipped_reason or "", "it could not be done safely")


def tonic_to_pc(tonic: str) -> int:
    return NOTE_NAMES.index(tonic)


def scale_pitch_classes(tonic: str, mode: str) -> list[int]:
    """Absolute pitch classes of the major or natural-minor scale on `tonic`."""
    base = MAJOR_PCS if mode == "major" else MINOR_PCS
    t = tonic_to_pc(tonic)
    return sorted((t + s) % 12 for s in base)


def scale_candidates(pitch: int, pcs: list[int]) -> list[int]:
    """The scale pitches nearest to `pitch`: [pitch] if it is in the scale, otherwise the one or
    two scale pitches at the smallest distance (two when it lies exactly between)."""
    allowed = set(pcs)
    if not allowed:
        return [pitch]
    for d in range(0, 12):
        found = [c for c in (pitch - d, pitch + d) if c % 12 in allowed]
        if found:
            return sorted(set(found))
    return [pitch]


def nearest_in_scale(pitch: int, pcs: list[int], prefer: int | None = None) -> int:
    """Nearest MIDI pitch whose pitch class is in `pcs`.

    When the pitch lies exactly between two scale pitches (always the case for an out-of-scale
    pitch in a 7-note scale) there is no nearest one. This no longer picks the lower one: it
    returns `prefer` if that is one of the two, otherwise the pitch itself, unchanged.
    """
    cands = scale_candidates(pitch, pcs)
    if len(cands) == 1:
        return cands[0]
    return prefer if prefer in cands else pitch


def fix_octave_jumps(pitches: list[int], threshold: int = OCTAVE_JUMP) -> list[int]:
    """Shift a note by whole octaves toward its neighbours' median when it is
    more than `threshold` semitones from every neighbour. The first and last
    notes have one neighbour, so the test uses just that one."""
    p = list(pitches)
    for i in range(len(p)):
        neigh = [p[j] for j in (i - 1, i + 1) if 0 <= j < len(p)]
        if neigh and all(abs(p[i] - q) > threshold for q in neigh):
            med = float(np.median(neigh))
            p[i] -= int(round((p[i] - med) / 12.0)) * 12
    return p


def snap_pitches(pitches: list[int], pcs: list[int]) -> tuple[list[int], int, int]:
    """Snap `pitches` to the scale without losing transitions.

    Returns (new pitches, notes moved, out-of-scale notes left alone).

    * A pitch in the scale stays. An out-of-scale pitch moves to the nearest scale pitch.
    * When two scale pitches are equally near, the one that is nearer the note's neighbours is
      used (the note is moved toward the side its neighbours are on). If that does not decide
      it either (neighbours on both sides, or none), the note keeps its pitch.
    * Two neighbouring notes that had different pitches never end up equal: both are put back
      to their pre-snap pitch, repeatedly, until no neighbouring pair has collapsed.
    """
    out = list(pitches)
    for i, p in enumerate(pitches):
        cands = scale_candidates(p, pcs)
        if len(cands) == 1:
            out[i] = cands[0]
            continue
        neighbours = [pitches[j] for j in (i - 1, i + 1) if 0 <= j < len(pitches)]
        costs = [sum(abs(c - q) for q in neighbours) for c in cands]
        if neighbours and costs[0] != costs[1]:
            out[i] = cands[int(np.argmin(costs))]
        # else: undecidable, the pitch stays

    changed = True
    while changed:
        changed = False
        for i in range(len(pitches) - 1):
            if pitches[i] != pitches[i + 1] and out[i] == out[i + 1]:
                out[i], out[i + 1] = pitches[i], pitches[i + 1]
                changed = True

    moved = sum(1 for a, b in zip(pitches, out) if a != b)
    left = sum(1 for a, b in zip(pitches, out) if a % 12 not in set(pcs) and a == b)
    return out, moved, left


def merge_touching(notes: list[Note]) -> list[Note]:
    """Join consecutive notes that have the same pitch and touch (end == next start, to the
    0.1 ms precision of the note times). Call it on RAW notes: a gap of any real size, even a
    few milliseconds, is a re-articulation and keeps the notes apart."""
    merged: list[Note] = []
    for n in notes:
        prev = merged[-1] if merged else None
        if prev is not None and prev["pitch"] == n["pitch"] and abs(n["start"] - prev["end"]) <= TOUCH_TOLERANCE_S:
            d1, d2 = prev["end"] - prev["start"], n["end"] - n["start"]
            if prev["confidence"] is not None and n["confidence"] is not None:
                prev["confidence"] = round((prev["confidence"] * d1 + n["confidence"] * d2) / (d1 + d2), 3)
            prev["velocity"] = max(prev["velocity"], n["velocity"])
            prev["end"] = max(prev["end"], n["end"])
        else:
            merged.append(dict(n))  # type: ignore[arg-type]
    return merged


def grid_evidence(onsets: list[float], step: float) -> dict:
    """How well do the onsets sit on a grid of `step` seconds (phase fitted, not assumed 0)?

    Returns {n, resultant, p_value, phase_s}. `resultant` is the length of the mean of the unit
    vectors exp(2*pi*i*t/step): 1 when every onset is at the same place in the step, near
    1/sqrt(n) for unrelated timing. `p_value` is the Rayleigh test probability for no grid.
    """
    t = np.asarray(onsets, dtype=float)
    n = len(t)
    if n == 0 or not step > 0:
        return {"n": n, "resultant": 0.0, "p_value": 1.0, "phase_s": 0.0}
    mean = np.exp(2j * np.pi * t / step).mean()
    r = float(abs(mean))
    p = float(math.exp(-n * r * r))
    phase = float((np.angle(mean) / (2 * np.pi)) * step) % step
    return {"n": n, "resultant": r, "p_value": p, "phase_s": phase}


def quantise_safely(
    notes: list[Note], bpm: float, steps_per_beat: int, tempo_trusted: bool
) -> tuple[list[Note], str | None]:
    """Move note onsets onto a rhythmic grid, or change nothing and return why not.

    Returns (notes, reason). `reason` is None when the notes were quantised, otherwise one of
    the Q_* codes and the returned notes are an unchanged copy. Notes are never deleted or
    reordered, pitches and note lengths are kept (each note moves as a whole), and an overlap
    that the moves would cause is trimmed off the earlier note's end.
    """
    unchanged = [dict(n) for n in notes]  # type: ignore[misc]
    try:
        step = 60.0 / float(bpm) / steps_per_beat
    except (TypeError, ValueError, ZeroDivisionError):
        return unchanged, Q_BAD_TEMPO  # type: ignore[return-value]
    if not math.isfinite(step) or step <= 0:
        return unchanged, Q_BAD_TEMPO  # type: ignore[return-value]
    if not tempo_trusted:
        return unchanged, Q_TEMPO_NOT_TRUSTED  # type: ignore[return-value]
    if len(notes) < GRID_MIN_ONSETS:
        return unchanged, Q_TOO_FEW_NOTES  # type: ignore[return-value]

    starts = [n["start"] for n in notes]
    ev = grid_evidence(starts, step)
    if ev["resultant"] < GRID_MIN_RESULTANT or ev["p_value"] > GRID_MAX_RAYLEIGH_P:
        return unchanged, Q_NO_GRID  # type: ignore[return-value]

    phase = ev["phase_s"]
    targets = [max(0.0, phase + round((s - phase) / step) * step) for s in starts]
    if any(b <= a + 1e-9 for a, b in zip(targets, targets[1:])):
        return unchanged, Q_COLLISION  # type: ignore[return-value]

    out: list[Note] = []
    for i, n in enumerate(notes):
        length = n["end"] - n["start"]
        end = targets[i] + length
        if i + 1 < len(notes):
            end = min(end, targets[i + 1])
        if end - targets[i] < QUANTISE_MIN_KEPT_DURATION * length:
            return unchanged, Q_SHORTENS  # type: ignore[return-value]
        out.append(dict(n, start=round(targets[i], 4), end=round(end, 4)))  # type: ignore[arg-type]
    return out, None  # type: ignore[return-value]


def clean_notes(
    notes_raw: list[Note],
    bpm: float,
    scale_pcs: list[int] | None,
    *,
    cleanup: bool = True,
    snap_to_scale: bool = True,
    quantize: bool = False,
    key_confidence: float | None = None,
    tempo_trusted: bool = False,
    steps_per_beat: int = 4,
) -> tuple[list[Note], CleanupReport]:
    """Return (cleaned copy of `notes_raw`, report of what was done and skipped).

    cleanup          merge touching same-pitch notes, fix octave jumps
    snap_to_scale    move notes onto `scale_pcs`, only if `key_confidence` >= 0.70
    quantize         OFF by default; see quantise_safely
    key_confidence   confidence of the detected key, 0..1; None means unknown, which does not
                     allow snapping
    tempo_trusted    whether `bpm` can be relied on (a BPM the user set, or one that beat
                     tracking and note timing agree on)
    steps_per_beat   4 = 1/16 grid, 2 = 1/8 grid (only used when quantizing)

    With all three switches off the result is an unchanged copy. Order of work: merge (on the
    raw timing and pitches), octave fix, snap, quantise.
    """
    report = CleanupReport(snap_requested=bool(snap_to_scale), quantise_requested=bool(quantize))
    notes = [dict(n) for n in sorted(notes_raw, key=lambda x: x["start"])]  # type: ignore[misc]
    if not notes:
        return [], report

    if cleanup:
        before = len(notes)
        notes = merge_touching(notes)  # type: ignore[arg-type]
        report.merged = before - len(notes)
        fixed = fix_octave_jumps([n["pitch"] for n in notes])
        report.octave_fixed = sum(1 for n, p in zip(notes, fixed) if n["pitch"] != p)
        for n, p in zip(notes, fixed):
            n["pitch"] = p

    if snap_to_scale and scale_pcs:
        if key_confidence is None:
            report.snap_skipped_reason = "unknown_key_confidence"
        elif key_confidence < SNAP_MIN_KEY_CONFIDENCE:
            report.snap_skipped_reason = "low_key_confidence"
        else:
            new, report.snapped, report.snap_kept_pitch = snap_pitches([n["pitch"] for n in notes], scale_pcs)
            for n, p in zip(notes, new):
                n["pitch"] = p

    if quantize:
        notes, reason = quantise_safely(notes, bpm, steps_per_beat, tempo_trusted)  # type: ignore[arg-type]
        report.quantised = reason is None
        report.quantise_skipped_reason = reason

    return notes, report  # type: ignore[return-value]


def cleanup_notes(
    notes_raw: list[Note],
    bpm: float,
    scale_pcs: list[int] | None,
    *,
    cleanup: bool = True,
    snap_to_scale: bool = True,
    quantize: bool = False,
    key_confidence: float | None = None,
    tempo_trusted: bool = False,
    steps_per_beat: int = 4,
) -> list[Note]:
    """`clean_notes` without the report (the original entry point; same name and arguments,
    plus the new keyword-only ones)."""
    return clean_notes(
        notes_raw,
        bpm,
        scale_pcs,
        cleanup=cleanup,
        snap_to_scale=snap_to_scale,
        quantize=quantize,
        key_confidence=key_confidence,
        tempo_trusted=tempo_trusted,
        steps_per_beat=steps_per_beat,
    )[0]
