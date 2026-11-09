"""Key/mode detection (F6) and BPM detection with override (F7)."""
from __future__ import annotations

import math

import numpy as np

from . import NOTE_NAMES, Note, PipelineError, make_warning

# Krumhansl-Kessler key profiles (the Krumhansl-Schmuckler algorithm's input).
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

BPM_MIN, BPM_MAX = 60.0, 160.0
BPM_PREFERRED = 95.0  # tie-break centre for tempo octave ambiguity
BPM_DEFAULT = 100.0  # used only when nothing can be measured, and always with a warning
BPM_OVERRIDE_RANGE = (20.0, 300.0)
# Warn when the key confidence is below this. Uncalibrated: on 5 real hums the scores
# were 0.19, 0.37, 0.60, 0.85, 0.89, and the two low ones were near-ties between keys.
KEY_LOW_CONFIDENCE = 0.5
# Warn when beat tracking and the note-onset estimate differ by more than this fraction.
# On 5 real hums they differed by 0-8% for three recordings and by 36% and 74% for two.
BPM_AGREEMENT_TOLERANCE = 0.15


def pitch_class_histogram(notes: list[Note]) -> np.ndarray:
    """Duration-weighted pitch-class histogram (length 12)."""
    h = np.zeros(12)
    for n in notes:
        h[int(n["pitch"]) % 12] += max(0.0, float(n["end"]) - float(n["start"]))
    return h


def detect_key(notes: list[Note]) -> dict:
    """Krumhansl-Schmuckler. Returns {tonic, mode, confidence}.

    `confidence` is an uncalibrated heuristic: the best correlation, scaled
    down when the runner-up key is close. It says "how clear-cut", not
    "probability of being right". Relative major/minor pairs are genuinely
    hard to separate from a short hum.
    """
    h = pitch_class_histogram(notes)
    if h.sum() <= 0:
        raise PipelineError("validation_error", "No notes to detect a key from.")
    scores: list[tuple[float, int, str]] = []
    for tonic in range(12):
        for mode, prof in (("major", KS_MAJOR), ("minor", KS_MINOR)):
            r = float(np.corrcoef(h, np.roll(prof, tonic))[0, 1])
            scores.append((0.0 if math.isnan(r) else r, tonic, mode))
    scores.sort(key=lambda s: s[0], reverse=True)
    (r1, tonic, mode), (r2, _, _) = scores[0], scores[1]
    margin = min(1.0, max(0.0, (r1 - r2) / 0.1))
    conf = max(0.0, min(1.0, max(r1, 0.0) * (0.5 + 0.5 * margin)))
    return {"tonic": NOTE_NAMES[tonic], "mode": mode, "confidence": round(conf, 3)}


def key_warnings(key: dict) -> list[dict]:
    """A warning when the key estimate is weak. Does not change the key."""
    conf = key.get("confidence")
    if conf is not None and conf < KEY_LOW_CONFIDENCE:
        return [
            make_warning(
                "low_key_confidence",
                f"The key ({key['tonic']} {key['mode']}) is a weak guess (confidence {conf:.2f}); "
                "other keys fit almost as well. Check it by ear.",
                "key_bpm",
            )
        ]
    return []


def fold_bpm(bpm: float, lo: float = BPM_MIN, hi: float = BPM_MAX) -> float:
    """Halve or double into [lo, hi], then clamp."""
    if not bpm or bpm <= 0 or not math.isfinite(bpm):
        raise ValueError("bpm must be positive")
    while bpm < lo:
        bpm *= 2
    while bpm > hi:
        bpm /= 2
    return float(min(max(bpm, lo), hi))


