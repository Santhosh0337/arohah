"""A small Standard MIDI File reader (standard library only) for tick-exact checks.

It exists so MIDI tests do not depend on the library that wrote the file: the header tempo,
the ticks-per-quarter-note and every note's start and end tick are read straight from the bytes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SmfNote:
    pitch: int
    velocity: int
    start_tick: int
    end_tick: int


@dataclass
class Smf:
    division: int  # ticks per quarter note
    tempo_us: int | None  # microseconds per quarter note of the first tempo event
    notes: list[SmfNote]
    tracks: int

    @property
    def bpm(self) -> float | None:
        return None if self.tempo_us is None else 60_000_000 / self.tempo_us

    def tick_seconds(self, bpm: float | None = None) -> float:
        return 60.0 / ((bpm or self.bpm) * self.division)


def _vlq(data: bytes, i: int) -> tuple[int, int]:
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def read_smf(data: bytes) -> Smf:
    if data[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    ntrks = int.from_bytes(data[10:12], "big")
    division = int.from_bytes(data[12:14], "big")
    if division & 0x8000:
        raise ValueError("SMPTE time division is not supported")
    i = 8 + int.from_bytes(data[4:8], "big")
    tempo_us = None
    notes: list[SmfNote] = []
    for _ in range(ntrks):
        if data[i : i + 4] != b"MTrk":
            raise ValueError("track chunk expected")
        length = int.from_bytes(data[i + 4 : i + 8], "big")
        j, end, tick, status = i + 8, i + 8 + length, 0, 0
        open_notes: dict[tuple[int, int], tuple[int, int]] = {}
        while j < end:
            delta, j = _vlq(data, j)
            tick += delta
            if data[j] & 0x80:
                status = data[j]
                j += 1
            if status == 0xFF:  # meta event
                kind = data[j]
                ln, j = _vlq(data, j + 1)
                if kind == 0x51 and tempo_us is None:
                    tempo_us = int.from_bytes(data[j : j + 3], "big")
                j += ln
            elif status in (0xF0, 0xF7):  # sysex
                ln, j = _vlq(data, j)
                j += ln
            else:
                kind, channel = status & 0xF0, status & 0x0F
                size = 1 if kind in (0xC0, 0xD0) else 2
                a = data[j]
                b = data[j + 1] if size == 2 else 0
                j += size
                if kind == 0x90 and b > 0:
                    open_notes[(channel, a)] = (tick, b)
                elif kind == 0x80 or (kind == 0x90 and b == 0):
                    started = open_notes.pop((channel, a), None)
                    if started is not None:
                        notes.append(SmfNote(a, started[1], started[0], tick))
        i = end
    notes.sort(key=lambda n: (n.start_tick, n.pitch))
    return Smf(division, tempo_us, notes, ntrks)
