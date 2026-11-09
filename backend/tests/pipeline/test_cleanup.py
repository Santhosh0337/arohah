import copy
import unittest

from app.pipeline.cleanup import (
    GRID_MIN_ONSETS,
    SNAP_MIN_KEY_CONFIDENCE,
    Q_BAD_TEMPO,
    Q_COLLISION,
    Q_NO_GRID,
    Q_TEMPO_NOT_TRUSTED,
    Q_TOO_FEW_NOTES,
    clean_notes,
    cleanup_notes,
    fix_octave_jumps,
    grid_evidence,
    merge_touching,
    nearest_in_scale,
    scale_candidates,
    scale_pitch_classes,
    snap_pitches,
)


def n(pitch, start, end, conf=0.9, vel=80):
    return {"pitch": pitch, "start": start, "end": end, "velocity": vel, "confidence": conf}


C_MAJOR = scale_pitch_classes("C", "major")
STEP = 0.125  # 120 BPM, 1/16 grid


def gridded_melody(steps=(0, 2, 3, 5, 8, 9, 12, 14, 16, 17, 20, 22), jitter=(0.004, -0.006, 0.0, 0.005, -0.003, 0.002)):
    """A rhythmic part: onsets on a 120 BPM 1/16 grid with a few ms of human jitter, notes
    0.8 of a step long (they never touch or overlap), alternating pitches."""
    out = []
    for i, s in enumerate(steps):
        t = s * STEP + jitter[i % len(jitter)] + 0.5
        out.append(n(60 + (i % 4) * 2, round(t, 4), round(t + 0.8 * STEP, 4)))
    return out


# ----------------------------------------------------------------------------- scale
class ScaleTests(unittest.TestCase):
    def test_scale_pcs(self):
        self.assertEqual(C_MAJOR, [0, 2, 4, 5, 7, 9, 11])
        self.assertEqual(scale_pitch_classes("A", "minor"), [0, 2, 4, 5, 7, 9, 11])
        self.assertEqual(scale_pitch_classes("D", "major"), [1, 2, 4, 6, 7, 9, 11])

    def test_candidates(self):
        self.assertEqual(scale_candidates(60, C_MAJOR), [60])
        self.assertEqual(scale_candidates(61, C_MAJOR), [60, 62])  # exactly between two scale pitches
        self.assertEqual(scale_candidates(63, C_MAJOR), [62, 64])
        self.assertEqual(scale_candidates(66, C_MAJOR), [65, 67])
        self.assertEqual(scale_candidates(61, [0, 2, 4, 7, 9]), [60, 62])  # pentatonic
        self.assertEqual(scale_candidates(65, [0, 2, 4, 7, 9]), [64])  # only one pitch is nearest

    def test_every_out_of_scale_pitch_of_a_seven_note_scale_is_a_tie(self):
        # why the old "ties go downward" rule was the whole of the old snapping behaviour
        for tonic in ("C", "D", "F#", "A#"):
            for mode in ("major", "minor"):
                pcs = scale_pitch_classes(tonic, mode)
                for p in range(48, 84):
                    if p % 12 not in pcs:
                        self.assertEqual(len(scale_candidates(p, pcs)), 2, (tonic, mode, p))

    def test_nearest_does_not_default_downward(self):
        self.assertEqual(nearest_in_scale(60, C_MAJOR), 60)
        self.assertEqual(nearest_in_scale(61, C_MAJOR), 61)  # a tie: no decision, pitch kept
        self.assertEqual(nearest_in_scale(63, C_MAJOR), 63)
        self.assertEqual(nearest_in_scale(61, C_MAJOR, prefer=62), 62)  # caller can decide: up ...
        self.assertEqual(nearest_in_scale(61, C_MAJOR, prefer=60), 60)  # ... or down
        self.assertEqual(nearest_in_scale(61, C_MAJOR, prefer=65), 61)  # a preference outside the tie is ignored


