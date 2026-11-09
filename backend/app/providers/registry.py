"""Picks live or mock providers from configuration.

Public API (docs/API_CONTRACT.md section 5): get_stt(), get_tts(), get_llm(),
provider_status().

Rules:
- A service is "live" only when ALL of these hold: USE_MOCKS is not true, an
  API key is configured, and a live adapter is registered in _LIVE_FACTORIES.
  A key alone never makes a service live.
- No live adapter exists yet (live integration is deferred, see
  DECISIONS_B.md), so every service is "mock" today.
- Status is derived from the same decision get_*() uses, so a mock is never
  reported as live.

To add a live adapter later: write the adapter in providers/gnani_*.py, then
point the matching _LIVE_FACTORIES entry at a function that takes a
ServiceConfig and returns the adapter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from .base import LLMProvider, STTProvider, TTSProvider
from .mock import MockLLM, MockSTT, MockTTS

SERVICES = ("prisma", "timbre", "llm")

# Env var names come from Arohah_Project_Bible.md section 14.
_KEY_VARS = {
    "prisma": "GNANI_PRISMA_API_KEY",
    "timbre": "GNANI_TIMBRE_API_KEY",
    "llm": "GNANI_LLM_API_KEY",
}
_BASE_URL_VARS = {
    "prisma": "GNANI_PRISMA_BASE_URL",
    "timbre": "GNANI_TIMBRE_BASE_URL",
    "llm": "GNANI_LLM_BASE_URL",
}
_SHARED_KEY_VAR = "GNANI_API_KEY"  # per-service variables override it
_LLM_MODEL_VAR = "GNANI_LLM_MODEL"


@dataclass(frozen=True)
class ServiceConfig:
    """What a live adapter factory receives. Nothing here is logged."""

    api_key: str
    base_url: str | None
    model: str | None  # only set for the llm service


# Live adapter factories. None means "no live adapter implemented yet".
_LIVE_FACTORIES: dict[str, Callable[[ServiceConfig], object] | None] = {
    "prisma": None,
    "timbre": None,
    "llm": None,
}


def _use_mocks() -> bool:
    return os.environ.get("USE_MOCKS", "false").strip().lower() in {"1", "true", "yes", "on"}


def _config(service: str) -> ServiceConfig | None:
    key = os.environ.get(_KEY_VARS[service], "").strip() or os.environ.get(
        _SHARED_KEY_VAR, ""
    ).strip()
    if not key:
        return None
    return ServiceConfig(
        api_key=key,
        base_url=os.environ.get(_BASE_URL_VARS[service], "").strip() or None,
        model=(os.environ.get(_LLM_MODEL_VAR, "").strip() or None)
        if service == "llm"
        else None,
    )


def _live_factory(service: str):
    """Return (factory, config), or (None, None) when the service must be mocked."""
    if _use_mocks():
        return None, None
    cfg = _config(service)
    factory = _LIVE_FACTORIES[service]
    if cfg is None or factory is None:
        return None, None
    return factory, cfg


def _build(service: str, mock_cls):
    factory, cfg = _live_factory(service)
    return factory(cfg) if factory else mock_cls()


def get_stt() -> STTProvider:
    return _build("prisma", MockSTT)


def get_tts() -> TTSProvider:
    return _build("timbre", MockTTS)


def get_llm() -> LLMProvider:
    return _build("llm", MockLLM)


def provider_status() -> dict[str, str]:
    """{"prisma": "live|mock", "timbre": "live|mock", "llm": "live|mock"}"""
    return {
        service: "live" if _live_factory(service)[0] else "mock"
        for service in SERVICES
    }
