"""Pitch extraction and note segmentation (F4).

Two layers so the logic can be tested without librosa:
  * compute_f0()     thin wrapper around librosa.pyin (needs librosa)
  * segment_notes()  pure numpy/scipy: f0 frames -> notes

All thresholds are module constants because the bible says to tune them on
real recordings (see eval/melody_eval.md).
"""
from __future__ import annotations

import logging
import os

import numpy as np
from scipy.ndimage import median_filter

from . import Note, PipelineError, make_warning

log = logging.getLogger(__name__)

HOP = 256
FRAME = 2048
FMIN_HZ = 65.406  # C2
FMAX_HZ = 1046.502  # C6

MEDIAN_FRAMES = 5  # smoothing window on the semitone track
SPLIT_SEMITONES = 0.5  # +-50 cents around the current note starts a new note ...
SPLIT_PERSIST = 3  # ... once this many frames in a row are outside it
MERGE_GAP_S = 0.04  # same-pitch notes closer than this are one note
LOW_CONFIDENCE = 0.5  # mean voicing probability below this adds a warning

# Note times are rounded to 0.1 ms, so two edges closer than this are the same instant
# ("touching"). Cleanup uses the same value for its "already touching in the raw data" test.
TOUCH_TOLERANCE_S = 2.0e-4

# Short notes (A1 melody-preservation decision): there is no minimum note length. A short
# segment is rejected only when it is unreliable, in one of two ways:
#   1. its mean voicing probability is below MIN_NOTE_CONFIDENCE (see below), or
#   2. it is a transition fragment: a segment that is continuous with both neighbours (no
#      unvoiced gap), whose pitch lies between theirs, and whose pitch is still moving
#      (a glide passing through) or too short to show a steady pitch at all.
# Evidence (5 real hums, one speaker, so uncalibrated; audit in DECISIONS_A.md): the old 80 ms
# cut removed 282 of 537 segments. Of the 148 of those that passed the confidence floor, 125
# were transition fragments. Their pitch slope had a median of 0.22 semitones per frame and
# 92% were above 12 semitones per second; the 255 steady notes of 80 ms or more had a median
# of 0.02 and 99% were below it. A segment with a flat pitch is a note however short it is.
DRIFT_SEMITONES_PER_S = 12.0  # |pitch slope| at or above this counts as "still moving"
MIN_FRAMES_FOR_SLOPE = 3  # fewer frames cannot show whether the pitch is steady
# The fragment test is only applied to segments shorter than this. Longer ones are always
# kept, which guarantees that every note the old code kept is still kept.
FRAGMENT_TEST_MAX_S = 0.08
# Notes whose mean voicing probability is below this are treated as unpitched sound and
# dropped. pYIN returned a pitch for pauses and noisy stretches at near-zero probability
# in 4 of the 5 real recordings (e.g. 0.01 notes at C2 in hum_04_pauses).
# Evidence (5 real hums, 255 raw notes, checked against a separate YIN tracker): all 21
# notes under 0.10 lacked independent pitch support; from 0.10 to 0.15, 1 of 6 had it;
# a 0.15 floor would already remove a supported note of 150 ms or more. One speaker and
# one microphone, so re-tune on more recordings.
MIN_NOTE_CONFIDENCE = 0.10


def hz_to_midi(hz: np.ndarray) -> np.ndarray:
    return 69.0 + 12.0 * np.log2(hz / 440.0)


def compute_f0(y: np.ndarray, sr: int, hop: int = HOP):
    """Run pYIN. Returns (times, f0_hz with NaN when unvoiced, voiced_prob)."""
    try:
        import librosa
    except ImportError as e:
        raise PipelineError("internal", "librosa is not installed (pip install -r backend/requirements.txt).") from e
    f0, _voiced_flag, voiced_prob = librosa.pyin(
        y, fmin=FMIN_HZ, fmax=FMAX_HZ, sr=sr, frame_length=FRAME, hop_length=hop
    )
    times = librosa.times_like(f0, sr=sr, hop_length=hop)
    return times, f0, voiced_prob


