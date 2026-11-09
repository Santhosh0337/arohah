import os
import shutil
import tempfile
import unittest
import wave

import numpy as np

import synth
from app.pipeline import PipelineError
from app.pipeline.ingest import PRISMA_SR, MUSIC_SR, ingest, normalize_peak, trim_silence


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _wav(self, y, sr=synth.SR, name="in.wav"):
        p = os.path.join(self.tmp, name)
        synth.write_wav(p, y, sr)
        return p

    def test_trim_silence_keeps_padding(self):
        y = synth.make_hum([(60, 1.0)], lead=1.0, tail=1.0)
        out, start = trim_silence(y, synth.SR)
        self.assertAlmostEqual(len(out) / synth.SR, 1.0 + 0.2, delta=0.1)
        self.assertAlmostEqual(start / synth.SR, 0.9, delta=0.03)

    def test_normalize_peak_to_minus_1_dbfs(self):
        y = normalize_peak(np.array([0.1, -0.2, 0.05], dtype=np.float32))
        self.assertAlmostEqual(float(np.max(np.abs(y))), 10 ** (-1 / 20), places=4)

    def test_ingest_outputs(self):
        y = synth.make_hum([(60, 0.8), (62, 0.8), (64, 0.8)], lead=0.8, tail=0.8)
        r = ingest(self._wav(y), workdir=os.path.join(self.tmp, "w"))
        self.assertEqual(r.sr, MUSIC_SR)
        self.assertLess(r.duration_s, r.original_duration_s)
        self.assertAlmostEqual(float(np.max(np.abs(r.samples))), 10 ** (-1 / 20), places=3)
        with wave.open(r.prisma_wav) as w:
            self.assertEqual((w.getframerate(), w.getnchannels()), (PRISMA_SR, 1))
            self.assertAlmostEqual(w.getnframes() / PRISMA_SR, r.duration_s, delta=0.01)
        with wave.open(r.music_wav) as w:
            self.assertEqual((w.getframerate(), w.getnchannels()), (MUSIC_SR, 1))

    def test_resamples_and_downmixes_other_rates(self):
        y = synth.make_hum([(60, 1.5)], sr=44100)
        r = ingest(self._wav(y, sr=44100), workdir=os.path.join(self.tmp, "w"))
        self.assertEqual(r.sr, MUSIC_SR)

    def test_too_long(self):
        y = synth.make_hum([(60, 5.0)])
        with self.assertRaises(PipelineError) as cm:
            ingest(self._wav(y), max_seconds=3.0)
        self.assertEqual(cm.exception.code, "audio_too_long")

    def test_too_short(self):
        y = synth.make_hum([(60, 0.3)], lead=0.1, tail=0.1)
        with self.assertRaises(PipelineError) as cm:
            ingest(self._wav(y))
        self.assertEqual(cm.exception.code, "audio_too_short")

    def test_silent_file(self):
        with self.assertRaises(PipelineError) as cm:
            ingest(self._wav(np.zeros(synth.SR * 2, dtype=np.float32)))
        self.assertEqual(cm.exception.code, "validation_error")

    def test_not_audio(self):
        p = os.path.join(self.tmp, "x.wav")
        with open(p, "wb") as f:
            f.write(b"this is not audio at all" * 50)
        with self.assertRaises(PipelineError) as cm:
            ingest(p)
        self.assertEqual(cm.exception.code, "unsupported_format")

    def test_missing_file(self):
        with self.assertRaises(PipelineError) as cm:
            ingest(os.path.join(self.tmp, "nope.wav"))
        self.assertEqual(cm.exception.code, "validation_error")


if __name__ == "__main__":
    unittest.main()
