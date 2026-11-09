import unittest
from unittest import mock

import numpy as np

import synth
from app.pipeline import PipelineError
from app.pipeline import pitch as pitch_mod
from app.pipeline.pitch import (
    DRIFT_SEMITONES_PER_S,
    FRAGMENT_TEST_MAX_S,
    HOP,
    MIN_NOTE_CONFIDENCE,
    TOUCH_TOLERANCE_S,
    drop_low_confidence,
    extract_notes,
    segment_notes,
    transition_fragments,
)

HOP_S = HOP / synth.SR


def _segment(schedule, total=4.0, start=0.2, gap=0.06):
    times, f0, prob = synth.f0_track(schedule, total, start, gap=gap)
    return segment_notes(times, f0, prob, None, HOP / synth.SR)


class SegmentTests(unittest.TestCase):
    def test_three_steady_notes(self):
        notes = _segment([(60, 0.5), (64, 0.5), (67, 0.5)])
        self.assertEqual([n["pitch"] for n in notes], [60, 64, 67])
        self.assertAlmostEqual(notes[0]["start"], 0.2, delta=0.02)
        self.assertAlmostEqual(notes[0]["end"] - notes[0]["start"], 0.5, delta=0.03)

    def test_legato_step_splits_without_gap(self):
        notes = _segment([(60, 0.5), (62, 0.5)], gap=0.0)
        self.assertEqual([n["pitch"] for n in notes], [60, 62])

    def test_vibrato_does_not_split(self):
        times = np.arange(0, 120) * HOP / synth.SR
        cents = 30 * np.sin(2 * np.pi * 5.5 * times)
        f0 = synth.midi_to_hz(60) * 2 ** (cents / 1200)
        notes = segment_notes(times, f0, np.full(len(f0), 0.9), None, HOP / synth.SR)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["pitch"], 60)

    def test_single_frame_glitch_ignored(self):
        times = np.arange(0, 80) * HOP / synth.SR
        f0 = np.full(80, synth.midi_to_hz(60))
        f0[40] = synth.midi_to_hz(72)  # one-frame octave error
        notes = segment_notes(times, f0, np.full(80, 0.9), None, HOP / synth.SR)
        self.assertEqual([n["pitch"] for n in notes], [60])

    def test_short_note_is_kept_when_its_pitch_is_steady(self):
        # A3 melody-preservation decision: no minimum note length. This 50 ms note used to be dropped.
        notes = _segment([(60, 0.5), (65, 0.05), (67, 0.5)])
        self.assertEqual([n["pitch"] for n in notes], [60, 65, 67])
        self.assertLess(notes[1]["end"] - notes[1]["start"], 0.08)

    def test_same_pitch_dropout_merged(self):
        times = np.arange(0, 100) * HOP / synth.SR
        f0 = np.full(100, synth.midi_to_hz(64))
        f0[40:43] = np.nan  # 3 frames (~35 ms) of pYIN dropout
        notes = segment_notes(times, f0, np.full(100, 0.9), None, HOP / synth.SR)
        self.assertEqual(len(notes), 1)

    def test_all_unvoiced_gives_no_notes(self):
        times = np.arange(0, 50) * HOP / synth.SR
        self.assertEqual(segment_notes(times, np.full(50, np.nan), None, None), [])

    def test_velocity_follows_loudness_and_stays_in_range(self):
        times = np.arange(0, 200) * HOP / synth.SR
        f0 = np.where(times < 1.1, synth.midi_to_hz(60), synth.midi_to_hz(67))
        rms = np.where(times < 1.1, 0.4, 0.1)
        notes = segment_notes(times, f0, None, rms, HOP / synth.SR)
        self.assertEqual(len(notes), 2)
        self.assertGreater(notes[0]["velocity"], notes[1]["velocity"])
        for n in notes:
            self.assertTrue(1 <= n["velocity"] <= 127)
            self.assertIsNone(n["confidence"])


def _glide_track(parts, total_s=3.0):
    """parts = [("hold", midi, dur) | ("glide", from_midi, to_midi, dur)], continuously voiced,
    starting at 0.2 s. Returns (times, f0, prob)."""
    n = 1 + int(total_s * synth.SR) // HOP
    times = np.arange(n) * HOP / synth.SR
    midi = np.full(n, np.nan)
    t0 = 0.2
    for p in parts:
        dur = p[-1]
        sel = (times >= t0) & (times < t0 + dur)
        if p[0] == "hold":
            midi[sel] = p[1]
        else:
            midi[sel] = np.linspace(p[1], p[2], int(sel.sum()))
        t0 += dur
    f0 = np.where(np.isfinite(midi), 440.0 * 2 ** ((midi - 69) / 12), np.nan)
    return times, f0, np.where(np.isfinite(midi), 0.9, 0.1)


