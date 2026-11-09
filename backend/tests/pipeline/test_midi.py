import importlib.util
import io
import math
import os
import tempfile
import unittest

import numpy as np

from app.pipeline import PipelineError
from app.pipeline.midi_export import (
    MIDI_RESOLUTION,
    build_midi,
    midi_bytes,
    select_exportable,
    write_midi,
)

HAVE_PM = importlib.util.find_spec("pretty_midi") is not None


def note(pitch=60, start=0.0, end=0.5, velocity=80, confidence=None):
    return {"pitch": pitch, "start": start, "end": end, "velocity": velocity, "confidence": confidence}


def tick_seconds(bpm):
    return 60.0 / (bpm * MIDI_RESOLUTION)


class SelectExportableTests(unittest.TestCase):
    """Pure logic: no pretty_midi needed."""

    def test_valid_notes_kept_in_order(self):
        kept, skipped = select_exportable([note(60, 0, 0.5, 90), note(64, 0.5, 1.0, 70)], 120)
        self.assertEqual(kept, [(60, 0.0, 0.5, 90), (64, 0.5, 1.0, 70)])
        self.assertEqual(skipped, 0)

    def test_zero_length_note_is_skipped(self):
        kept, skipped = select_exportable([note(60, 1.0, 1.0)], 100)
        self.assertEqual((kept, skipped), ([], 1))

    def test_zero_length_between_valid_notes(self):
        kept, skipped = select_exportable([note(60, 0, 0.5), note(62, 0.5, 0.5), note(64, 0.5, 1.0)], 100)
        self.assertEqual([k[0] for k in kept], [60, 64])
        self.assertEqual(skipped, 1)

    def test_shorter_than_one_tick_is_skipped_exactly_one_tick_is_kept(self):
        for bpm in (60, 100, 120, 200):
            tick = tick_seconds(bpm)
            kept, skipped = select_exportable([note(60, 1.0, 1.0 + tick * 0.9)], bpm)
            self.assertEqual((kept, skipped), ([], 1), bpm)
            kept, skipped = select_exportable([note(60, 1.0, 1.0 + tick * 1.01)], bpm)
            self.assertEqual((len(kept), skipped), (1, 0), bpm)

    def test_empty_list(self):
        self.assertEqual(select_exportable([], 100), ([], 0))

    def test_all_notes_skipped(self):
        kept, skipped = select_exportable([note(60, 1, 1), note(62, 2, 2)], 100)
        self.assertEqual((kept, skipped), ([], 2))

    def test_numpy_integers_and_integer_floats_are_accepted(self):
        kept, _ = select_exportable([note(np.int64(60), 0, 0.5, np.int32(80)), note(62.0, 0.5, 1.0, 80.0)], 100)
        self.assertEqual([(k[0], k[3]) for k in kept], [(60, 80), (62, 80)])
        self.assertTrue(all(type(k[0]) is int and type(k[3]) is int for k in kept))

    def test_invalid_notes_raise_validation_error(self):
        bad = {
            "missing key": {"pitch": 60, "start": 0.0, "end": 0.5},
            "nan start": note(start=float("nan")),
            "inf end": note(end=float("inf")),
            "negative start": note(start=-0.1, end=0.5),
            "end before start": note(start=1.0, end=0.5),
            "text start": note(start="abc"),
            "none end": note(end=None),
            "pitch too high": note(pitch=128),
            "pitch negative": note(pitch=-1),
            "fractional pitch": note(pitch=60.5),
            "bool pitch": note(pitch=True),
            "text pitch": note(pitch="C4"),
            "velocity zero": note(velocity=0),
            "velocity too high": note(velocity=128),
            "fractional velocity": note(velocity=80.5),
        }
        for label, n in bad.items():
            with self.subTest(label):
                with self.assertRaises(PipelineError) as cm:
                    select_exportable([note(), n], 100)
                self.assertEqual(cm.exception.code, "validation_error")

    def test_error_names_the_offending_note(self):
        with self.assertRaises(PipelineError) as cm:
            select_exportable([note(), note(), note(pitch=200)], 100)
        self.assertIn("Note 2", cm.exception.message)

    def test_invalid_note_wins_over_zero_length_skip(self):
        # a zero-length note with an impossible pitch is still reported, not silently dropped
        with self.assertRaises(PipelineError):
            select_exportable([note(pitch=200, start=1.0, end=1.0)], 100)

    def test_invalid_bpm_raises(self):
        for bpm in (0, -5, float("nan"), float("inf"), "fast", None):
            with self.subTest(bpm=bpm):
                with self.assertRaises(PipelineError) as cm:
                    select_exportable([note()], bpm)
                self.assertEqual(cm.exception.code, "validation_error")

    def test_inputs_are_not_modified(self):
        notes = [note(60, 0, 0.5), note(62, 1, 1)]
        before = [dict(n) for n in notes]
        select_exportable(notes, 100)
        self.assertEqual(notes, before)