# ----------------------------------------------------------------------------- octave
class OctaveTests(unittest.TestCase):
    def test_isolated_jump_fixed(self):
        self.assertEqual(fix_octave_jumps([60, 62, 74, 64, 60]), [60, 62, 62, 64, 60])

    def test_low_jump_fixed(self):
        self.assertEqual(fix_octave_jumps([67, 65, 52, 64]), [67, 65, 64, 64])

    def test_real_leap_kept_when_followed(self):
        # a leap that the next note follows is a real register change
        self.assertEqual(fix_octave_jumps([60, 62, 74, 76, 74]), [60, 62, 74, 76, 74])

    def test_endpoints(self):
        self.assertEqual(fix_octave_jumps([48, 60, 62]), [60, 60, 62])
        self.assertEqual(fix_octave_jumps([60, 62, 76]), [60, 62, 64])

    def test_short_inputs(self):
        self.assertEqual(fix_octave_jumps([]), [])
        self.assertEqual(fix_octave_jumps([60]), [60])

    def test_nine_semitones_is_not_a_jump_ten_is(self):
        self.assertEqual(fix_octave_jumps([60, 62, 71, 62, 60]), [60, 62, 71, 62, 60])
        self.assertEqual(fix_octave_jumps([60, 62, 72, 62, 60]), [60, 62, 60, 62, 60])

    def test_first_and_last_note_use_their_single_neighbour(self):
        # Existing behaviour, kept: a leap of more than 9 semitones at the very start or end of
        # the melody is treated as an octave error, so a real 10-semitone opening leap is moved.
        self.assertEqual(fix_octave_jumps([60, 70, 70]), [72, 70, 70])

    def test_cleanup_applies_it_and_leaves_the_raw_notes_alone(self):
        raw = [n(60, 0.0, 0.4), n(62, 0.5, 0.9), n(74, 1.0, 1.4), n(64, 1.5, 1.9), n(60, 2.0, 2.4)]
        before = copy.deepcopy(raw)
        out = cleanup_notes(raw, 120, None, snap_to_scale=False)
        self.assertEqual([x["pitch"] for x in out], [60, 62, 62, 64, 60])
        self.assertEqual(raw, before)

    def test_cleanup_off_means_no_octave_fix(self):
        raw = [n(60, 0.0, 0.4), n(62, 0.5, 0.9), n(74, 1.0, 1.4), n(64, 1.5, 1.9), n(60, 2.0, 2.4)]
        out = cleanup_notes(raw, 120, None, cleanup=False, snap_to_scale=False)
        self.assertEqual([x["pitch"] for x in out], [60, 62, 74, 64, 60])


# ----------------------------------------------------------------------------- merging
class MergeTests(unittest.TestCase):
    def test_touching_same_pitch_notes_merge(self):
        out = cleanup_notes([n(60, 0.0, 0.5, 0.8), n(60, 0.5, 1.0, 0.6)], 120, None, snap_to_scale=False)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["start"], out[0]["end"]), (0.0, 1.0))
        self.assertAlmostEqual(out[0]["confidence"], 0.7)  # duration-weighted

    def test_merge_keeps_the_louder_velocity(self):
        out = merge_touching([n(60, 0.0, 0.5, vel=70), n(60, 0.5, 1.0, vel=90)])
        self.assertEqual(out[0]["velocity"], 90)

    def test_edges_within_the_time_rounding_still_touch(self):
        # note times are rounded to 0.1 ms, so edges 0.1 ms apart are the same instant
        out = merge_touching([n(60, 0.0, 0.4999), n(60, 0.5, 1.0)])
        self.assertEqual(len(out), 1)

    def test_a_real_gap_is_never_merged_however_small(self):
        for gap in (0.0005, 0.005, 0.02, 0.07, 0.128, 0.4):
            with self.subTest(gap=gap):
                out = cleanup_notes([n(60, 0.0, 0.5), n(60, 0.5 + gap, 1.0 + gap)], 120, None, snap_to_scale=False)
                self.assertEqual(len(out), 2)
                self.assertAlmostEqual(out[1]["start"] - out[0]["end"], gap, places=6)

    def test_rearticulation_with_a_gap_survives_a_whole_phrase(self):
        raw = [n(60, 0.0, 0.3), n(60, 0.35, 0.6), n(62, 0.6, 0.9), n(60, 0.95, 1.2)]
        out = cleanup_notes(raw, 120, C_MAJOR, key_confidence=0.9)
        self.assertEqual([(x["pitch"], x["start"], x["end"]) for x in out], [(p["pitch"], p["start"], p["end"]) for p in raw])

    def test_notes_equal_only_after_snapping_are_not_merged(self):
        # raw 60 and 61 touch; snapping 61 to 60 would make them equal. They must stay two notes.
        raw = [n(60, 0.0, 0.5), n(61, 0.5, 1.0)]
        out = cleanup_notes(raw, 120, C_MAJOR, key_confidence=0.95)
        self.assertEqual(len(out), 2)
        self.assertNotEqual(out[0]["pitch"], out[1]["pitch"])

    def test_notes_equal_only_after_octave_correction_are_not_merged(self):
        # 75 is an octave error (63 raw would be right); once fixed it equals the touching 63 before it
        raw = [n(62, 0.0, 0.5), n(63, 0.5, 1.0), n(75, 1.0, 1.5), n(64, 1.5, 2.0), n(62, 2.0, 2.5)]
        out = cleanup_notes(raw, 120, None, snap_to_scale=False)
        self.assertEqual([x["pitch"] for x in out], [62, 63, 63, 64, 62])  # fixed, but still five notes

    def test_merge_decision_uses_raw_timing_not_quantised_timing(self):
        # 70 ms and 128 ms gaps are the ones that old quantising turned into "touching"
        raw = [n(60, 0.0, 0.3), n(60, 0.37, 0.6), n(60, 0.728, 0.9)]
        self.assertEqual(len(cleanup_notes(raw, 69.8, None, snap_to_scale=False)), 3)