class ShortNoteTests(unittest.TestCase):
    """There is no minimum note length. A short segment is rejected only when it is unreliable."""

    def test_short_notes_in_a_fast_legato_run_survive(self):
        # five touching 70 ms notes with a steady pitch each: a fast scale, not glide fragments
        run = [(60, 0.07), (62, 0.07), (64, 0.07), (65, 0.07), (67, 0.07)]
        notes = _segment([(60, 0.5)] + run + [(72, 0.5)], gap=0.0)
        self.assertEqual([n["pitch"] for n in notes], [60, 62, 64, 65, 67, 72])  # the 70 ms notes all stay
        self.assertTrue(all(n["end"] - n["start"] < 0.08 for n in notes[1:5]))

    def test_isolated_notes_of_any_length_above_a_few_frames_survive(self):
        for dur in (0.035, 0.05, 0.07, 0.1):
            with self.subTest(dur=dur):
                notes = _segment([(60, 0.5), (65, dur), (67, 0.5)])
                self.assertIn(65, [n["pitch"] for n in notes])

    def test_a_glide_between_two_notes_does_not_become_extra_notes(self):
        times, f0, prob = _glide_track([("hold", 60, 0.5), ("glide", 60, 67, 0.25), ("hold", 67, 0.5)])
        notes = segment_notes(times, f0, prob, None, HOP_S)
        self.assertEqual([n["pitch"] for n in notes], [60, 67])  # the passing pitches are not notes

    def test_a_slow_slide_keeps_its_long_segments(self):
        # segments of 80 ms or more are never judged as fragments: nothing the old code kept is lost
        times, f0, prob = _glide_track([("hold", 60, 0.4), ("glide", 60, 66, 1.2), ("hold", 66, 0.4)], total_s=3.0)
        notes = segment_notes(times, f0, prob, None, HOP_S)
        self.assertEqual([n["pitch"] for n in notes], [60, 61, 62, 63, 64, 65, 66])  # a staircase, all kept
        self.assertTrue(all(n["end"] - n["start"] >= FRAGMENT_TEST_MAX_S for n in notes[1:-1]))

    def test_a_single_frame_blip_between_two_notes_is_not_a_note(self):
        times, f0, prob = _glide_track([("hold", 60, 0.5), ("hold", 64, HOP_S * 1.2), ("hold", 67, 0.5)])
        notes = segment_notes(times, f0, prob, None, HOP_S)
        self.assertEqual([n["pitch"] for n in notes], [60, 67])

    def test_short_noisy_detection_is_rejected_by_reliability_not_duration(self):
        # same 60 ms length: the confident one is kept, the unreliable one is not
        for prob, expect in ((0.9, True), (0.04, False)):
            with self.subTest(prob=prob):
                times = np.arange(0, 3.0 * synth.SR / HOP) * HOP / synth.SR
                f0 = np.full(len(times), np.nan)
                p = np.zeros(len(times))
                for midi, start, dur, pr in ((60, 0.2, 0.6, 0.9), (65, 1.2, 0.06, prob), (67, 1.8, 0.6, 0.9)):
                    sel = (times >= start) & (times < start + dur)
                    f0[sel] = synth.midi_to_hz(midi)
                    p[sel] = pr
                with mock.patch.object(pitch_mod, "compute_f0", lambda y, sr_, hop=HOP: (times, f0, p)):
                    notes, _ = extract_notes(np.zeros(int(3.0 * synth.SR), dtype=np.float32), synth.SR)
                self.assertEqual(65 in [n["pitch"] for n in notes], expect)

    def test_a_long_unreliable_note_is_rejected_too(self):
        # so the rule is the confidence, not the length: a 0.6 s note at probability 0.05 goes
        times = np.arange(0, 3.0 * synth.SR / HOP) * HOP / synth.SR
        f0 = np.full(len(times), np.nan)
        p = np.zeros(len(times))
        for midi, start, dur, pr in ((60, 0.2, 0.6, 0.9), (65, 1.2, 0.6, 0.05)):
            sel = (times >= start) & (times < start + dur)
            f0[sel], p[sel] = synth.midi_to_hz(midi), pr
        with mock.patch.object(pitch_mod, "compute_f0", lambda y, sr_, hop=HOP: (times, f0, p)):
            notes, _ = extract_notes(np.zeros(int(3.0 * synth.SR), dtype=np.float32), synth.SR)
        self.assertEqual([n["pitch"] for n in notes], [60])

    def test_nothing_the_old_80_ms_rule_kept_is_lost(self):
        times, f0, prob = _glide_track([("hold", 60, 0.3), ("glide", 60, 64, 0.2), ("hold", 64, 0.3), ("hold", 65, 0.1), ("hold", 62, 0.4)])
        with mock.patch.object(pitch_mod, "transition_fragments", lambda notes, drift: set()):
            no_fragment_test = segment_notes(times, f0, prob, None, HOP_S)
        kept_by_old_rule = [n for n in no_fragment_test if n["end"] - n["start"] >= 0.08]
        now = {(n["pitch"], n["start"], n["end"]) for n in segment_notes(times, f0, prob, None, HOP_S)}
        for n in kept_by_old_rule:
            self.assertIn((n["pitch"], n["start"], n["end"]), now)


