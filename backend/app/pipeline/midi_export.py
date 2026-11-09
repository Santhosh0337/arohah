"""MIDI export, first version (F14): the melody track only.

Chords, bass and drums join in Phase A3 (the contract lists tracks melody,
chords, bass, drums); the signature is already keyword-extensible.

What gets exported
------------------
* A note is exported only if it lasts at least one MIDI tick at the given
  tempo. Zero-length notes (end == start), and notes so short that they would
  round to zero ticks, are never written: a note-on and note-off on the same
  tick can leave a hanging or silent note in some players. Skipped notes are
  counted in a log warning.
* Structurally invalid notes (missing keys, non-numeric or non-finite times,
  a negative start, end before start, pitch outside 0..127, velocity outside
  1..127) raise PipelineError("validation_error"). Pydantic's Note model
  already rejects them upstream, so this only fires on misuse. Values are
  never silently clamped: that would change the melody without telling anyone.
* An empty list, or a list in which every note was skipped, still produces a
  valid MIDI file: header, tempo, and a named but empty "melody" track. This
  is deliberate. The exporter does not decide whether an empty export is
  meaningful (a later phase may export chords or drums with no melody); the
  caller does. Note that pretty_midi does not recreate an empty instrument
  when it reads such a file back, so a reader sees tempo and no instruments.
"""
from __future__ import annotations

import io
import logging
import math
from numbers import Integral
from typing import Any

from . import Note, PipelineError

log = logging.getLogger(__name__)

MIDI_RESOLUTION = 220  # ticks per beat; pretty_midi's default


def _as_int(value: Any, what: str, index: int) -> int:
    if isinstance(value, bool):
        raise PipelineError("validation_error", f"Note {index}: {what} must be a number, not a bool.")
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise PipelineError("validation_error", f"Note {index}: {what} must be a whole number, got {value!r}.")


def select_exportable(
    notes: list[Note], bpm: float, resolution: int = MIDI_RESOLUTION
) -> tuple[list[tuple[int, float, float, int]], int]:
    """Validate notes and drop the ones that cannot be exported.

    Returns ([(pitch, start, end, velocity), ...], skipped_count).
    Raises PipelineError("validation_error") for a bad tempo or an invalid note.
    """
    try:
        bpm = float(bpm)
    except (TypeError, ValueError) as e:
        raise PipelineError("validation_error", f"BPM must be a number, got {bpm!r}.") from e
    if not math.isfinite(bpm) or bpm <= 0:
        raise PipelineError("validation_error", f"BPM must be a positive number, got {bpm!r}.")
    tick_s = 60.0 / (bpm * resolution)

    kept: list[tuple[int, float, float, int]] = []
    skipped = 0
    for i, n in enumerate(notes):
        try:
            raw_pitch, raw_start, raw_end, raw_vel = n["pitch"], n["start"], n["end"], n["velocity"]
            start, end = float(raw_start), float(raw_end)
        except (KeyError, TypeError, ValueError) as e:
            raise PipelineError("validation_error", f"Note {i} is malformed: {e!r}.") from e
        if not (math.isfinite(start) and math.isfinite(end)):
            raise PipelineError("validation_error", f"Note {i}: start and end must be finite numbers.")
        if start < 0:
            raise PipelineError("validation_error", f"Note {i}: start must not be negative (got {start}).")
        if end < start:
            raise PipelineError("validation_error", f"Note {i}: end ({end}) is before start ({start}).")
        pitch = _as_int(raw_pitch, "pitch", i)
        velocity = _as_int(raw_vel, "velocity", i)
        if not 0 <= pitch <= 127:
            raise PipelineError("validation_error", f"Note {i}: pitch must be 0..127, got {pitch}.")
        if not 1 <= velocity <= 127:
            raise PipelineError("validation_error", f"Note {i}: velocity must be 1..127, got {velocity}.")
        if end - start < tick_s:  # zero-length, or less than one MIDI tick
            skipped += 1
            continue
        kept.append((pitch, start, end, velocity))
    return kept, skipped


def build_midi(notes: list[Note], bpm: float, *, program: int = 0):
    """Notes -> pretty_midi.PrettyMIDI with one 'melody' track (possibly empty)."""
    try:
        import pretty_midi
    except ImportError as e:
        raise PipelineError("internal", "pretty_midi is not installed (pip install -r backend/requirements.txt).") from e
    kept, skipped = select_exportable(notes, bpm)
    if skipped:
        log.warning("MIDI export skipped %d of %d note(s) shorter than one MIDI tick.", skipped, len(notes))
    if not kept:
        log.warning("MIDI export has no notes: writing a tempo-only file.")
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(bpm))
    inst = pretty_midi.Instrument(program=program, name="melody")
    for pitch, start, end, velocity in kept:
        inst.notes.append(pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end))
    pm.instruments.append(inst)
    return pm


def midi_bytes(notes: list[Note], bpm: float) -> bytes:
    buf = io.BytesIO()
    build_midi(notes, bpm).write(buf)
    return buf.getvalue()


def write_midi(path: str, notes: list[Note], bpm: float) -> None:
    with open(path, "wb") as f:
        f.write(midi_bytes(notes, bpm))
