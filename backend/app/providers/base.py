"""Provider interfaces for Arohah.

These definitions are copied from docs/API_CONTRACT.md section 5. The
signatures are fixed by the contract: change them only through a contract PR
that both people approve.

Adapters raise ProviderError subclasses and never return fabricated data.
Only mock.py returns placeholder data.
"""

from __future__ import annotations

from typing import Protocol, TypedDict, runtime_checkable


class Word(TypedDict):
    text: str
    start: float | None
    end: float | None
    confidence: float | None


class Transcript(TypedDict):
    text: str
    words: list[Word]
    language: str
    raw: dict


@runtime_checkable
class STTProvider(Protocol):
    def transcribe(
        self, wav_path: str, language: str, mixed_language: bool = False
    ) -> Transcript: ...


@runtime_checkable
class TTSProvider(Protocol):
    def synthesize(
        self, text: str, language: str, voice: str | None = None
    ) -> tuple[bytes, str]:  # (audio bytes, mime type)
        ...


@runtime_checkable
class LLMProvider(Protocol):
    def complete_json(self, system: str, user: str, schema: dict) -> dict: ...


class ProviderError(Exception):
    """Base class for every provider failure."""


class ProviderUnavailable(ProviderError):
    """The provider could not be reached or rejected the request."""


class ProviderTimeout(ProviderError):
    """The provider call timed out."""


class ProviderBadResponse(ProviderError):
    """The provider answered, but the response could not be used."""