def frame_rms(y: np.ndarray, n_frames: int, hop: int = HOP, frame_length: int = FRAME) -> np.ndarray:
    """RMS per frame, centred like librosa's (frame i is centred on sample i*hop)."""
    padded = np.pad(y, (frame_length // 2, frame_length // 2))
    out = np.zeros(n_frames, dtype=np.float64)
    for i in range(n_frames):
        seg = padded[i * hop : i * hop + frame_length]
        if len(seg):
            out[i] = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2)))
    return out


def _voiced_runs(voiced: np.ndarray) -> list[tuple[int, int]]:
    runs, i, n = [], 0, len(voiced)
    while i < n:
        if voiced[i]:
            j = i
            while j < n and voiced[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def segment_notes(
    times: np.ndarray,
    f0: np.ndarray,
    voiced_prob: np.ndarray | None = None,
    rms: np.ndarray | None = None,
    hop_s: float | None = None,
) -> list[Note]:
    """Turn an f0 track into notes.

    There is no minimum note length: see "Short notes" above for what is rejected instead.
    """
    times = np.asarray(times, dtype=float)
    f0 = np.asarray(f0, dtype=float)
    if len(f0) == 0:
        return []
    if hop_s is None:
        hop_s = float(np.median(np.diff(times))) if len(times) > 1 else HOP / 22050
    voiced = np.isfinite(f0) & (f0 > 0)
    m = np.full(len(f0), np.nan)
    m[voiced] = hz_to_midi(f0[voiced])
    m_unsmoothed = m.copy()  # the drift test looks at the unfiltered track

    segments: list[tuple[int, int]] = []  # frame ranges [a, b)
    for a, b in _voiced_runs(voiced):
        if b - a >= 3:  # median_filter needs something to chew on; tiny runs stay raw
            m[a:b] = median_filter(m[a:b], size=min(MEDIAN_FRAMES, b - a), mode="nearest")
        start = a
        for i in range(a + 1, b):
            center = float(np.median(m[start:i]))
            look = m[i : min(b, i + SPLIT_PERSIST)]
            if len(look) and np.all(np.abs(look - center) > SPLIT_SEMITONES):
                segments.append((start, i))
                start = i
        segments.append((start, b))

    rms_max = float(np.max(rms)) if rms is not None and len(rms) and np.max(rms) > 0 else None
    notes: list[Note] = []
    spans: list[tuple[int, int]] = []  # frame range of each note, for the drift test
    for a, b in segments:
        pitch = int(round(float(np.median(m[a:b]))))
        conf = float(np.mean(voiced_prob[a:b])) if voiced_prob is not None else None
        if rms is not None and rms_max:
            ratio = float(np.mean(rms[a:b])) / rms_max
            velocity = int(np.clip(round(45 + 70 * ratio), 1, 127))
        else:
            velocity = 80
        notes.append(
            {
                "pitch": pitch,
                "start": round(float(times[a]), 4),
                "end": round(float(times[b - 1]) + hop_s, 4),
                "velocity": velocity,
                "confidence": None if conf is None else round(conf, 3),
            }
        )
        spans.append((a, b))

    # Merge same-pitch neighbours separated by a tiny gap (pYIN dropouts inside one note).
    merged: list[Note] = []
    merged_spans: list[tuple[int, int]] = []
    for n, span in zip(notes, spans):
        if merged and merged[-1]["pitch"] == n["pitch"] and n["start"] - merged[-1]["end"] <= MERGE_GAP_S:
            p = merged[-1]
            d1, d2 = p["end"] - p["start"], n["end"] - n["start"]
            if p["confidence"] is not None and n["confidence"] is not None:
                p["confidence"] = round((p["confidence"] * d1 + n["confidence"] * d2) / (d1 + d2), 3)
            p["velocity"] = max(p["velocity"], n["velocity"])
            p["end"] = n["end"]
            merged_spans[-1] = (merged_spans[-1][0], span[1])
        else:
            merged.append(dict(n))  # type: ignore[arg-type]
            merged_spans.append(span)

    fragments = transition_fragments(merged, [_drift(m_unsmoothed, a, b, hop_s) for a, b in merged_spans])
    return [n for i, n in enumerate(merged) if i not in fragments]


def _drift(track: np.ndarray, a: int, b: int, hop_s: float) -> float | None:
    """Pitch slope in semitones per second over frames [a, b), or None when there are
    fewer than MIN_FRAMES_FOR_SLOPE voiced frames to measure it from."""
    idx = np.arange(a, b)
    ok = np.isfinite(track[a:b])
    if int(ok.sum()) < MIN_FRAMES_FOR_SLOPE:
        return None
    return float(np.polyfit(idx[ok], track[a:b][ok], 1)[0]) / hop_s


def transition_fragments(notes: list[Note], drift: list[float | None]) -> set[int]:
    """Indices of short segments that are a pitch glide passing between two notes.

    A segment is a fragment only if ALL of these hold: it is shorter than FRAGMENT_TEST_MAX_S;
    it has a neighbour on each side and touches both (no unvoiced gap); its pitch lies between
    theirs; and its pitch is moving (|drift| >= DRIFT_SEMITONES_PER_S) or cannot be measured
    (drift is None). Neighbours are the segments before any were removed, so a glide that
    leaves several fragments in a row is removed as a whole. Isolated short notes and short
    notes with a steady pitch are never fragments.
    """
    out: set[int] = set()
    for i in range(1, len(notes) - 1):
        n, before, after = notes[i], notes[i - 1], notes[i + 1]
        if n["end"] - n["start"] >= FRAGMENT_TEST_MAX_S:
            continue
        touching = n["start"] - before["end"] <= TOUCH_TOLERANCE_S and after["start"] - n["end"] <= TOUCH_TOLERANCE_S
        between = min(before["pitch"], after["pitch"]) <= n["pitch"] <= max(before["pitch"], after["pitch"])
        moving = drift[i] is None or abs(drift[i]) >= DRIFT_SEMITONES_PER_S
        if touching and between and moving:
            out.add(i)
    return out


def drop_low_confidence(notes: list[Note], min_confidence: float = MIN_NOTE_CONFIDENCE) -> list[Note]:
    """Remove notes the tracker itself considered almost certainly unvoiced.

    Notes without a confidence value (None) are kept.
    """
    kept = [n for n in notes if n["confidence"] is None or n["confidence"] >= min_confidence]
    if len(kept) < len(notes):
        log.info("Dropped %d note(s) with confidence below %.2f.", len(notes) - len(kept), min_confidence)
    return kept


def extract_notes(y: np.ndarray, sr: int, engine: str | None = None) -> tuple[list[Note], list[dict]]:
    """Audio -> (notes, warnings). pYIN only for now (see DECISIONS_A.md)."""
    warnings: list[dict] = []
    engine = (engine or os.environ.get("PITCH_ENGINE", "pyin")).lower()
    if engine != "pyin":
        warnings.append(
            make_warning("pitch_engine_fallback", f"PITCH_ENGINE={engine} is not implemented; used pyin.", "pitch")
        )
    times, f0, voiced_prob = compute_f0(y, sr)
    hop_s = HOP / sr
    all_notes = segment_notes(times, f0, voiced_prob, frame_rms(y, len(f0)), hop_s)
    # The warning looks at every detected note, before low-confidence ones are dropped,
    # so removing junk never makes an uncertain recording look clean.
    confs = [n["confidence"] for n in all_notes if n["confidence"] is not None]
    notes = drop_low_confidence(all_notes)
    if not notes:
        raise PipelineError(
            "validation_error", "No melody could be found in this recording. Try humming louder and closer to the mic."
        )
    if confs and float(np.mean(confs)) < LOW_CONFIDENCE:
        warnings.append(
            make_warning("low_pitch_confidence", "Pitch tracking was uncertain; the notes may contain errors.", "pitch")
        )
    return notes, warnings