def _frag(pitch, start, end):
    return {"pitch": pitch, "start": start, "end": end, "velocity": 80, "confidence": 0.9}


class TransitionFragmentTests(unittest.TestCase):
    """The rule itself, on hand-made notes. drift is semitones per second, None = not measurable."""

    NOTES = [_frag(60, 0.0, 0.5), _frag(62, 0.5, 0.55), _frag(64, 0.55, 1.0)]
    FAST, STEADY = DRIFT_SEMITONES_PER_S * 2, 1.0

    def test_touching_between_and_moving_is_a_fragment(self):
        self.assertEqual(transition_fragments(self.NOTES, [None, self.FAST, None]), {1})
        self.assertEqual(transition_fragments(self.NOTES, [None, -self.FAST, None]), {1})

    def test_threshold_is_inclusive(self):
        self.assertEqual(transition_fragments(self.NOTES, [None, DRIFT_SEMITONES_PER_S, None]), {1})
        self.assertEqual(transition_fragments(self.NOTES, [None, DRIFT_SEMITONES_PER_S - 0.01, None]), set())

    def test_too_short_to_measure_counts_as_moving(self):
        self.assertEqual(transition_fragments(self.NOTES, [None, None, None]), {1})

    def test_a_steady_pitch_is_a_note(self):
        self.assertEqual(transition_fragments(self.NOTES, [None, self.STEADY, None]), set())

    def test_an_isolated_short_note_is_never_a_fragment(self):
        gap_before = [_frag(60, 0.0, 0.5), _frag(62, 0.6, 0.65), _frag(64, 0.65, 1.0)]
        gap_after = [_frag(60, 0.0, 0.5), _frag(62, 0.5, 0.55), _frag(64, 0.7, 1.0)]
        for notes in (gap_before, gap_after):
            self.assertEqual(transition_fragments(notes, [None, self.FAST, None]), set())

    def test_a_note_outside_its_neighbours_pitch_range_is_an_ornament_not_a_glide(self):
        notes = [_frag(60, 0.0, 0.5), _frag(67, 0.5, 0.55), _frag(62, 0.55, 1.0)]
        self.assertEqual(transition_fragments(notes, [None, self.FAST, None]), set())

    def test_the_first_and_last_notes_are_never_fragments(self):
        self.assertEqual(transition_fragments(self.NOTES, [self.FAST, self.STEADY, self.FAST]), set())

    def test_a_segment_of_80_ms_or_more_is_never_judged(self):
        end = round(0.5 + FRAGMENT_TEST_MAX_S + 0.001, 4)  # clearly above the limit (floats make 80.0 ms ambiguous)
        notes = [_frag(60, 0.0, 0.5), _frag(62, 0.5, end), _frag(64, end, 1.0)]
        self.assertEqual(transition_fragments(notes, [None, self.FAST, None]), set())

    def test_a_glide_of_several_fragments_is_removed_as_a_whole(self):
        notes = [_frag(60, 0.0, 0.5), _frag(61, 0.5, 0.53), _frag(62, 0.53, 0.56), _frag(63, 0.56, 0.59), _frag(64, 0.59, 1.0)]
        self.assertEqual(transition_fragments(notes, [None, self.FAST, self.FAST, self.FAST, None]), {1, 2, 3})

    def test_edges_within_the_time_rounding_still_touch(self):
        notes = [_frag(60, 0.0, 0.5), _frag(62, 0.5 + TOUCH_TOLERANCE_S, 0.55), _frag(64, 0.55, 1.0)]
        self.assertEqual(transition_fragments(notes, [None, self.FAST, None]), {1})

    def test_short_lists(self):
        self.assertEqual(transition_fragments([], []), set())
        self.assertEqual(transition_fragments(self.NOTES[:2], [None, None]), set())


