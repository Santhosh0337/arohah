"""Mock providers: offline stand-ins for Prisma, Timbre and the LLM.

Everything returned here is placeholder data. It is never real Gnani output.
Each class sets ``is_mock = True`` and every payload carries a mock marker, so
callers and the UI can tell it apart from live results. The registry reports
these as "mock" in /api/health.
"""

from __future__ import annotations

import io
import wave

from .base import Transcript

MOCK_MARKER = "[MOCK]"


class MockSTT:
    """Returns a fixed placeholder transcript. Does not read the audio."""

    is_mock = True

    def transcribe(
        self, wav_path: str, language: str, mixed_language: bool = False
    ) -> Transcript:
        return {
            "text": f"{MOCK_MARKER} placeholder transcript, not real speech recognition",
            "words": [],  # no word timestamps or confidence are ever invented
            "language": language,
            "raw": {
                "mock": True,
                "wav_path": wav_path,
                "mixed_language": mixed_language,
            },
        }


class MockTTS:
    """Returns half a second of silence as a WAV. Does not speak the text."""

    is_mock = True

    def synthesize(
        self, text: str, language: str, voice: str | None = None
    ) -> tuple[bytes, str]:
        sample_rate = 16000
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(b"\x00\x00" * (sample_rate // 2))
        return buf.getvalue(), "audio/wav"


class MockLLM:
    """Returns an object shaped like ``schema`` filled with placeholder values.

    Strings become "[MOCK]", numbers 0, booleans False, arrays empty. For an
    ``enum`` the first listed value is used only so the result stays valid
    against the schema; it does not mean the model chose it. Callers that act
    on an LLM result (intent fallback) should check provider_status() and skip
    the fallback when the LLM is "mock".
    """

    is_mock = True

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        value = self._fill(schema)
        return value if isinstance(value, dict) else {"mock": True}

    def _fill(self, schema: dict):
        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]
        kind = schema.get("type")
        if kind == "object":
            props = schema.get("properties", {})
            return {name: self._fill(sub) for name, sub in props.items()}
        if kind == "array":
            return []
        if kind == "string":
            return MOCK_MARKER
        if kind == "integer":
            return 0
        if kind == "number":
            return 0.0
        if kind == "boolean":
            return False
        return None