def bpm_from_onsets(onsets: list[float]) -> float | None:
    """Estimate BPM from note onset times (fallback when beat tracking fails).

    Scores each candidate tempo by how well the inter-onset intervals sit on
    its beat grid (whole beats, or half beats at a 15% discount). A tempo and
    its half/double score almost the same, so when the best tempo has a rival
    at half or double speed scoring within 10% of it, the one closer to 95 BPM
    wins. Approximate: tempo octave errors are possible (the user can override).
    """
    t = np.sort(np.asarray(onsets, dtype=float))
    ioi = np.diff(t)
    ioi = ioi[(ioi > 0.05) & (ioi < 4.0)]
    if len(ioi) < 3:
        return None
    grid = np.arange(BPM_MIN, BPM_MAX + 0.01, 0.5)
    scores = np.zeros(len(grid))
    for k, b in enumerate(grid):
        beat = 60.0 / b
        whole = (1 + np.cos(2 * np.pi * ioi / beat)) / 2
        half = 0.85 * (1 + np.cos(2 * np.pi * ioi / (beat / 2))) / 2
        scores[k] = float(np.mean(np.maximum(whole, half)))
    best = int(np.argmax(scores))
    best_b = float(grid[best])
    choice = best_b
    for rival in (best_b / 2, best_b * 2):
        if not (BPM_MIN <= rival <= BPM_MAX):
            continue
        near = np.abs(grid - rival) <= 1.5
        if scores[near].max() >= 0.9 * scores[best]:
            r = float(grid[near][int(np.argmax(scores[near]))])
            if abs(math.log(r / BPM_PREFERRED)) < abs(math.log(choice / BPM_PREFERRED)):
                choice = r
    return choice


def _beat_track_tempo(y: np.ndarray | None, sr: int) -> float | None:
    if y is None:
        return None
    try:
        import librosa

        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.atleast_1d(tempo)[0])
        if len(beats) < 4 or not math.isfinite(tempo) or tempo <= 0:
            return None
        return tempo
    except Exception:  # librosa missing or beat tracking failed: use the fallback
        return None


def detect_bpm(
    y: np.ndarray | None, sr: int, notes: list[Note], override: float | None = None
) -> tuple[dict, list[dict]]:
    """Returns ({bpm, bpm_source, method, trusted}, warnings). A user override always wins.

    `trusted` says whether the BPM may be used to place notes on a rhythmic grid (explicit
    quantisation only): True for a BPM the user set, or when beat tracking and the note-onset
    estimate agree. False when they disagree, when only one estimate exists, or for the
    placeholder. It never changes the BPM itself.
    """
    if override is not None:
        lo, hi = BPM_OVERRIDE_RANGE
        if not (lo <= float(override) <= hi):
            raise PipelineError("validation_error", f"BPM must be between {lo:g} and {hi:g}.")
        return {"bpm": round(float(override), 1), "bpm_source": "user", "method": "override", "trusted": True}, []

    tempo = _beat_track_tempo(y, sr)
    if tempo is not None:
        bpm = fold_bpm(tempo)
        warnings: list[dict] = []
        # Cross-check with the note timing. The reported BPM stays the beat-tracker's;
        # a disagreement only adds a warning, because either one may be half or double time.
        other = bpm_from_onsets([n["start"] for n in notes])
        disagree = other is not None and abs(math.log(bpm / other)) > math.log(1 + BPM_AGREEMENT_TOLERANCE)
        if disagree:
            warnings.append(
                make_warning(
                    "bpm_low_confidence",
                    f"Tempo estimates disagree: beat tracking found {bpm:.0f} BPM, note timing suggests "
                    f"{other:.0f} BPM. The tempo may be half or double time; set BPM by hand if it sounds wrong.",
                    "key_bpm",
                )
            )
        trusted = other is not None and not disagree
        return {"bpm": round(bpm, 1), "bpm_source": "auto", "method": "beat_track", "trusted": trusted}, warnings

    est = bpm_from_onsets([n["start"] for n in notes])
    if est is not None:
        return {"bpm": round(fold_bpm(est), 1), "bpm_source": "auto", "method": "note_onsets", "trusted": False}, []

    return (
        {"bpm": BPM_DEFAULT, "bpm_source": "auto", "method": "default", "trusted": False},
        [make_warning("bpm_low_confidence", "Tempo could not be measured; 100 BPM is a placeholder. Set it by hand.", "key_bpm")],
    )
