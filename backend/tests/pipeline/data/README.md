# Real-recording fixtures (Phase A1)

Outputs of the pipeline on the five real hums in `backend/samples/` (one speaker, one microphone).
They are test data, not ground truth: nobody has marked what was hummed, so tests that use them
check properties (nothing deleted, nothing moved, MIDI agrees with JSON), never "the right notes".

| file | what it is | from |
|---|---|---|
| `real_<name>.json` | pipeline payload (notes_raw, notes_clean, analysis, warnings) from the pre-change code | `a1_rev2/<name>.json` of the A1 experiments ZIP |
| `real_<name>_f0.json` | pYIN output (times, f0, voiced_prob, rms) | `backend/out/<name>_f0.json` |
| `real_<name>.mid` (2 files) | the MIDI export of that run | `a1_rev2/<name>.mid` |

Caveats:

* `notes_raw` in the JSON files is what the OLD extraction produced (it dropped every segment
  under 80 ms). The cleanup tests use it as raw input, which is exactly what the old cleanup received.
* The `_f0.json` files come from a slightly different pYIN run than the JSON files (about 80%
  of notes identical, some boundaries one frame apart; f0 stored to 0.01 Hz). Extraction tests
  therefore compare the code with itself on this data and do not compare with `notes_raw`.
