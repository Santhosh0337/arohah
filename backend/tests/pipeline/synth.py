"""Synthetic test signals. These are test fixtures, NOT sample recordings:
real hums for the eval go in backend/samples/."""
from __future__ import annotations

import wave

import numpy as np

SR = 22050
HOP = 256


def midi_to_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def make_hum(notes: list[tuple[int, float]], gap: float = 0.06, lead: float = 0.3, tail: float = 0.3,
             vibrato_cents: float = 20.0, sr: int = SR, amp: float = 0.4) -> np.ndarray:
    """notes = [(midi, seconds)]. Sine tone with mild vibrato, silence around."""
    parts = [np.zeros(int(lead * sr))]
    for m, dur in notes:
        t = np.arange(int(dur * sr)) / sr
        f = midi_to_hz(m) * 2 ** ((vibrato_cents / 1200) * np.sin(2 * np.pi * 5.5 * t))
        phase = 2 * np.pi * np.cumsum(f) / sr
        env = np.minimum(1.0, np.minimum(t / 0.01, (dur - t) / 0.01))
        parts.append(amp * env * np.sin(phase))
        parts.append(np.zeros(int(gap * sr)))
    parts.append(np.zeros(int(tail * sr)))
    return np.concatenate(parts).astype(np.float32)


def write_wav(path: str, y: np.ndarray, sr: int = SR) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())


def f0_track(schedule: list[tuple[int, float]], total_s: float, start_s: float, hop: int = HOP, sr: int = SR,
             gap: float = 0.06):
    """Ideal pYIN-like output for a schedule of (midi, dur) starting at start_s."""
    n = 1 + int(total_s * sr) // hop
    times = np.arange(n) * hop / sr
    f0 = np.full(n, np.nan)
    prob = np.full(n, 0.1)
    t0 = start_s
    for m, dur in schedule:
        sel = (times >= t0) & (times < t0 + dur)
        f0[sel] = midi_to_hz(m)
        prob[sel] = 0.9
        t0 += dur + gap
    return times, f0, prob