@unittest.skipUnless(HAVE_PM, "pretty_midi not installed")
class MidiTests(unittest.TestCase):
    """Writes real MIDI bytes and reads them back with pretty_midi."""

    @staticmethod
    def _read(data):
        import pretty_midi

        return pretty_midi.PrettyMIDI(io.BytesIO(data))

    @staticmethod
    def _all_notes(pm):
        return [n for inst in pm.instruments for n in inst.notes]

    def _assert_tempo(self, pm, bpm):
        tempi = pm.get_tempo_changes()[1]
        self.assertGreaterEqual(len(tempi), 1)
        self.assertAlmostEqual(float(tempi[0]), bpm, delta=0.5)

    def test_round_trip(self):
        notes = [note(60, 0.0, 0.5, 90, 0.9), note(64, 0.5, 1.0, 70, None)]
        data = midi_bytes(notes, 120)
        self.assertEqual(data[:4], b"MThd")
        pm = self._read(data)
        self.assertEqual(len(pm.instruments), 1)
        self.assertEqual(pm.instruments[0].name, "melody")
        got = [(n.pitch, n.velocity) for n in pm.instruments[0].notes]
        self.assertEqual(got, [(60, 90), (64, 70)])
        self.assertAlmostEqual(pm.instruments[0].notes[1].start, 0.5, places=2)
        self._assert_tempo(pm, 120)

    def test_zero_length_note_is_never_exported(self):
        # The exporter drops the note; pretty_midi then reads back a file with no
        # instruments at all (it does not recreate an empty track), so the test
        # counts notes instead of indexing pm.instruments[0].
        data = midi_bytes([note(60, 1.0, 1.0)], 100)
        self.assertEqual(data[:4], b"MThd")
        pm = self._read(data)
        self.assertEqual(self._all_notes(pm), [])
        self._assert_tempo(pm, 100)

    def test_empty_list_gives_valid_tempo_only_file(self):
        data = midi_bytes([], 90)
        self.assertEqual(data[:4], b"MThd")
        pm = self._read(data)
        self.assertEqual(self._all_notes(pm), [])
        self._assert_tempo(pm, 90)

    def test_build_midi_keeps_a_named_empty_melody_track_in_memory(self):
        pm = build_midi([note(60, 1.0, 1.0)], 100)
        self.assertEqual([i.name for i in pm.instruments], ["melody"])
        self.assertEqual(pm.instruments[0].notes, [])

    def test_mixed_valid_and_invalid_lengths(self):
        tick = tick_seconds(100)
        notes = [
            note(60, 0.0, 0.5, 90),
            note(62, 0.5, 0.5, 80),  # zero length
            note(63, 0.6, 0.6 + tick * 0.5, 80),  # under one tick
            note(64, 0.7, 1.2, 70),
        ]
        pm = self._read(midi_bytes(notes, 100))
        got = [(n.pitch, n.velocity, round(n.start, 2), round(n.end, 2)) for n in self._all_notes(pm)]
        self.assertEqual(got, [(60, 90, 0.0, 0.5), (64, 70, 0.7, 1.2)])

    def test_all_notes_survive_with_timing_within_5_ms(self):
        notes = [note(48 + i % 12, i * 0.25, i * 0.25 + 0.2, 60 + i) for i in range(40)]
        got = sorted(self._all_notes(self._read(midi_bytes(notes, 117.5))), key=lambda n: n.start)
        self.assertEqual(len(got), len(notes))
        for src, out in zip(notes, got):
            self.assertEqual((out.pitch, out.velocity), (src["pitch"], src["velocity"]))
            self.assertLess(abs(out.start - src["start"]), 0.005)
            self.assertLess(abs(out.end - src["end"]), 0.005)

    def test_invalid_note_raises_and_produces_no_bytes(self):
        for bad in (note(pitch=130), note(velocity=0), note(start=float("nan")), note(start=-1, end=1)):
            with self.subTest(bad=bad):
                with self.assertRaises(PipelineError):
                    midi_bytes([note(), bad], 100)

    def test_values_are_not_clamped(self):
        # the old exporter clamped pitch 130 to 127; it must now refuse instead
        with self.assertRaises(PipelineError):
            midi_bytes([note(pitch=130)], 100)

    def test_write_midi_to_disk_round_trips(self):
        import pretty_midi

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.mid")
            write_midi(path, [note(60, 0, 0.5, 80), note(67, 0.5, 1.0, 80)], 100)
            self.assertTrue(os.path.getsize(path) > 14)
            pm = pretty_midi.PrettyMIDI(path)
        self.assertEqual([n.pitch for n in self._all_notes(pm)], [60, 67])
        self.assertTrue(math.isclose(pm.get_tempo_changes()[1][0], 100, abs_tol=0.5))

