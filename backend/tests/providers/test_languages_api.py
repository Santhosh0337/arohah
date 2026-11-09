"""Tests for GET /api/languages (Phase B2, bible 16.5 and contract 2.2)."""

import json
import unicodedata
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from app.api import languages as languages_api  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "data" / "languages.json"
EXPECTED_KEYS = {
    "code", "name", "native_name", "script", "font_family",
    "prisma", "timbre", "command_keywords", "demo", "tested",
}
STATUSES = {"confirmed", "unconfirmed", "unsupported"}


def raw_rows():
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def test_handler_returns_contract_structure():
    body = languages_api.list_languages().model_dump()
    assert list(body) == ["languages"]
    for row in body["languages"]:
        assert set(row) == EXPECTED_KEYS
        assert row["prisma"] in STATUSES and row["timbre"] in STATUSES


def test_handler_matches_json_file_exactly():
    served = languages_api.list_languages().model_dump()["languages"]
    assert served == raw_rows()


def test_demo_languages_and_statuses_are_unchanged():
    by_code = {r["code"]: r for r in raw_rows()}
    assert set(by_code) == {"en-IN", "ta-IN", "hi-IN"}
    for row in by_code.values():
        assert row["demo"] is True
        assert row["prisma"] == "unconfirmed"
        assert row["timbre"] == "unconfirmed"
        assert row["tested"] is False


def test_native_script_names_are_intact_utf8_nfc():
    by_code = {r["code"]: r for r in raw_rows()}
    assert by_code["ta-IN"]["native_name"] == "தமிழ்"
    assert by_code["hi-IN"]["native_name"] == "हिन्दी"
    served = languages_api.list_languages().model_dump()["languages"]
    for row in served:
        for value in row.values():
            if isinstance(value, str):
                assert unicodedata.is_normalized("NFC", value)
    DATA.read_bytes().decode("utf-8")  # strict decode must not raise


def test_font_family_matches_script():
    fonts = {r["code"]: r["font_family"] for r in raw_rows()}
    assert fonts == {
        "en-IN": "Noto Sans",
        "ta-IN": "Noto Sans Tamil",
        "hi-IN": "Noto Sans Devanagari",
    }


def test_loader_rejects_bad_files(tmp_path):
    bad_shape = tmp_path / "a.json"
    bad_shape.write_text('{"languages": []}', encoding="utf-8")
    with pytest.raises(languages_api.LanguagesFileError):
        languages_api.load_languages(bad_shape)

    bad_status = tmp_path / "b.json"
    row = dict(raw_rows()[0], prisma="maybe")
    bad_status.write_text(json.dumps([row]), encoding="utf-8")
    with pytest.raises(languages_api.LanguagesFileError):
        languages_api.load_languages(bad_status)

    dup = tmp_path / "c.json"
    dup.write_text(json.dumps([raw_rows()[0], raw_rows()[0]]), encoding="utf-8")
    with pytest.raises(languages_api.LanguagesFileError):
        languages_api.load_languages(dup)

    with pytest.raises(languages_api.LanguagesFileError):
        languages_api.load_languages(tmp_path / "missing.json")


def test_loader_normalises_to_nfc(tmp_path):
    decomposed = unicodedata.normalize("NFD", "é")  # e + combining acute
    row = dict(raw_rows()[0], native_name=decomposed)
    f = tmp_path / "d.json"
    f.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
    assert languages_api.load_languages(f)[0].native_name == "é"


def test_http_route_if_test_client_available():
    pytest.importorskip("httpx")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(languages_api.router)
    res = TestClient(app).get("/api/languages")
    assert res.status_code == 200
    assert res.json() == {"languages": raw_rows()}
    # No ASCII escaping on the wire (contract section 0).
    assert "தமிழ்".encode("utf-8") in res.content
    assert b"\\u0ba4" not in res.content


def test_http_route_error_uses_top_level_contract_envelope(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    missing = tmp_path / "missing-languages.json"
    monkeypatch.setattr(languages_api, "CANDIDATE_PATHS", (missing,))
    app = FastAPI()
    app.include_router(languages_api.router)
    response = TestClient(app).get("/api/languages")
    assert response.status_code == 500
    assert set(response.json()) == {"error"}
    assert response.json()["error"]["code"] == "internal"
    assert set(response.json()["error"]) == {"code", "message", "details"}
