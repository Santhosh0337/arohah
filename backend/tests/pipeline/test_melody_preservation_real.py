"""A1 melody-preservation regression tests on the real recordings.

The fixtures in data/ are outputs of the pipeline on five real hums (see data/README.md).
There is no ground truth for them, so nothing here says which notes are "right". The tests
check properties that must hold whatever was hummed: nothing is deleted, nothing is moved
without cause, weak evidence changes nothing, and the MIDI agrees with the JSON.
"""
import copy
import json
import os
import unittest
from unittest import mock

import numpy as np

from app.pipeline import pitch as pitch_mod
from app.pipeline.cleanup import SNAP_MIN_KEY_CONFIDENCE, clean_notes, scale_pitch_classes
from app.pipeline.pitch import HOP, MIN_NOTE_CONFIDENCE, drop_low_confidence, segment_notes

from smf_reader import read_smf

DATA = os.path.join(os.path.dirname(__file__), "data")
NAMES = ["hum_01_short", "hum_02_clean", "hum_03_noisy", "hum_04_pauses", "hum_05_long"]


def load(name):
    with open(os.path.join(DATA, f"real_{name}.json"), encoding="utf-8-sig") as f:
        return json.load(f)


def load_f0(name):
    with open(os.path.join(DATA, f"real_{name}_f0.json"), encoding="utf-8-sig") as f:
        d = json.load(f)
    return tuple(np.array(d[k], dtype=float) for k in ("times", "f0", "voiced_prob", "rms"))


def cleaned(name, **kw):
    d = load(name)
    key, bpm = d["analysis"]["key"], d["analysis"]["bpm"]
    pcs = scale_pitch_classes(key["tonic"], key["mode"])
    kw.setdefault("key_confidence", key["confidence"])
    return d, clean_notes(d["notes_raw"], bpm, pcs, **kw)


def touching_same_pitch_pairs(raw):
    return sum(1 for a, b in zip(raw, raw[1:]) if a["pitch"] == b["pitch"] and abs(b["start"] - a["end"]) <= 2e-4)


class FixtureTests(unittest.TestCase):
    def test_both_required_recordings_and_all_five_are_present(self):
        self.assertIn("hum_02_clean", NAMES)
        self.assertIn("hum_05_long", NAMES)
        for name in NAMES:
            raw = load(name)["notes_raw"]
            self.assertGreater(len(raw), 10, name)
            self.assertEqual([n["start"] for n in raw], sorted(n["start"] for n in raw), name)