# ----------------------------------------------------------------------------- snapping
class SnapTests(unittest.TestCase):
    RAW = [n(64, 0.0, 0.4), n(61, 0.5, 0.9), n(67, 1.0, 1.4)]  # 61 has both neighbours above

    def test_threshold_value(self):
        self.assertEqual(SNAP_MIN_KEY_CONFIDENCE, 0.70)

    def test_below_threshold_skips_snapping_and_says_so(self):
        for conf in (0.0, 0.37, 0.699):
            with self.subTest(conf=conf):
                out, rep = clean_notes(self.RAW, 120, C_MAJOR, key_confidence=conf)
                self.assertEqual([x["pitch"] for x in out], [64, 61, 67])
                self.assertEqual(rep.snap_skipped_reason, "low_key_confidence")
                self.assertEqual(rep.snapped, 0)

    def test_at_and_above_threshold_snapping_is_allowed(self):
        for conf in (0.70, 0.85, 1.0):
            with self.subTest(conf=conf):
                out, rep = clean_notes(self.RAW, 120, C_MAJOR, key_confidence=conf)
                self.assertEqual([x["pitch"] for x in out], [64, 62, 67])
                self.assertIsNone(rep.snap_skipped_reason)
                self.assertEqual(rep.snapped, 1)

    def test_unknown_key_confidence_does_not_allow_snapping(self):
        out, rep = clean_notes(self.RAW, 120, C_MAJOR)
        self.assertEqual([x["pitch"] for x in out], [64, 61, 67])
        self.assertEqual(rep.snap_skipped_reason, "unknown_key_confidence")

    def test_switch_off_is_not_reported_as_a_confidence_skip(self):
        out, rep = clean_notes(self.RAW, 120, C_MAJOR, snap_to_scale=False, key_confidence=0.9)
        self.assertEqual([x["pitch"] for x in out], [64, 61, 67])
        self.assertIsNone(rep.snap_skipped_reason)

    def test_ties_are_not_resolved_downward(self):
        up, _, _ = snap_pitches([64, 61, 67], C_MAJOR)  # neighbours above: moves up
        down, _, _ = snap_pitches([55, 61, 57], C_MAJOR)  # neighbours below: moves down
        self.assertEqual(up[1], 62)
        self.assertEqual(down[1], 60)

    def test_an_undecidable_note_keeps_its_pitch(self):
        out, moved, left = snap_pitches([60, 61, 64], C_MAJOR)  # one neighbour each side
        self.assertEqual(out, [60, 61, 64])
        self.assertEqual((moved, left), (0, 1))
        self.assertEqual(snap_pitches([61], C_MAJOR)[0], [61])  # no neighbours at all

    def test_snapping_cannot_collapse_neighbouring_distinct_pitches(self):
        # 61 would snap to 62 (its neighbour) and merge into it: both keep their pitch
        out, moved, _ = snap_pitches([62, 61], C_MAJOR)
        self.assertEqual(out, [62, 61])
        self.assertEqual(moved, 0)
        # a lower neighbour ornament between two equal pitches
        self.assertEqual(snap_pitches([62, 61, 62], C_MAJOR)[0], [62, 61, 62])
        # a chain: undoing one pair must not leave another collapsed
        out, _, _ = snap_pitches([62, 61, 60], C_MAJOR)
        for a, b in zip(out, out[1:]):
            self.assertNotEqual(a, b)

    def test_in_scale_notes_never_move(self):
        raw = [60, 62, 64, 65, 67, 69, 71, 72]
        self.assertEqual(snap_pitches(raw, C_MAJOR)[0], raw)

    def test_a_moved_note_moves_by_one_semitone_at_most_in_a_seven_note_scale(self):
        import random

        rng = random.Random(7)
        for _ in range(200):
            raw = [rng.randint(55, 79) for _ in range(rng.randint(1, 12))]
            out, _, _ = snap_pitches(raw, C_MAJOR)
            for a, b in zip(raw, out):
                self.assertLessEqual(abs(a - b), 1)
            for a, b, c, d in zip(raw, raw[1:], out, out[1:]):
                if a != b:
                    self.assertNotEqual(c, d)

    def test_original_pitches_stay_available_in_the_raw_notes(self):
        raw = copy.deepcopy(self.RAW)
        out, _ = clean_notes(raw, 120, C_MAJOR, key_confidence=0.9)
        self.assertEqual(raw, self.RAW)  # the raw list still holds 61
        self.assertEqual(raw[1]["pitch"], 61)
        self.assertEqual(out[1]["pitch"], 62)
        self.assertIsNot(out[1], raw[1])

    def test_snapping_does_not_touch_timing(self):
        out, _ = clean_notes(self.RAW, 120, C_MAJOR, key_confidence=0.9)
        self.assertEqual([(x["start"], x["end"]) for x in out], [(r["start"], r["end"]) for r in self.RAW])


