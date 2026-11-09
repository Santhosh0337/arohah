import unittest
from unittest import mock

from app.pipeline import PipelineError
from app.pipeline import key_bpm as key_bpm_mod
from app.pipeline.key_bpm import (KEY_LOW_CONFIDENCE, bpm_from_onsets, detect_bpm, detect_key, fold_bpm,
                                  key_warnings)


def n(pitch, start, dur):
    return {"pitch": pitch, "start": start, "end": start + dur, "velocity": 80, "confidence": 0.9}


def melody(pitches, dur=0.5):
    return [n(p, i * dur, dur) for i, p in enumerate(pitches)]


C_MAJOR = [60, 62, 64, 60, 64, 67, 65, 64, 62, 60, 67, 60, 72, 67, 64, 60]
A_MINOR = [69, 71, 72, 69, 64, 72, 71, 69, 68, 69, 64, 69, 76, 72, 69, 69, 64, 69]


class KeyTests(unittest.TestCase):
    def test_c_major(self):
        k = detect_key(melody(C_MAJOR))
        self.assertEqual((k["tonic"], k["mode"]), ("C", "major"))
        self.assertTrue(0 <= k["confidence"] <= 1)

    def test_transposed_to_d_major(self):
        k = detect_key(melody([p + 2 for p in C_MAJOR]))
        self.assertEqual((k["tonic"], k["mode"]), ("D", "major"))

    def test_a_minor(self):
        k = detect_key(melody(A_MINOR))
        self.assertEqual((k["tonic"], k["mode"]), ("A", "minor"))

    def test_octave_does_not_matter(self):
        k = detect_key(melody([p + 12 for p in C_MAJOR]))
        self.assertEqual((k["tonic"], k["mode"]), ("C", "major"))

    def test_duration_weighting(self):
        # Many short chromatic notes, but long C-E-G tones dominate.
        notes = [n(60, 0, 3), n(64, 3, 2), n(67, 5, 2)] + [n(61, 7 + i * 0.1, 0.05) for i in range(10)]
        self.assertEqual(detect_key(notes)["tonic"], "C")

    def test_empty_raises(self):
        with self.assertRaises(PipelineError):
            detect_key([])

    def test_single_note_does_not_crash(self):
        k = detect_key([n(60, 0, 1)])
        self.assertIn(k["mode"], ("major", "minor"))


def onsets_at(bpm, pattern):
    """pattern in beats between onsets, e.g. [1, 1, 0.5, 0.5, 2]."""
    beat, t, out = 60.0 / bpm, 0.0, []
    for _ in range(3):
        for p in pattern:
            out.append(t)
            t += p * beat
    out.append(t)
    return out


class BpmTests(unittest.TestCase):
    def test_fold(self):
        self.assertEqual(fold_bpm(200), 100)
        self.assertEqual(fold_bpm(40), 80)
        self.assertEqual(fold_bpm(120), 120)
        self.assertEqual(fold_bpm(161), 80.5)
        with self.assertRaises(ValueError):
            fold_bpm(0)

    def test_onsets_recover_tempo(self):
        for bpm in (72, 80, 90, 100, 110, 120):
            est = bpm_from_onsets(onsets_at(bpm, [1, 1, 0.5, 0.5, 2, 1, 1]))
            self.assertIsNotNone(est)
            self.assertAlmostEqual(est, bpm, delta=3, msg=f"true {bpm} got {est}")

    def test_octave_ambiguity_picks_a_related_tempo(self):
        # 140 and 70 are indistinguishable from onsets alone; either is acceptable.
        for true in (66, 140):
            est = bpm_from_onsets(onsets_at(true, [1, 1, 0.5, 0.5, 2, 1, 1]))
            related = (true, true * 2 if true < 80 else true / 2)
            self.assertTrue(any(abs(est - r) < 4 for r in related), (true, est))

    def test_onsets_too_few(self):
        self.assertIsNone(bpm_from_onsets([0.0, 0.5]))

    def test_user_override_wins(self):
        info, warns = detect_bpm(None, 22050, melody(C_MAJOR), override=87)
        self.assertEqual((info["bpm"], info["bpm_source"]), (87.0, "user"))
        self.assertEqual(warns, [])

    def test_override_out_of_range(self):
        with self.assertRaises(PipelineError):
            detect_bpm(None, 22050, [], override=5)

    def test_falls_back_to_note_onsets_without_audio(self):
        notes = [n(60, t, 0.2) for t in onsets_at(100, [1, 1, 0.5, 0.5, 2, 1, 1])]
        info, warns = detect_bpm(None, 22050, notes)
        self.assertEqual((info["bpm_source"], info["method"]), ("auto", "note_onsets"))
        self.assertAlmostEqual(info["bpm"], 100, delta=3)

    def test_default_is_flagged(self):
        info, warns = detect_bpm(None, 22050, [n(60, 0, 1)])
        self.assertEqual(info["method"], "default")
        self.assertEqual(warns[0]["code"], "bpm_low_confidence")