class RealCleanupTests(unittest.TestCase):
    def each(self):
        for name in NAMES:
            with self.subTest(recording=name):
                yield name

    def test_default_cleanup_keeps_every_note_except_touching_same_pitch_pairs(self):
        for name in self.each():
            d, (out, rep) = cleaned(name)
            self.assertEqual(len(out), len(d["notes_raw"]) - touching_same_pitch_pairs(d["notes_raw"]))
            self.assertEqual(rep.merged, len(d["notes_raw"]) - len(out))

    def test_default_cleanup_keeps_the_hummed_timing(self):
        for name in self.each():
            d, (out, _) = cleaned(name)
            raw_starts = {n["start"] for n in d["notes_raw"]}
            raw_ends = {n["end"] for n in d["notes_raw"]}
            for n in out:
                self.assertIn(n["start"], raw_starts)
                self.assertIn(n["end"], raw_ends)

    def test_raw_notes_are_not_modified(self):
        for name in self.each():
            d = load(name)
            before = copy.deepcopy(d["notes_raw"])
            cleaned(name, key_confidence=0.95, quantize=True, tempo_trusted=True)
            self.assertEqual(load(name)["notes_raw"], before)

    def test_weak_key_confidence_changes_pitches_by_octaves_only_and_says_so(self):
        checked = 0
        for name in self.each():
            d, (out, rep) = cleaned(name)
            if d["analysis"]["key"]["confidence"] >= SNAP_MIN_KEY_CONFIDENCE:
                continue
            checked += 1
            self.assertEqual(rep.snap_skipped_reason, "low_key_confidence")
            self.assertEqual(rep.snapped, 0)
            raw = d["notes_raw"]
            self.assertEqual(len(out), len(raw) - rep.merged)
            if rep.merged == 0:
                for r, c in zip(raw, out):
                    self.assertEqual((r["pitch"] - c["pitch"]) % 12, 0)  # at most an octave correction
        self.assertGreater(checked, 0, "the recordings include weak-key cases (e.g. hum_02_clean, hum_05_long)")

    def test_hum_02_clean_and_hum_05_long_have_weak_keys(self):
        # observed in the supplied run, not an accuracy claim
        for name in ("hum_02_clean", "hum_05_long"):
            self.assertLess(load(name)["analysis"]["key"]["confidence"], SNAP_MIN_KEY_CONFIDENCE, name)

    def test_even_a_confident_key_cannot_collapse_a_transition_or_move_a_pitch_far(self):
        for name in self.each():
            d = load(name)
            key, bpm = d["analysis"]["key"], d["analysis"]["bpm"]
            pcs = scale_pitch_classes(key["tonic"], key["mode"])
            base, _ = clean_notes(d["notes_raw"], bpm, pcs, snap_to_scale=False)
            snapped, rep = clean_notes(d["notes_raw"], bpm, pcs, key_confidence=0.95)
            self.assertEqual(len(base), len(snapped))
            for a, b in zip(base, snapped):
                self.assertLessEqual(abs(a["pitch"] - b["pitch"]), 1)
                self.assertEqual((a["start"], a["end"]), (b["start"], b["end"]))
            for i in range(len(base) - 1):
                if base[i]["pitch"] != base[i + 1]["pitch"]:
                    self.assertNotEqual(snapped[i]["pitch"], snapped[i + 1]["pitch"], (name, i))

    def test_snapping_is_not_biased_downward(self):
        ups = downs = 0
        for name in self.each():
            d = load(name)
            key, bpm = d["analysis"]["key"], d["analysis"]["bpm"]
            pcs = scale_pitch_classes(key["tonic"], key["mode"])
            base, _ = clean_notes(d["notes_raw"], bpm, pcs, snap_to_scale=False)
            snapped, _ = clean_notes(d["notes_raw"], bpm, pcs, key_confidence=0.95)
            ups += sum(1 for a, b in zip(base, snapped) if b["pitch"] > a["pitch"])
            downs += sum(1 for a, b in zip(base, snapped) if b["pitch"] < a["pitch"])
        # the old rule moved every changed note down (34 of 34 on hum_05_long)
        self.assertGreater(ups + downs, 0)
        self.assertGreater(ups, 0)

    def test_explicit_quantising_never_loses_or_reorders_notes_and_never_runs_on_weak_evidence(self):
        for name in self.each():
            d, (default, _) = cleaned(name)
            _, (out, rep) = cleaned(name, quantize=True, tempo_trusted=True)
            self.assertEqual(len(out), len(default))
            self.assertEqual([n["pitch"] for n in out], [n["pitch"] for n in default])
            if not rep.quantised:
                self.assertEqual(out, default)  # refused: timing exactly as hummed
                self.assertIsNotNone(rep.quantise_skipped_reason)

    def test_an_untrusted_tempo_never_quantises(self):
        for name in self.each():
            d, (default, _) = cleaned(name)
            _, (out, rep) = cleaned(name, quantize=True, tempo_trusted=False)
            self.assertEqual(out, default)
            self.assertEqual(rep.quantise_skipped_reason, "tempo_not_trusted")

    def test_note_durations_are_the_hummed_durations(self):
        # no note is shortened or lengthened except by merging touching notes
        for name in self.each():
            d, (out, rep) = cleaned(name)
            if rep.merged == 0:
                for r, c in zip(d["notes_raw"], out):
                    self.assertEqual(r["end"] - r["start"], c["end"] - c["start"])