# ----------------------------------------------------------------------------- quantising
class QuantiseTests(unittest.TestCase):
    def test_default_leaves_every_onset_and_end_unchanged(self):
        raw = gridded_melody()
        out = cleanup_notes(raw, 120, C_MAJOR, key_confidence=0.9, tempo_trusted=True)
        self.assertEqual([(x["start"], x["end"]) for x in out], [(r["start"], r["end"]) for r in raw])

    def test_default_leaves_free_form_timing_unchanged(self):
        raw = [n(60, 0.07, 0.31), n(62, 0.34, 0.80), n(64, 0.83, 1.4), n(65, 1.45, 1.51)]
        out = cleanup_notes(raw, 100, C_MAJOR, key_confidence=0.9)
        self.assertEqual([(x["start"], x["end"]) for x in out], [(r["start"], r["end"]) for r in raw])

    def test_explicit_quantise_with_trusted_tempo_and_a_real_grid_moves_onsets_to_the_grid(self):
        raw = gridded_melody()
        out, rep = clean_notes(raw, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=True)
        self.assertTrue(rep.quantised)
        self.assertIsNone(rep.quantise_skipped_reason)
        phase = grid_evidence([x["start"] for x in raw], STEP)["phase_s"]
        for r, q in zip(raw, out):
            k = (q["start"] - phase) / STEP
            self.assertAlmostEqual(k, round(k), places=2)  # on the fitted grid
            self.assertLessEqual(abs(q["start"] - r["start"]), STEP / 2 + 1e-9)  # moved by under half a step

    def test_explicit_quantise_keeps_count_order_pitches_and_lengths(self):
        raw = gridded_melody()
        out, rep = clean_notes(raw, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=True)
        self.assertTrue(rep.quantised)
        self.assertEqual(len(out), len(raw))
        self.assertEqual([x["pitch"] for x in out], [r["pitch"] for r in raw])
        self.assertEqual(sorted(x["start"] for x in out), [x["start"] for x in out])
        for r, q in zip(raw, out):
            self.assertAlmostEqual(q["end"] - q["start"], r["end"] - r["start"], places=3)

    def test_quantised_notes_never_overlap(self):
        raw = gridded_melody()
        out, _ = clean_notes(raw, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=True)
        for a, b in zip(out, out[1:]):
            self.assertLessEqual(a["end"], b["start"] + 1e-9)

    def test_a_grid_collision_deletes_nothing_and_changes_nothing(self):
        raw = gridded_melody()
        # an extra note 20 ms after another one: both would land on the same grid position
        extra = n(71, raw[4]["start"] + 0.02, raw[4]["start"] + 0.03)
        crowded = sorted(raw + [extra], key=lambda x: x["start"])
        out, rep = clean_notes(crowded, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=True)
        self.assertFalse(rep.quantised)
        self.assertEqual(rep.quantise_skipped_reason, Q_COLLISION)
        self.assertEqual(out, crowded)  # same notes, same timing
        self.assertEqual(len(out), len(raw) + 1)

    def test_distinct_pitch_transitions_survive(self):
        # legato notes (end == next start) with different pitches, on a grid
        raw = []
        for i, s in enumerate((0, 1, 2, 4, 5, 6, 8, 9, 10, 12)):
            t = 0.5 + s * STEP + (0.003 if i % 2 else -0.003)
            raw.append(n(60 + (i % 3) * 2, round(t, 4), round(t + STEP, 4)))
        out, rep = clean_notes(raw, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=True)
        self.assertEqual([x["pitch"] for x in out], [r["pitch"] for r in raw])
        self.assertEqual(len(out), len(raw))

    def test_untrusted_tempo_leaves_real_timing_alone_even_on_a_perfect_grid(self):
        raw = [n(60 + i, 0.5 + s * STEP, 0.5 + s * STEP + 0.1) for i, s in enumerate(range(0, 24, 2))]
        out, rep = clean_notes(raw, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=False)
        self.assertEqual(rep.quantise_skipped_reason, Q_TEMPO_NOT_TRUSTED)
        self.assertEqual(out, raw)
        self.assertIn("not trusted", rep.quantise_skipped_text())

    def test_free_form_onsets_are_not_quantised_even_with_a_trusted_tempo(self):
        starts = [0.0, 0.41, 0.93, 1.12, 1.9, 2.37, 2.6, 3.31, 3.77, 4.2, 4.95, 5.4]
        raw = [n(60 + i % 5, s, s + 0.3) for i, s in enumerate(starts)]
        out, rep = clean_notes(raw, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=True)
        self.assertEqual(rep.quantise_skipped_reason, Q_NO_GRID)
        self.assertEqual(out, raw)

    def test_too_few_notes_are_not_quantised(self):
        raw = gridded_melody()[: GRID_MIN_ONSETS - 1]
        out, rep = clean_notes(raw, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=True)
        self.assertEqual(rep.quantise_skipped_reason, Q_TOO_FEW_NOTES)
        self.assertEqual(out, raw)

    def test_a_bad_tempo_is_reported_not_raised(self):
        for bpm in (0, -3, float("nan"), None):
            with self.subTest(bpm=bpm):
                out, rep = clean_notes(gridded_melody(), bpm, None, snap_to_scale=False, quantize=True, tempo_trusted=True)
                self.assertEqual(rep.quantise_skipped_reason, Q_BAD_TEMPO)
                self.assertEqual(out, gridded_melody())

    def test_skipped_quantising_returns_independent_copies(self):
        raw = gridded_melody()
        out, _ = clean_notes(raw, 120, None, snap_to_scale=False, quantize=True, tempo_trusted=False)
        out[0]["pitch"] = 1
        self.assertNotEqual(raw[0]["pitch"], 1)

    def test_not_requested_is_not_reported_as_skipped(self):
        _, rep = clean_notes(gridded_melody(), 120, None, snap_to_scale=False)
        self.assertFalse(rep.quantise_requested)
        self.assertFalse(rep.quantised)


