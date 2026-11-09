"""Audio ingest (F1, backend side): decode, trim, normalise, length-check.

ffmpeg decodes anything to mono 16-bit WAV at 22.05 kHz (music analysis). A
16 kHz copy is derived for Prisma (verify Prisma's real requirement with Gnani,
see OPEN_QUESTIONS_A.md). Audio is only written to a temp working directory;
the caller (the API layer) uploads what it needs to GridFS and removes it.
"""
from __future__ import annotations

import math
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass

import numpy as np
from scipy.signal import resample_poly

from . import PipelineError

MUSIC_SR = 22050
PRISMA_SR = 16000
PEAK_TARGET_DBFS = -1.0
MIN_SECONDS = 1.0
MIN_AUDIBLE_SECONDS = 0.3  # what must remain after silence trimming
SILENCE_FLOOR = 1e-4  # about -80 dBFS: below this the file is treated as silent


@dataclass
class IngestResult:
    music_wav: str  # mono 22.05 kHz, trimmed and normalised
    prisma_wav: str  # mono 16 kHz copy of the same audio
    samples: np.ndarray  # float32 in [-1, 1] at MUSIC_SR
    sr: int
    duration_s: float  # duration after trimming
    original_duration_s: float
    leading_trim_s: float  # silence removed from the start
    workdir: str  # caller removes this when done


def _decode(src: str, dst: str, sr: int, max_seconds: float) -> None:
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src,
        "-vn", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le",
        # Cap decoding so an absurdly long file cannot eat memory before the
        # length check below runs.
        "-t", str(max_seconds + 1.0),
        dst,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as e:
        raise PipelineError("internal", "ffmpeg is not installed or not on PATH.") from e
    except subprocess.TimeoutExpired as e:
        raise PipelineError("internal", "Decoding the audio took too long.") from e
    if proc.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) < 44:
        raise PipelineError(
            "unsupported_format",
            "Could not read this file as audio. Use wav, mp3, m4a or webm.",
        )


def _read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    y = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return y, sr


def _write_wav(path: str, y: np.ndarray, sr: int) -> None:
    pcm = (np.clip(y, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def trim_silence(
    y: np.ndarray, sr: int, threshold_db: float = -40.0, pad_s: float = 0.1, frame_ms: float = 20.0
) -> tuple[np.ndarray, int]:
    """Trim leading and trailing silence.

    Silence is anything more than `threshold_db` below the loudest 20 ms frame.
    `pad_s` is kept on both sides. Returns (trimmed, start_sample).
    """
    frame = max(1, int(sr * frame_ms / 1000))
    n = len(y) // frame
    if n == 0:
        return y, 0
    rms = np.sqrt(np.mean(y[: n * frame].reshape(n, frame) ** 2, axis=1))
    peak = float(rms.max())
    if peak <= 0:
        return y, 0
    loud = np.nonzero(rms >= peak * 10 ** (threshold_db / 20))[0]
    pad = int(pad_s * sr)
    start = max(0, int(loud[0]) * frame - pad)
    end = min(len(y), (int(loud[-1]) + 1) * frame + pad)
    return y[start:end], start


def normalize_peak(y: np.ndarray, target_dbfs: float = PEAK_TARGET_DBFS) -> np.ndarray:
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak <= 0:
        return y
    return (y * (10 ** (target_dbfs / 20) / peak)).astype(np.float32)


def ingest(src_path: str, workdir: str | None = None, max_seconds: float = 60.0) -> IngestResult:
    """Decode, validate, trim and normalise one audio file."""
    if not os.path.isfile(src_path):
        raise PipelineError("validation_error", "Audio file not found.")
    workdir = workdir or tempfile.mkdtemp(prefix="arohah_")
    os.makedirs(workdir, exist_ok=True)

    decoded = os.path.join(workdir, "decoded.wav")
    _decode(src_path, decoded, MUSIC_SR, max_seconds)
    y, sr = _read_wav(decoded)
    os.remove(decoded)
    original = len(y) / sr

    if original > max_seconds + 1e-3:
        raise PipelineError(
            "audio_too_long", f"Audio must be {max_seconds:g} seconds or less.", {"max_seconds": max_seconds}
        )
    if original < MIN_SECONDS:
        raise PipelineError("audio_too_short", "Audio must be at least 1 second.", {"min_seconds": MIN_SECONDS})
    if float(np.max(np.abs(y))) < SILENCE_FLOOR:
        raise PipelineError("validation_error", "The recording is silent. Check the microphone and try again.")

    y, start = trim_silence(y, sr)
    if len(y) / sr < MIN_AUDIBLE_SECONDS:
        raise PipelineError("audio_too_short", "Not enough sound was found after removing silence.")
    y = normalize_peak(y)

    music_wav = os.path.join(workdir, "music_22k.wav")
    prisma_wav = os.path.join(workdir, "prisma_16k.wav")
    _write_wav(music_wav, y, sr)
    g = math.gcd(PRISMA_SR, sr)
    _write_wav(prisma_wav, resample_poly(y, PRISMA_SR // g, sr // g).astype(np.float32), PRISMA_SR)

    return IngestResult(
        music_wav=music_wav,
        prisma_wav=prisma_wav,
        samples=y,
        sr=sr,
        duration_s=round(len(y) / sr, 3),
        original_duration_s=round(original, 3),
        leading_trim_s=round(start / sr, 3),
        workdir=workdir,
    )
