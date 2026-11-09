# Test recordings for the melody pipeline

Put 3 to 5 **real** hums here (Phase A1, bible section 9). Original melodies only, no copyrighted songs.
Mono is fine; wav, mp3, m4a or webm; 3 to 20 seconds each.

For every clip add a small JSON file with what you *know* about it (what you hummed, not what the code says):

    s-folk-hum.wav
    s-folk-hum.expected.json   {"key": "D major", "bpm": 96, "notes": "started on Sa, one octave jump near the end"}

Run one clip and compare by ear:

    cd backend
    python -m app.pipeline.run samples/s-folk-hum.wav --mode hum --midi /tmp/out.mid --json /tmp/out.json

Record the expected vs observed key/BPM and any octave or timing errors in `eval/melody_eval.md` (Phase A5).
The synthetic signals in `tests/pipeline/synth.py` are unit-test fixtures only and are not samples.