class GridEvidenceTests(unittest.TestCase):
    def test_metronomic_onsets_score_high_and_unrelated_ones_low(self):
        on_grid = [0.5 + k * STEP for k in (0, 2, 3, 5, 8, 9, 12, 14, 16, 17, 20, 22)]
        self.assertGreater(grid_evidence(on_grid, STEP)["resultant"], 0.99)
        free = [0.0, 0.41, 0.93, 1.12, 1.9, 2.37, 2.6, 3.31, 3.77, 4.2, 4.95, 5.4]
        self.assertLess(grid_evidence(free, STEP)["resultant"], 0.5)

    def test_a_constant_offset_from_t0_is_still_a_grid(self):
        shifted = [0.043 + k * STEP for k in (0, 1, 3, 4, 6, 9, 10, 13, 15)]
        ev = grid_evidence(shifted, STEP)
        self.assertGreater(ev["resultant"], 0.99)
        self.assertAlmostEqual(ev["phase_s"], 0.043, places=3)

    def test_degenerate_input(self):
        self.assertEqual(grid_evidence([], STEP)["resultant"], 0.0)
        self.assertEqual(grid_evidence([1.0, 2.0], 0)["resultant"], 0.0)


# ----------------------------------------------------------------------------- whole function
class CleanupTests(unittest.TestCase):
    def test_raw_is_untouched(self):
        raw = [n(61, 0.03, 0.52), n(64, 0.55, 1.0)]
        before = copy.deepcopy(raw)
        cleanup_notes(raw, 120, C_MAJOR, key_confidence=0.9)
        clean_notes(raw, 120, C_MAJOR, key_confidence=0.9, quantize=True, tempo_trusted=True)
        self.assertEqual(raw, before)

    def test_no_note_is_ever_deleted_without_merging(self):
        raw = [n(60 + i % 7, i * 0.3, i * 0.3 + 0.1 + (i % 3) * 0.05) for i in range(30)]
        for kw in ({}, {"key_confidence": 0.9}, {"key_confidence": 0.9, "quantize": True, "tempo_trusted": True}):
            with self.subTest(kw=kw):
                self.assertEqual(len(cleanup_notes(raw, 100, C_MAJOR, **kw)), len(raw))

    def test_tiny_note_keeps_its_length(self):
        out = cleanup_notes([n(60, 0.0, 0.01)], 120, C_MAJOR, key_confidence=0.9)
        self.assertAlmostEqual(out[0]["end"] - out[0]["start"], 0.01)

    def test_input_order_does_not_matter(self):
        a, b = n(60, 0.0, 0.3), n(62, 0.5, 0.8)
        self.assertEqual(cleanup_notes([b, a], 120, None, snap_to_scale=False), cleanup_notes([a, b], 120, None, snap_to_scale=False))

    def test_toggles(self):
        raw = [n(61, 0.03, 0.52), n(64, 0.55, 1.0), n(67, 1.1, 1.5)]
        same = cleanup_notes(raw, 120, C_MAJOR, cleanup=False, snap_to_scale=False, key_confidence=0.9)
        self.assertEqual(same, raw)
        snap_only = cleanup_notes(raw, 120, C_MAJOR, cleanup=False, snap_to_scale=True, key_confidence=0.9)
        self.assertEqual((snap_only[0]["pitch"], snap_only[0]["start"]), (62, 0.03))
        clean_only = cleanup_notes(raw, 120, C_MAJOR, cleanup=True, snap_to_scale=False, key_confidence=0.9)
        self.assertEqual((clean_only[0]["pitch"], clean_only[0]["start"]), (61, 0.03))

    def test_original_call_signature_still_works(self):
        out = cleanup_notes([n(60, 0.0, 0.5)], 120, C_MAJOR)
        self.assertEqual(len(out), 1)
        out = cleanup_notes([n(60, 0.0, 0.5)], 120, C_MAJOR, cleanup=True, snap_to_scale=True, steps_per_beat=2)
        self.assertEqual(len(out), 1)

    def test_report_counts(self):
        raw = [n(60, 0.0, 0.5), n(60, 0.5, 1.0), n(62, 1.1, 1.5), n(74, 1.6, 2.0), n(64, 2.1, 2.5), n(62, 2.6, 3.0)]
        out, rep = clean_notes(raw, 120, C_MAJOR, key_confidence=0.9)
        self.assertEqual(len(out), 5)
        self.assertEqual(rep.merged, 1)
        self.assertEqual(rep.octave_fixed, 1)

    def test_empty(self):
        self.assertEqual(cleanup_notes([], 120, C_MAJOR), [])
        out, rep = clean_notes([], 120, C_MAJOR, quantize=True)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
