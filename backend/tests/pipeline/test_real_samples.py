"""Runs the whole A1 pipeline on the real recordings in backend/samples/.

Skipped unless librosa is installed and at least one sample exists. Checks structural
invariants only. It cannot say whether the melody is musically right: that needs a
human to listen (see DECISIONS_A.md, "A1 acceptance").
"""
import glob
import importlib.util
import io
import json
import os
import shutil
import unittest

from app.pipeline.cleanup import SNAP_MIN_KEY_CONFIDENCE
from app.pipeline.pitch import MIN_NOTE_CONFIDENCE
from app.pipeline.run import run_pipeline

SAMPLES = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "..", "samples", "hum_*.mp4")))
HAVE_LIBROSA = importlib.util.find_spec("librosa") is not None
HAVE_PM = importlib.util.find_spec("pretty_midi") is not None
KNOWN_WARNING_CODES = {
    "low_pitch_confidence", "low_key_confidence", "bpm_low_confidence", "pitch_engine_fallback",
    "snap_skipped", "quantise_skipped",
}
EPS = 1e-6


def invariant_problems(payload: dict) -> list[str]:
    """Return a list of human-readable problems; empty means all invariants hold."""
    bad: list[str] = []
    raw, clean, a = payload["notes_raw"], payload["notes_clean"], payload["analysis"]
    if not raw:
        bad.append("no raw notes")
    if not clean:
        bad.append("no clean notes")
    for label, notes in (("raw", raw), ("clean", clean)):
        for i, n in enumerate(notes):
            if not n["end"] > n["start"] >= 0:
                bad.append(f"{label}[{i}] bad times {n['start']}..{n['end']}")
            if not 0 <= n["pitch"] <= 127 or not 1 <= n["velocity"] <= 127:
                bad.append(f"{label}[{i}] pitch/velocity out of range")
        for i, (p, q) in enumerate(zip(notes, notes[1:])):
            if q["start"] < p["end"] - EPS:
                bad.append(f"{label}[{i}] overlaps the next note")
    for i, n in enumerate(raw):
        if n["confidence"] is not None and n["confidence"] < MIN_NOTE_CONFIDENCE:
            bad.append(f"raw[{i}] pitch {n['pitch']} has confidence {n['confidence']} below the floor")
    # A1 melody preservation: quantising is off, so cleaning keeps the hummed timing, and the
    # only notes lost are touching same-pitch notes that were merged.
    raw_starts, raw_ends = {n["start"] for n in raw}, {n["end"] for n in raw}
    touching = sum(1 for p, q in zip(raw, raw[1:]) if p["pitch"] == q["pitch"] and abs(q["start"] - p["end"]) <= 2e-4)
    if len(clean) != len(raw) - touching:
        bad.append(f"{len(raw)} raw notes, {touching} touching pairs, but {len(clean)} clean notes")
    for i, n in enumerate(clean):
        if n["start"] not in raw_starts or n["end"] not in raw_ends:
            bad.append(f"clean[{i}] timing differs from the raw notes")
    if a["key"]["confidence"] < SNAP_MIN_KEY_CONFIDENCE and len(clean) == len(raw):
        for i, (r, c) in enumerate(zip(raw, clean)):
            if (r["pitch"] - c["pitch"]) % 12:
                bad.append(f"clean[{i}] pitch {c['pitch']} differs from raw {r['pitch']} by more than an octave although the key is weak")
    if not 60 <= a["bpm"] <= 160 and a["bpm_source"] == "auto":
        bad.append(f"auto bpm {a['bpm']} outside 60..160")
    if not 0 <= a["key"]["confidence"] <= 1:
        bad.append("key confidence outside 0..1")
    for w in payload["warnings"]:
        if w["code"] not in KNOWN_WARNING_CODES:
            bad.append(f"unknown warning code {w['code']}")
    return bad


@unittest.skipUnless(HAVE_LIBROSA and SAMPLES, "needs librosa and backend/samples/hum_*.mp4")
class RealSampleTests(unittest.TestCase):
    results: dict = {}

    @classmethod
    def setUpClass(cls):
        for path in SAMPLES:
            res = run_pipeline(path, mode="hum")
            cls.addClassCleanup(shutil.rmtree, res["workdir"], True)
            cls.results[os.path.basename(path)] = res

    def test_every_sample_satisfies_the_invariants(self):
        for name, res in self.results.items():
            with self.subTest(name):
                self.assertEqual(invariant_problems(res["payload"]), [])

    def test_stages_ran_as_designed(self):
        for name, res in self.results.items():
            with self.subTest(name):
                states = {s["name"]: s["state"] for s in res["stages"]}
                self.assertEqual(states, {"ingest": "done", "pitch": "done", "key_bpm": "done", "cleanup": "done",
                                          "scale": "skipped", "lyrics": "skipped", "arrange": "skipped"})

    def test_payload_is_json_serialisable(self):
        for name, res in self.results.items():
            with self.subTest(name):
                json.dumps(res["payload"], ensure_ascii=False)

    @unittest.skipUnless(HAVE_PM, "pretty_midi not installed")
    def test_midi_matches_the_cleaned_notes(self):
        import pretty_midi

        from app.pipeline.midi_export import midi_bytes

        for name, res in self.results.items():
            with self.subTest(name):
                clean, bpm = res["payload"]["notes_clean"], res["payload"]["analysis"]["bpm"]
                pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes(clean, bpm)))
                got = sorted((n for i in pm.instruments for n in i.notes), key=lambda n: (n.start, n.pitch))
                tick = 60.0 / (bpm * 220)  # one MIDI tick in seconds
                self.assertEqual(len(got), len(clean))
                self.assertAlmostEqual(pm.get_tempo_changes()[1][0], bpm, places=1)  # header tempo == analysis.bpm
                for src, out in zip(clean, got):
                    self.assertEqual(out.pitch, src["pitch"])
                    self.assertLessEqual(abs(out.start - src["start"]), tick + 1e-9)
                    self.assertLessEqual(abs(out.end - src["end"]), tick + 1e-9)


if __name__ == "__main__":
    unittest.main()
