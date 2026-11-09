import json
from pathlib import Path

import pytest

from app.providers import mock, registry

ENV_VARS = [
    "USE_MOCKS", "GNANI_API_KEY", "GNANI_PRISMA_API_KEY", "GNANI_TIMBRE_API_KEY",
    "GNANI_LLM_API_KEY", "GNANI_LLM_MODEL",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in ENV_VARS:
        monkeypatch.delenv(v, raising=False)


ALL_MOCK = {"prisma": "mock", "timbre": "mock", "llm": "mock"}


def test_default_is_mock():
    assert registry.provider_status() == ALL_MOCK
    assert isinstance(registry.get_stt(), mock.MockSTT)
    assert isinstance(registry.get_tts(), mock.MockTTS)
    assert isinstance(registry.get_llm(), mock.MockLLM)


def test_keys_alone_never_make_a_service_live(monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY", "dummy")
    monkeypatch.setenv("GNANI_PRISMA_API_KEY", "dummy")
    assert registry.provider_status() == ALL_MOCK
    assert isinstance(registry.get_stt(), mock.MockSTT)


def test_live_needs_factory_key_and_no_use_mocks(monkeypatch):
    class Fake:
        pass

    seen = {}

    def factory(cfg):
        seen["cfg"] = cfg
        return Fake()

    monkeypatch.setitem(registry._LIVE_FACTORIES, "prisma", factory)
    # factory but no key
    assert registry.provider_status()["prisma"] == "mock"
    # shared key
    monkeypatch.setenv("GNANI_API_KEY", "shared")
    assert registry.provider_status()["prisma"] == "live"
    assert isinstance(registry.get_stt(), Fake)
    assert seen["cfg"].api_key == "shared"
    # per-service key overrides shared
    monkeypatch.setenv("GNANI_PRISMA_API_KEY", "own")
    registry.get_stt()
    assert seen["cfg"].api_key == "own"
    # other services stay mock
    assert registry.provider_status()["timbre"] == "mock"
    # USE_MOCKS forces mock
    monkeypatch.setenv("USE_MOCKS", "true")
    assert registry.provider_status()["prisma"] == "mock"
    assert isinstance(registry.get_stt(), mock.MockSTT)


def test_status_keys_match_contract():
    assert set(registry.provider_status()) == {"prisma", "timbre", "llm"}


def test_languages_json_matches_contract_schema():
    path = Path(__file__).resolve().parents[2] / "data" / "languages.json"
    langs = json.loads(path.read_text(encoding="utf-8"))
    fields = {
        "code", "name", "native_name", "script", "font_family",
        "prisma", "timbre", "command_keywords", "demo", "tested",
    }
    assert [l["name"] for l in langs] == ["English", "Tamil", "Hindi"]
    for l in langs:
        assert set(l) == fields
        assert l["prisma"] in {"confirmed", "unconfirmed", "unsupported"}
        assert l["timbre"] in {"confirmed", "unconfirmed", "unsupported"}
        assert l["prisma"] == "unconfirmed" and l["timbre"] == "unconfirmed"
        assert l["tested"] is False
