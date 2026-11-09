"""Arohah melody pipeline (Person A).

Shared types and errors for the pipeline stages. Notes are plain dicts that
already match the API contract (docs/API_CONTRACT.md section 1), so they can be
stored and returned without conversion.
"""
from __future__ import annotations

from typing import Any, TypedDict

# Sharp-only tonic names (contract section 0).
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Stage names in the order the contract lists them (section 2.5).
STAGES = ["ingest", "pitch", "cleanup", "key_bpm", "scale", "lyrics", "arrange"]


class Note(TypedDict):
    pitch: int  # MIDI note number
    start: float  # seconds
    end: float  # seconds
    velocity: int  # 1..127
    confidence: float | None  # 0..1 or None


class PipelineError(Exception):
    """A failure that stops the pipeline.

    `code` is one of the error codes in the API contract (section 3), so the
    API layer can map it straight to an error response.
    """

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def make_warning(code: str, message: str, stage: str) -> dict[str, str]:
    """A non-fatal problem, shaped like an entry of payload.warnings."""
    return {"code": code, "message": message, "stage": stage}
