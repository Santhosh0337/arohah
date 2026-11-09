import inspect
import io
import wave

import pytest

from app.providers import base, mock


def _params(fn):
    return [
        (p.name, p.default, p.annotation)
        for p in inspect.signature(fn).parameters.values()
        if p.name != "self"
    ]


def test_mock_signatures_match_contract_protocols():
    pairs = [
        (base.STTProvider.transcribe, mock.MockSTT.transcribe),
        (base.TTSProvider.synthesize, mock.MockTTS.synthesize),
        (base.LLMProvider.complete_json, mock.MockLLM.complete_json),
    ]
    for proto_fn, mock_fn in pairs:
        assert _params(proto_fn) == _params(mock_fn)


def test_contract_signature_details():
    assert [n for n, *_ in _params(base.STTProvider.transcribe)] == [
        "wav_path", "language", "mixed_language",
    ]
    assert _params(base.STTProvider.transcribe)[2][1] is False
    assert [n for n, *_ in _params(base.TTSProvider.synthesize)] == [
        "text", "language", "voice",
    ]
    assert [n for n, *_ in _params(base.LLMProvider.complete_json)] == [
        "system", "user", "schema",
    ]


def test_error_hierarchy():
    for cls in (base.ProviderUnavailable, base.ProviderTimeout, base.ProviderBadResponse):
        assert issubclass(cls, base.ProviderError)


def test_mocks_satisfy_protocols():
    assert isinstance(mock.MockSTT(), base.STTProvider)
    assert isinstance(mock.MockTTS(), base.TTSProvider)
    assert isinstance(mock.MockLLM(), base.LLMProvider)


def test_mock_stt_is_marked_and_invents_no_words():
    t = mock.MockSTT().transcribe("/tmp/x.wav", "hi-IN", mixed_language=True)
    assert t["text"].startswith(mock.MOCK_MARKER)
    assert t["words"] == []
    assert t["language"] == "hi-IN"
    assert t["raw"]["mock"] is True


def test_mock_tts_returns_valid_wav():
    data, mime = mock.MockTTS().synthesize("hello", "en-IN")
    assert mime == "audio/wav"
    with wave.open(io.BytesIO(data)) as w:
        assert w.getnchannels() == 1 and w.getnframes() > 0


def test_mock_llm_fills_schema_with_placeholders():
    schema = {
        "type": "object",
        "properties": {
            "name": {"enum": ["play_stop", "explain"]},
            "params": {"type": "object", "properties": {"label": {"type": "string"}}},
            "confidence": {"type": "number"},
        },
    }
    out = mock.MockLLM().complete_json("s", "u", schema)
    assert out == {"name": "play_stop", "params": {"label": "[MOCK]"}, "confidence": 0.0}