def _note(pitch, conf):
    return {"pitch": pitch, "start": 0.0, "end": 0.5, "velocity": 80, "confidence": conf}


class ConfidenceFloorTests(unittest.TestCase):
    def test_drops_below_floor_keeps_at_and_above(self):
        notes = [_note(60, 0.01), _note(62, MIN_NOTE_CONFIDENCE - 0.001), _note(64, MIN_NOTE_CONFIDENCE), _note(65, 0.9)]
        self.assertEqual([n["pitch"] for n in drop_low_confidence(notes)], [64, 65])

    def test_unknown_confidence_is_kept(self):
        self.assertEqual(len(drop_low_confidence([_note(60, None)])), 1)

    def test_input_list_is_not_modified(self):
        notes = [_note(60, 0.01), _note(62, 0.9)]
        drop_low_confidence(notes)
        self.assertEqual(len(notes), 2)

    def test_empty(self):
        self.assertEqual(drop_low_confidence([]), [])


def _fake_f0(segments, total_s=3.0, sr=synth.SR):
    """segments = [(midi, start_s, dur_s, voiced_prob)] -> a compute_f0 stand-in."""

    def fake(y, sr_, hop=HOP):
        n = 1 + len(y) // hop
        times = np.arange(n) * hop / sr_
        f0 = np.full(n, np.nan)
        prob = np.full(n, 0.0)
        for midi, start, dur, p in segments:
            sel = (times >= start) & (times < start + dur)
            f0[sel] = synth.midi_to_hz(midi)
            prob[sel] = p
        return times, f0, prob

    return fake


class ExtractNotesTests(unittest.TestCase):
    Y = np.zeros(int(3.0 * synth.SR), dtype=np.float32)

    def _extract(self, segments):
        with mock.patch.object(pitch_mod, "compute_f0", _fake_f0(segments)):
            return extract_notes(self.Y, synth.SR)

    def test_junk_note_in_a_pause_is_removed(self):
        # a real note, then a 0.01-probability "note" at the 65 Hz floor (as seen in hum_04_pauses)
        notes, _ = self._extract([(60, 0.2, 0.6, 0.9), (36, 1.5, 0.3, 0.01)])
        self.assertEqual([n["pitch"] for n in notes], [60])

    def test_no_note_below_the_floor_is_returned(self):
        notes, _ = self._extract([(60, 0.2, 0.5, 0.9), (64, 1.0, 0.5, 0.05), (67, 1.8, 0.5, 0.8)])
        self.assertTrue(all(n["confidence"] >= MIN_NOTE_CONFIDENCE for n in notes))
        self.assertEqual([n["pitch"] for n in notes], [60, 67])

    def test_warning_uses_all_detected_notes_not_just_the_survivors(self):
        # one good note and two junk notes: the survivor alone has confidence 0.9,
        # but the recording as a whole was uncertain and must still be flagged
        notes, warns = self._extract([(60, 0.2, 0.6, 0.9), (36, 1.2, 0.3, 0.01), (36, 2.0, 0.3, 0.01)])
        self.assertEqual(len(notes), 1)
        self.assertIn("low_pitch_confidence", [w["code"] for w in warns])

    def test_clean_recording_has_no_warning(self):
        _, warns = self._extract([(60, 0.2, 0.6, 0.9), (64, 1.2, 0.6, 0.85)])
        self.assertEqual(warns, [])

    def test_only_junk_raises_no_melody(self):
        with self.assertRaises(PipelineError) as cm:
            self._extract([(36, 0.5, 0.4, 0.01)])
        self.assertEqual(cm.exception.code, "validation_error")

    def test_all_unvoiced_raises_no_melody(self):
        with self.assertRaises(PipelineError):
            self._extract([])


if __name__ == "__main__":
    unittest.main()
