import os
import shutil
import tempfile
import unittest
from unittest import mock

import synth
from app.pipeline import PipelineError
from app.pipeline import pitch as pitch_mod
from app.pipeline import run as run_mod
from app.pipeline.run import align_lyrics, run_lyrics_stage, run_pipeline

SCHEDULE = [(60, 0.5), (62, 0.5), (64, 0.5), (60, 0.5), (64, 0.5), (67, 0.5), (65, 0.5), (64, 0.5),
            (62, 0.5), (60, 0.5), (67, 0.5), (60, 0.5)]


def fake_compute_f0(y, sr, hop=256):
    """Stand-in for librosa.pyin: an ideal f0 track for SCHEDULE, starting where
    the (real, ffmpeg-decoded, trimmed) audio first becomes loud."""
    import numpy as np

    n = 1 + len(y) // hop
    times = np.arange(n) * hop / sr
    loud = np.nonzero(np.abs(y) > 0.02)[0]
    return synth.f0_track(SCHEDULE, len(y) / sr, loud[0] / sr, hop=hop, sr=sr)[0:3] if len(loud) else (times, np.full(n, np.nan), np.zeros(n))


class FakeSTT:
    def __init__(self, text="चाँद", words=None):
        self.text, self.words, self.calls = text, words, []

    def transcribe(self, wav_path, language, mixed_language=False):
        self.calls.append((wav_path, language, mixed_language))
        return {"text": self.text, "words": self.words if self.words is not None else [], "language": language, "raw": {}}


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.wav = os.path.join(self.tmp, "hum.wav")
        synth.write_wav(self.wav, synth.make_hum(SCHEDULE, lead=0.5, tail=0.5))
        p = mock.patch.object(pitch_mod, "compute_f0", fake_compute_f0)
        p.start()
        self.addCleanup(p.stop)

    def _run(self, **kw):
        res = run_pipeline(self.wav, workdir=os.path.join(self.tmp, "w"), **kw)
        return res

    def test_hum_end_to_end(self):
        events = []
        res = self._run(mode="hum", on_progress=lambda s, st, allst: events.append((s, st)))
        pl = res["payload"]
        self.assertEqual([n["pitch"] for n in pl["notes_raw"]], [p for p, _ in SCHEDULE])
        self.assertEqual(len(pl["notes_clean"]), len(SCHEDULE))
        self.assertEqual((pl["analysis"]["key"]["tonic"], pl["analysis"]["key"]["mode"]), ("C", "major"))
        self.assertTrue(60 <= pl["analysis"]["bpm"] <= 160)
        self.assertEqual(pl["analysis"]["bpm_source"], "auto")
        self.assertEqual(pl["input"]["mode"], "hum")
        self.assertIsNone(pl["input"]["language"])
        self.assertEqual(pl["lyrics"], [])
        states = {s["name"]: s["state"] for s in res["stages"]}
        self.assertEqual(states, {"ingest": "done", "pitch": "done", "cleanup": "done", "key_bpm": "done",
                                  "scale": "skipped", "lyrics": "skipped", "arrange": "skipped"})
        order = [s for s, st in events if st == "running"]
        self.assertEqual(order, ["ingest", "pitch", "key_bpm", "cleanup"])
        self.assertTrue(os.path.exists(res["files"]["music_wav"]) and os.path.exists(res["files"]["prisma_wav"]))

    def test_payload_is_json_serialisable_utf8(self):
        import json

        res = self._run(mode="sing", language="hi-IN", stt=FakeSTT("चाँद रात"))
        s = json.dumps(res["payload"], ensure_ascii=False)
        self.assertIn("चाँद", s)

    def test_raw_kept_and_cleanup_off_matches_raw(self):
        res = self._run(mode="hum", cleanup=False, snap_to_scale=False)
        pl = res["payload"]
        self.assertEqual(pl["notes_clean"], pl["notes_raw"])

    def test_bpm_override(self):
        pl = self._run(mode="hum", bpm_override=90)["payload"]
        self.assertEqual((pl["analysis"]["bpm"], pl["analysis"]["bpm_source"]), (90.0, "user"))
        # quantising is off by default, so the tempo does not move any note
        self.assertEqual([n["start"] for n in pl["notes_clean"]], [n["start"] for n in pl["notes_raw"]])

    def test_default_run_keeps_the_hummed_timing_and_the_note_count(self):
        pl = self._run(mode="hum")["payload"]
        self.assertEqual(len(pl["notes_clean"]), len(pl["notes_raw"]))
        for raw, clean in zip(pl["notes_raw"], pl["notes_clean"]):
            self.assertEqual((raw["start"], raw["end"]), (clean["start"], clean["end"]))
        self.assertNotIn("quantise_skipped", [w["code"] for w in pl["warnings"]])  # not asked for

    def test_asking_for_quantising_on_free_form_timing_is_refused_and_reported(self):
        # the synthetic hum has no rhythmic grid at 90 BPM; the tempo is trusted (user set it)
        pl = self._run(mode="hum", bpm_override=90, quantize=True)["payload"]
        self.assertEqual([n["start"] for n in pl["notes_clean"]], [n["start"] for n in pl["notes_raw"]])
        skipped = [w for w in pl["warnings"] if w["code"] == "quantise_skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["stage"], "cleanup")
        self.assertIn("grid", skipped[0]["message"])

    def test_quantising_with_an_untrusted_tempo_is_refused_and_reported(self):
        untrusted = ({"bpm": 100.0, "bpm_source": "auto", "method": "default", "trusted": False}, [])
        with mock.patch.object(run_mod, "detect_bpm", return_value=untrusted):
            pl = self._run(mode="hum", quantize=True)["payload"]
        skipped = [w for w in pl["warnings"] if w["code"] == "quantise_skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertIn("not trusted", skipped[0]["message"])
        self.assertEqual([n["start"] for n in pl["notes_clean"]], [n["start"] for n in pl["notes_raw"]])

    def test_weak_key_skips_snapping_keeps_pitches_and_says_so(self):
        weak = {"tonic": "F#", "mode": "major", "confidence": 0.37}  # a wrong, weak key: snapping would move notes
        with mock.patch.object(run_mod, "detect_key", return_value=weak):
            pl = self._run(mode="hum")["payload"]
        self.assertEqual([n["pitch"] for n in pl["notes_clean"]], [n["pitch"] for n in pl["notes_raw"]])
        snap = [w for w in pl["warnings"] if w["code"] == "snap_skipped"]
        self.assertEqual(len(snap), 1)
        self.assertEqual(snap[0]["stage"], "cleanup")
        self.assertIn("0.37", snap[0]["message"])
        self.assertIn("0.70", snap[0]["message"])

    def test_confident_key_may_snap_and_does_not_warn(self):
        strong = {"tonic": "F#", "mode": "major", "confidence": 0.9}
        with mock.patch.object(run_mod, "detect_key", return_value=strong):
            pl = self._run(mode="hum")["payload"]
        self.assertNotIn("snap_skipped", [w["code"] for w in pl["warnings"]])
        for raw, clean in zip(pl["notes_raw"], pl["notes_clean"]):
            self.assertLessEqual(abs(raw["pitch"] - clean["pitch"]), 1)
            self.assertEqual((raw["start"], raw["end"]), (clean["start"], clean["end"]))

    def test_switching_snapping_off_is_not_reported_as_a_skip(self):
        weak = {"tonic": "G", "mode": "major", "confidence": 0.19}
        with mock.patch.object(run_mod, "detect_key", return_value=weak):
            pl = self._run(mode="hum", snap_to_scale=False)["payload"]
        self.assertNotIn("snap_skipped", [w["code"] for w in pl["warnings"]])

    def test_command_line_quantize_flag(self):
        import contextlib
        import io
        import json

        out = os.path.join(self.tmp, "out.json")
        for flags, expect in (([], 0), (["--quantize"], 1)):
            with self.subTest(flags=flags):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = run_mod._main([self.wav, "--bpm", "90", "--json", out, *flags])
                self.assertEqual(code, 0)
                with open(out, encoding="utf-8") as f:
                    codes = [w["code"] for w in json.load(f)["warnings"]]
                self.assertEqual(codes.count("quantise_skipped"), expect)

    def test_sing_calls_stt_with_16k_file(self):
        stt = FakeSTT("one two three")
        res = self._run(mode="sing", language="en-IN", mixed_language=True, stt=stt)
        self.assertEqual(stt.calls[0][0], res["files"]["prisma_wav"])
        self.assertEqual(stt.calls[0][1:], ("en-IN", True))
        self.assertEqual([w["text"] for w in res["payload"]["lyrics"]], ["one", "two", "three"])
        self.assertEqual(res["payload"]["input"]["mixed_language"], True)

    def test_provider_failure_never_fails_project(self):
        class Boom:
            def transcribe(self, *a, **k):
                raise RuntimeError("gnani down")

        res = self._run(mode="sing", language="hi-IN", stt=Boom())
        states = {s["name"]: s["state"] for s in res["stages"]}
        self.assertEqual(states["lyrics"], "failed")
        self.assertEqual(res["payload"]["lyrics"], [])
        self.assertEqual(res["payload"]["warnings"][-1]["stage"], "lyrics")
        self.assertTrue(res["payload"]["notes_clean"])

    def test_missing_registry_skips_lyrics_with_warning(self):
        # B's providers/ may not exist yet: the stage is skipped, the project completes.
        with mock.patch.object(run_mod, "_default_stt", side_effect=ModuleNotFoundError("app.providers")):
            res = self._run(mode="speak", language="hi-IN")
        states = {s["name"]: s["state"] for s in res["stages"]}
        self.assertEqual(states["lyrics"], "skipped")
        self.assertIn("providers_unavailable", [w["code"] for w in res["payload"]["warnings"]])
        self.assertTrue(res["payload"]["notes_clean"])

    def test_clear_key_has_no_key_warning(self):
        codes = [w["code"] for w in self._run(mode="hum")["payload"]["warnings"]]
        self.assertNotIn("low_key_confidence", codes)

    def test_weak_key_is_flagged_in_the_payload_but_not_changed(self):
        weak = {"tonic": "G", "mode": "major", "confidence": 0.19}
        with mock.patch.object(run_mod, "detect_key", return_value=weak):
            pl = self._run(mode="hum")["payload"]
        self.assertEqual(pl["analysis"]["key"], weak)
        flagged = [w for w in pl["warnings"] if w["code"] == "low_key_confidence"]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["stage"], "key_bpm")

    def test_validation(self):
        with self.assertRaises(PipelineError) as cm:
            self._run(mode="sing")
        self.assertEqual(cm.exception.code, "validation_error")
        with self.assertRaises(PipelineError):
            self._run(mode="whistle")

    def test_failure_reports_failed_stage(self):
        events = []
        with self.assertRaises(PipelineError):
            run_pipeline(os.path.join(self.tmp, "missing.wav"), on_progress=lambda s, st, a: events.append((s, st)))
        self.assertIn(("ingest", "failed"), events)


def W(text, start=None, end=None, conf=None):
    return {"text": text, "start": start, "end": end, "confidence": conf}


def N(start):
    return {"pitch": 60, "start": start, "end": start + 0.4, "velocity": 80, "confidence": 0.9}


class AlignTests(unittest.TestCase):
    NOTES = [N(0.0), N(0.5), N(1.0), N(1.5)]

    def test_timestamps_match_closest_onset(self):
        out, approx = align_lyrics([W("a", 0.02), W("b", 0.55), W("c", 1.08)], self.NOTES)
        self.assertEqual([w["note_index"] for w in out], [0, 1, 2])
        self.assertFalse(approx)

    def test_leftover_words_attach_to_nearest_note(self):
        out, _ = align_lyrics([W("a", 0.0), W("b", 0.1), W("c", 0.52)], self.NOTES)
        self.assertEqual(out[0]["note_index"], 0)
        self.assertEqual(out[1]["note_index"], 0)  # nearest note is already taken: shares it
        self.assertEqual(out[2]["note_index"], 1)

    def test_no_timestamps_spread_evenly(self):
        out, approx = align_lyrics([W("a"), W("b")], self.NOTES)
        self.assertEqual([w["note_index"] for w in out], [0, 2])
        self.assertTrue(approx)
        self.assertIsNone(out[0]["start"])

    def test_more_words_than_notes(self):
        out, _ = align_lyrics([W(str(i)) for i in range(8)], self.NOTES)
        self.assertTrue(all(0 <= w["note_index"] < 4 for w in out))

    def test_no_notes(self):
        out, _ = align_lyrics([W("a", 0.1)], [])
        self.assertIsNone(out[0]["note_index"])

    def test_nfc_normalisation(self):
        decomposed = "e\u0301"  # e + combining acute
        out, _ = align_lyrics([W(decomposed)], self.NOTES)
        self.assertEqual(out[0]["text"], "\u00e9")

    def test_devanagari_conjunct_survives(self):
        word = "क्षत्रिय"  # conjuncts plus vowel signs
        out, _ = align_lyrics([W(word)], self.NOTES)
        self.assertEqual(out[0]["text"], word)


class LyricsStageTests(unittest.TestCase):
    NOTES = AlignTests.NOTES

    def test_empty_transcript(self):
        lyrics, warns = run_lyrics_stage(FakeSTT(""), "x.wav", "hi-IN", False, self.NOTES)
        self.assertEqual(lyrics, [])
        self.assertEqual(warns[0]["code"], "lyrics_empty")

    def test_all_low_confidence_is_unclear_but_kept(self):
        stt = FakeSTT("kuch bhi", [W("kuch", 0.0, 0.3, 0.1), W("bhi", 0.5, 0.8, 0.2)])
        lyrics, warns = run_lyrics_stage(stt, "x.wav", "hi-IN", False, self.NOTES)
        self.assertEqual(len(lyrics), 2)
        self.assertIn("lyrics_unclear", [w["code"] for w in warns])

    def test_very_short_text_is_unclear(self):
        _, warns = run_lyrics_stage(FakeSTT("ha"), "x.wav", "hi-IN", False, self.NOTES)
        self.assertIn("lyrics_unclear", [w["code"] for w in warns])

    def test_good_lyrics_no_warnings_when_timestamped(self):
        stt = FakeSTT("tum ho", [W("tum", 0.0, 0.4, 0.9), W("ho", 0.5, 0.9, 0.8)])
        lyrics, warns = run_lyrics_stage(stt, "x.wav", "hi-IN", False, self.NOTES)
        self.assertEqual(warns, [])
        self.assertEqual([w["note_index"] for w in lyrics], [0, 1])


if __name__ == "__main__":
    unittest.main()