class RealExtractionTests(unittest.TestCase):
    """pitch.py on the saved pYIN output of each recording (see data/README.md for the caveat)."""

    HOP_S = HOP / 22050

    def segments(self, name, with_fragment_test=True):
        times, f0, prob, rms = load_f0(name)
        if with_fragment_test:
            return segment_notes(times, f0, prob, rms, self.HOP_S)
        with mock.patch.object(pitch_mod, "transition_fragments", lambda notes, drift: set()):
            return segment_notes(times, f0, prob, rms, self.HOP_S)

    @staticmethod
    def key(n):
        return (n["pitch"], n["start"], n["end"])

    def test_every_note_the_old_80_ms_rule_kept_is_still_kept(self):
        for name in NAMES:
            with self.subTest(recording=name):
                old_kept = [n for n in drop_low_confidence(self.segments(name, False)) if n["end"] - n["start"] >= 0.08]
                now = {self.key(n) for n in drop_low_confidence(self.segments(name))}
                self.assertGreater(len(old_kept), 5)
                for n in old_kept:
                    self.assertIn(self.key(n), now)

    def test_short_notes_are_now_retained(self):
        total_short = 0
        for name in NAMES:
            with self.subTest(recording=name):
                short = [n for n in drop_low_confidence(self.segments(name)) if n["end"] - n["start"] < 0.08]
                total_short += len(short)
        self.assertGreater(total_short, 0)

    def test_only_segments_under_80_ms_are_ever_rejected_as_fragments(self):
        for name in NAMES:
            with self.subTest(recording=name):
                everything = self.segments(name, False)
                kept = {self.key(n) for n in self.segments(name)}
                for n in everything:
                    if self.key(n) not in kept:
                        self.assertLess(n["end"] - n["start"], 0.08)

    def test_what_is_rejected_as_a_fragment_lies_between_its_touching_neighbours(self):
        for name in NAMES:
            with self.subTest(recording=name):
                everything = self.segments(name, False)
                kept = {self.key(n) for n in self.segments(name)}
                for i, n in enumerate(everything):
                    if self.key(n) in kept:
                        continue
                    before, after = everything[i - 1], everything[i + 1]
                    self.assertLessEqual(n["start"] - before["end"], 2e-4)
                    self.assertLessEqual(after["start"] - n["end"], 2e-4)
                    self.assertLessEqual(min(before["pitch"], after["pitch"]), n["pitch"])
                    self.assertGreaterEqual(max(before["pitch"], after["pitch"]), n["pitch"])

    def test_the_confidence_floor_still_rejects_unreliable_detections(self):
        for name in NAMES:
            with self.subTest(recording=name):
                everything = self.segments(name)
                kept = drop_low_confidence(everything)
                self.assertTrue(all(n["confidence"] is None or n["confidence"] >= MIN_NOTE_CONFIDENCE for n in kept))
                self.assertTrue(any(n["confidence"] is not None and n["confidence"] < MIN_NOTE_CONFIDENCE for n in everything))

    def test_notes_are_ordered_and_do_not_overlap(self):
        for name in NAMES:
            with self.subTest(recording=name):
                notes = drop_low_confidence(self.segments(name))
                for a, b in zip(notes, notes[1:]):
                    self.assertLessEqual(a["end"], b["start"] + 1e-9)


class SuppliedMidiTests(unittest.TestCase):
    """The MIDI files exported by the earlier real run, read at tick level (no pretty_midi)."""

    def test_midi_matches_its_json(self):
        for name in ("hum_02_clean", "hum_05_long"):
            with self.subTest(recording=name):
                d = load(name)
                with open(os.path.join(DATA, f"real_{name}.mid"), "rb") as f:
                    smf = read_smf(f.read())
                clean = d["notes_clean"]
                self.assertEqual(len(smf.notes), len(clean))  # count matches the cleaned JSON
                self.assertAlmostEqual(smf.bpm, d["analysis"]["bpm"], places=1)  # header tempo == analysis.bpm
                tick = smf.tick_seconds(d["analysis"]["bpm"])
                for m, c in zip(smf.notes, sorted(clean, key=lambda x: (x["start"], x["pitch"]))):
                    self.assertEqual(m.pitch, c["pitch"])
                    self.assertEqual(m.velocity, c["velocity"])
                    self.assertLessEqual(abs(m.start_tick * tick - c["start"]), tick + 1e-9)  # within one tick
                    self.assertLessEqual(abs(m.end_tick * tick - c["end"]), tick + 1e-9)
                for a, b in zip(smf.notes, smf.notes[1:]):
                    self.assertLessEqual(a.end_tick, b.start_tick + 1)  # no overlap beyond rounding


if __name__ == "__main__":
    unittest.main()
