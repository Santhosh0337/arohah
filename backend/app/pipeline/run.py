"""Pipeline orchestrator with per-stage progress.

Phase A1 runs: ingest -> pitch -> key_bpm -> cleanup -> (lyrics).
`scale` and `arrange` are reported as "skipped" until Phase A3.

Cleanup needs the key and BPM, so key_bpm *executes* before cleanup even
though the contract lists the stage names as cleanup, key_bpm (see
OPEN_QUESTIONS_A.md, item 1).

Command line, from `backend/`:
    python -m app.pipeline.run clip.wav --mode hum --midi out.mid --json out.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import unicodedata
from typing import Any, Callable

from . import STAGES, Note, PipelineError, make_warning
from .cleanup import SNAP_MIN_KEY_CONFIDENCE, clean_notes, scale_pitch_classes
from .ingest import ingest
from .key_bpm import detect_bpm, detect_key, key_warnings
from .pitch import extract_notes

ProgressFn = Callable[[str, str, list[dict]], None]  # (stage, state, all stage states)

ALIGN_TOLERANCE_S = 0.15
LOW_WORD_CONFIDENCE = 0.4
MODES = ("hum", "sing", "speak")


def align_lyrics(words: list[dict], notes: list[Note]) -> tuple[list[dict], bool]:
    """Approximate lyric-to-note alignment (bible 6.4).

    Returns (LyricWord list, approximate). With word timestamps each word takes
    the note whose onset is closest within 150 ms (one word per note, closest
    pairs first); leftover words attach to the nearest note. Without
    timestamps, words are spread evenly across the notes and `approximate`
    is True.
    """
    out = [
        {
            "text": unicodedata.normalize("NFC", w["text"]),
            "start": w.get("start"),
            "end": w.get("end"),
            "note_index": None,
            "confidence": w.get("confidence"),
        }
        for w in words
    ]
    if not out or not notes:
        return out, not all(w["start"] is not None for w in out)

    timed = all(w["start"] is not None for w in out)
    if not timed:
        for i, w in enumerate(out):
            w["note_index"] = min(int(i * len(notes) / len(out)), len(notes) - 1)
        return out, True

    pairs = sorted(
        (abs(w["start"] - n["start"]), wi, ni)
        for wi, w in enumerate(out)
        for ni, n in enumerate(notes)
        if abs(w["start"] - n["start"]) <= ALIGN_TOLERANCE_S
    )
    used_w: set[int] = set()
    used_n: set[int] = set()
    for _, wi, ni in pairs:
        if wi not in used_w and ni not in used_n:
            out[wi]["note_index"] = ni
            used_w.add(wi)
            used_n.add(ni)
    for wi, w in enumerate(out):
        if w["note_index"] is None:
            w["note_index"] = min(range(len(notes)), key=lambda ni: abs(notes[ni]["start"] - w["start"]))
    return out, False


def run_lyrics_stage(stt: Any, wav_path: str, language: str, mixed_language: bool, notes: list[Note]):
    """Transcribe and align. Returns (lyrics, warnings). Raises ProviderError subclasses."""
    t = stt.transcribe(wav_path, language, mixed_language)
    text = unicodedata.normalize("NFC", (t.get("text") or "")).strip()
    words = [dict(w) for w in (t.get("words") or [])]
    if not words and text:
        words = [{"text": w, "start": None, "end": None, "confidence": None} for w in text.split()]
    if not text and not words:
        return [], [make_warning("lyrics_empty", "No lyrics were recognised. Type them in.", "lyrics")]

    lyrics, approximate = align_lyrics(words, notes)
    warnings: list[dict] = []
    confs = [w["confidence"] for w in lyrics if w["confidence"] is not None]
    if len(text) < 3 or (confs and max(confs) < LOW_WORD_CONFIDENCE):
        warnings.append(make_warning("lyrics_unclear", "Lyrics unclear, please edit.", "lyrics"))
    if approximate:
        warnings.append(
            make_warning("lyrics_alignment_approximate", "No word timestamps; lyrics are spread evenly over the notes.", "lyrics")
        )
    return lyrics, warnings


def _default_stt():
    """B's registry. Until B pushes providers/, the lyrics stage is skipped."""
    from app.providers.registry import get_stt  # type: ignore[import-not-found]

    return get_stt()