class KeyWarningTests(unittest.TestCase):
    def test_weak_key_warns_and_names_the_key(self):
        w = key_warnings({"tonic": "G", "mode": "major", "confidence": 0.19})
        self.assertEqual([x["code"] for x in w], ["low_key_confidence"])
        self.assertEqual(w[0]["stage"], "key_bpm")
        self.assertIn("G major", w[0]["message"])

    def test_threshold_is_exclusive(self):
        self.assertEqual(key_warnings({"tonic": "C", "mode": "major", "confidence": KEY_LOW_CONFIDENCE}), [])
        self.assertEqual(key_warnings({"tonic": "C", "mode": "major", "confidence": 0.9}), [])

    def test_warning_does_not_change_the_key(self):
        key = {"tonic": "G", "mode": "major", "confidence": 0.19}
        key_warnings(key)
        self.assertEqual(key, {"tonic": "G", "mode": "major", "confidence": 0.19})


class BpmCrossCheckTests(unittest.TestCase):
    NOTES = [n(60, t, 0.2) for t in onsets_at(100, [1, 1, 0.5, 0.5, 2, 1, 1])]

    def _detect(self, beat_tempo, **kw):
        with mock.patch.object(key_bpm_mod, "_beat_track_tempo", return_value=beat_tempo):
            return detect_bpm(None, 22050, self.NOTES, **kw)

    def test_agreement_gives_no_warning(self):
        info, warns = self._detect(105.0)
        self.assertEqual((info["bpm"], info["method"]), (105.0, "beat_track"))
        self.assertEqual(warns, [])

    def test_disagreement_warns_but_keeps_the_beat_tracker_value(self):
        info, warns = self._detect(152.0)
        self.assertEqual((info["bpm"], info["bpm_source"]), (152.0, "auto"))
        self.assertEqual([w["code"] for w in warns], ["bpm_low_confidence"])
        self.assertIn("152", warns[0]["message"])

    def test_half_time_estimate_is_flagged(self):
        info, warns = self._detect(50.0)  # folded to 100: agrees, so no warning
        self.assertEqual(info["bpm"], 100.0)
        self.assertEqual(warns, [])
        info, warns = self._detect(62.0)  # 62 vs ~100: disagrees
        self.assertEqual(info["bpm"], 62.0)
        self.assertEqual(len(warns), 1)

    def test_user_override_never_warns_and_skips_beat_tracking(self):
        with mock.patch.object(key_bpm_mod, "_beat_track_tempo") as bt:
            info, warns = detect_bpm(None, 22050, self.NOTES, override=152)
        bt.assert_not_called()
        self.assertEqual((info["bpm"], info["bpm_source"], warns), (152.0, "user", []))

    def test_too_few_notes_for_a_cross_check_gives_no_warning(self):
        with mock.patch.object(key_bpm_mod, "_beat_track_tempo", return_value=152.0):
            info, warns = detect_bpm(None, 22050, [n(60, 0, 1)])
        self.assertEqual((info["bpm"], warns), (152.0, []))


class TempoTrustTests(unittest.TestCase):
    """`trusted` only decides whether the tempo may be used for explicit quantising. It never
    changes the BPM or the warnings."""

    NOTES = BpmCrossCheckTests.NOTES

    def _detect(self, beat_tempo, notes=None, **kw):
        with mock.patch.object(key_bpm_mod, "_beat_track_tempo", return_value=beat_tempo):
            return detect_bpm(None, 22050, self.NOTES if notes is None else notes, **kw)

    def test_a_bpm_the_user_set_is_trusted(self):
        info, _ = self._detect(152.0, override=90)
        self.assertTrue(info["trusted"])

    def test_beat_tracking_that_agrees_with_the_note_timing_is_trusted(self):
        info, warns = self._detect(105.0)
        self.assertTrue(info["trusted"])
        self.assertEqual(warns, [])

    def test_estimates_that_disagree_are_not_trusted(self):
        info, warns = self._detect(152.0)
        self.assertFalse(info["trusted"])
        self.assertEqual(len(warns), 1)
        self.assertEqual(info["bpm"], 152.0)  # the BPM itself is unchanged

    def test_beat_tracking_with_nothing_to_cross_check_against_is_not_trusted(self):
        info, warns = self._detect(105.0, notes=[n(60, 0, 1)])
        self.assertFalse(info["trusted"])
        self.assertEqual(warns, [])

    def test_the_onset_fallback_and_the_placeholder_are_not_trusted(self):
        notes = [n(60, t, 0.2) for t in onsets_at(100, [1, 1, 0.5, 0.5, 2, 1, 1])]
        info, _ = detect_bpm(None, 22050, notes)
        self.assertEqual(info["method"], "note_onsets")
        self.assertFalse(info["trusted"])
        info, _ = detect_bpm(None, 22050, [n(60, 0, 1)])
        self.assertEqual(info["method"], "default")
        self.assertFalse(info["trusted"])

    def test_existing_keys_are_unchanged(self):
        info, _ = self._detect(105.0)
        self.assertEqual(set(info), {"bpm", "bpm_source", "method", "trusted"})


if __name__ == "__main__":
    unittest.main()