@unittest.skipUnless(HAVE_PM, "pretty_midi is not installed")
class CleanedMelodyMidiTests(unittest.TestCase):
    """The default (melody-preserving) cleanup of each real recording, exported and read back
    at tick level with an independent reader (smf_reader.py)."""

    def test_midi_matches_the_cleaned_json_for_every_real_recording(self):
        import json

        from app.pipeline.cleanup import clean_notes, scale_pitch_classes
        from smf_reader import read_smf

        data = os.path.join(os.path.dirname(__file__), "data")
        for name in ("hum_01_short", "hum_02_clean", "hum_03_noisy", "hum_04_pauses", "hum_05_long"):
            with self.subTest(recording=name):
                with open(os.path.join(data, f"real_{name}.json"), encoding="utf-8-sig") as f:
                    d = json.load(f)
                key, bpm = d["analysis"]["key"], d["analysis"]["bpm"]
                clean, _ = clean_notes(
                    d["notes_raw"], bpm, scale_pitch_classes(key["tonic"], key["mode"]), key_confidence=key["confidence"]
                )
                exportable, skipped = select_exportable(clean, bpm)
                self.assertEqual(skipped, 0)  # no note is lost to the export
                smf = read_smf(midi_bytes(clean, bpm))
                tick = tick_seconds(bpm)
                self.assertEqual(len(smf.notes), len(clean))  # note count matches the JSON
                self.assertAlmostEqual(smf.bpm, bpm, places=2)  # header tempo == analysis.bpm
                self.assertEqual(smf.division, MIDI_RESOLUTION)
                ordered = sorted(clean, key=lambda n: (n["start"], n["pitch"]))
                for m, c in zip(smf.notes, ordered):
                    self.assertEqual((m.pitch, m.velocity), (c["pitch"], c["velocity"]))
                    self.assertLessEqual(abs(m.start_tick * tick - c["start"]), tick + 1e-9)
                    self.assertLessEqual(abs(m.end_tick * tick - c["end"]), tick + 1e-9)
                for a, b in zip(smf.notes, smf.notes[1:]):
                    self.assertLessEqual(a.end_tick, b.start_tick + 1)  # no overlap beyond tick rounding


if __name__ == "__main__":
    unittest.main()