def run_pipeline(
    audio_path: str,
    *,
    mode: str = "hum",
    language: str | None = None,
    mixed_language: bool = False,
    bpm_override: float | None = None,
    cleanup: bool = True,
    snap_to_scale: bool = True,
    quantize: bool = False,
    workdir: str | None = None,
    max_seconds: float = 60.0,
    on_progress: ProgressFn | None = None,
    stt: Any = None,
) -> dict:
    """Run the A1 pipeline on one audio file.

    Returns {"payload", "stages", "files", "workdir"}:
      payload  partial contract Payload: input, lyrics, notes_raw, notes_clean,
               analysis (bpm, bpm_source, key, sa_override), warnings.
               notes_clean keeps the hummed timing; quantize=True asks for grid timing and is
               done only when the tempo is trusted and the onsets sit on a grid (otherwise a
               warning says why). Scale snapping needs key confidence >= 0.70.
               input.audio_file_id is None; the API layer fills it after the
               GridFS upload. scale_matches, mood and arrangement come in A3.
      files    paths of the processed WAVs for the API layer to store
      workdir  temp dir the caller removes
    Raises PipelineError; stage states are reported through on_progress first.
    """
    if mode not in MODES:
        raise PipelineError("validation_error", f"mode must be one of {', '.join(MODES)}.")
    if mode != "hum" and not language:
        raise PipelineError("validation_error", "language is required unless mode is hum.")

    states = {s: "pending" for s in STAGES}

    def snapshot() -> list[dict]:
        return [{"name": s, "state": states[s]} for s in STAGES]

    def set_state(stage: str, state: str) -> None:
        states[stage] = state
        if on_progress:
            on_progress(stage, state, snapshot())

    warnings: list[dict] = []

    def stage(name: str, fn):
        set_state(name, "running")
        try:
            result = fn()
        except Exception:
            set_state(name, "failed")
            raise
        set_state(name, "done")
        return result

    ing = stage("ingest", lambda: ingest(audio_path, workdir, max_seconds))
    notes_raw, w = stage("pitch", lambda: extract_notes(ing.samples, ing.sr))
    warnings += w

    def _key_bpm():
        key = detect_key(notes_raw)
        bpm, bw = detect_bpm(ing.samples, ing.sr, notes_raw, bpm_override)
        return key, bpm, key_warnings(key) + bw

    key, bpm_info, kbw = stage("key_bpm", _key_bpm)
    warnings += kbw

    notes_clean, cleanup_report = stage(
        "cleanup",
        lambda: clean_notes(
            notes_raw,
            bpm_info["bpm"],
            scale_pitch_classes(key["tonic"], key["mode"]),
            cleanup=cleanup,
            snap_to_scale=snap_to_scale,
            quantize=quantize,
            key_confidence=key["confidence"],
            tempo_trusted=bool(bpm_info.get("trusted", False)),
        ),
    )
    if cleanup_report.snap_skipped_reason:
        conf = key["confidence"]
        warnings.append(
            make_warning(
                "snap_skipped",
                f"Notes were not moved onto the {key['tonic']} {key['mode']} scale: the key estimate "
                f"(confidence {conf:.2f}) is below {SNAP_MIN_KEY_CONFIDENCE:.2f}, so your pitches are kept as hummed."
                if conf is not None
                else "Notes were not moved onto a scale: the key confidence is unknown.",
                "cleanup",
            )
        )
    if cleanup_report.quantise_requested and not cleanup_report.quantised:
        warnings.append(
            make_warning(
                "quantise_skipped",
                f"Rhythm was not quantised: {cleanup_report.quantise_skipped_text()}. The timing is as hummed.",
                "cleanup",
            )
        )

    set_state("scale", "skipped")  # Phase A3

    lyrics: list[dict] = []
    if mode == "hum":
        set_state("lyrics", "skipped")
    else:
        set_state("lyrics", "running")
        try:
            provider = stt or _default_stt()
            lyrics, lw = run_lyrics_stage(provider, ing.prisma_wav, language, mixed_language, notes_clean)  # type: ignore[arg-type]
            warnings += lw
            set_state("lyrics", "done")
        except ImportError:
            warnings.append(make_warning("providers_unavailable", "Speech provider module not available yet.", "lyrics"))
            set_state("lyrics", "skipped")
        except Exception as e:  # ProviderError subclasses (B) and anything else: never fail the project
            warnings.append(make_warning("provider_error", f"Lyrics failed: {type(e).__name__}.", "lyrics"))
            set_state("lyrics", "failed")

    set_state("arrange", "skipped")  # Phase A3

    payload = {
        "input": {
            "mode": mode,
            "language": None if mode == "hum" else language,
            "mixed_language": bool(mixed_language) if mode != "hum" else False,
            "audio_file_id": None,
            "duration_s": ing.duration_s,
        },
        "lyrics": lyrics,
        "notes_raw": notes_raw,
        "notes_clean": notes_clean,
        "analysis": {
            "bpm": bpm_info["bpm"],
            "bpm_source": bpm_info["bpm_source"],
            "key": key,
            "scale_matches": [],
            "sa_override": None,
        },
        "warnings": warnings,
    }
    return {
        "payload": payload,
        "stages": snapshot(),
        "files": {"music_wav": ing.music_wav, "prisma_wav": ing.prisma_wav},
        "workdir": ing.workdir,
    }


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the Arohah melody pipeline on one clip.")
    ap.add_argument("audio")
    ap.add_argument("--mode", default="hum", choices=MODES)
    ap.add_argument("--language")
    ap.add_argument("--mixed", action="store_true")
    ap.add_argument("--bpm", type=float, help="override BPM")
    ap.add_argument("--no-cleanup", action="store_true")
    ap.add_argument("--no-snap", action="store_true")
    ap.add_argument("--quantize", action="store_true", help="snap note onsets to a rhythmic grid (off by default; only done when the tempo is trusted and the onsets fit a grid)")
    ap.add_argument("--midi", help="write the cleaned melody as a .mid file")
    ap.add_argument("--json", help="write the partial payload as JSON")
    a = ap.parse_args(argv)

    def progress(stage: str, state: str, _all: list[dict]) -> None:
        print(f"  [{state:>7}] {stage}", file=sys.stderr)

    try:
        res = run_pipeline(
            a.audio, mode=a.mode, language=a.language, mixed_language=a.mixed, bpm_override=a.bpm,
            cleanup=not a.no_cleanup, snap_to_scale=not a.no_snap, quantize=a.quantize, on_progress=progress,
        )
    except PipelineError as e:
        print(f"error ({e.code}): {e.message}", file=sys.stderr)
        return 2
    try:
        p = res["payload"]
        k = p["analysis"]["key"]
        print(f"duration {p['input']['duration_s']} s | {len(p['notes_raw'])} raw notes -> {len(p['notes_clean'])} clean")
        print(f"key {k['tonic']} {k['mode']} (confidence {k['confidence']}) | {p['analysis']['bpm']} BPM ({p['analysis']['bpm_source']})")
        for wn in p["warnings"]:
            print(f"warning [{wn['stage']}] {wn['code']}: {wn['message']}")
        if a.json:
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump(p, f, ensure_ascii=False, indent=2)
        if a.midi:
            from .midi_export import write_midi

            write_midi(a.midi, p["notes_clean"], p["analysis"]["bpm"])
            print(f"wrote {a.midi}")
    finally:
        shutil.rmtree(res["workdir"], ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
