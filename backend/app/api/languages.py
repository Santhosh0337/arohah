"""GET /api/languages (contract 2.2). Owner: Person B.

Serves backend/data/languages.json as { "languages": [...] }.

The file is the single source of truth (bible 16.2). This route only reads and
validates it: it never edits a status, and it never invents a capability.
Text stays Unicode NFC and is returned as UTF-8 without ASCII escaping.

Router registration: this module exposes `router` (an APIRouter that already
carries the "/api" prefix). Person A's main.py auto-loads routers from api/;
see INTEGRATION_NOTES.md if its convention differs.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models_gnani import Language, LanguagesResponse

# backend/app/api/languages.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]

# The team plan tree and the CODEOWNERS list disagree on the folder, so look in
# both. backend/data/ is the primary location (it is where Phase B1 put it).
CANDIDATE_PATHS: tuple[Path, ...] = (
    _BACKEND_DIR / "data" / "languages.json",
    _BACKEND_DIR / "app" / "data" / "languages.json",
)


class LanguagesFileError(RuntimeError):
    """languages.json is missing or malformed."""


def languages_path() -> Path:
    for path in CANDIDATE_PATHS:
        if path.is_file():
            return path
    tried = ", ".join(str(p) for p in CANDIDATE_PATHS)
    raise LanguagesFileError(f"languages.json not found. Looked in: {tried}")


def _nfc(value):
    """NFC-normalise every string in a loaded JSON value (bible 16.5)."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(v) for v in value]
    if isinstance(value, dict):
        return {_nfc(k): _nfc(v) for k, v in value.items()}
    return value


def load_languages(path: Path | None = None) -> list[Language]:
    """Read and validate languages.json. Raises LanguagesFileError on any problem."""
    src = path or languages_path()
    try:
        with open(src, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise LanguagesFileError(f"Could not read {src}: {exc}") from exc
    if not isinstance(data, list):
        raise LanguagesFileError(f"{src} must contain a JSON array of languages.")
    try:
        languages = [Language(**row) for row in _nfc(data)]
    except (TypeError, ValueError) as exc:  # pydantic ValidationError is a ValueError
        raise LanguagesFileError(f"{src} has an invalid language entry: {exc}") from exc
    codes = [lang.code for lang in languages]
    if len(codes) != len(set(codes)):
        raise LanguagesFileError(f"{src} has duplicate language codes.")
    return languages


router = APIRouter(prefix="/api", tags=["languages"])


@router.get("/languages", response_model=LanguagesResponse)
def list_languages() -> LanguagesResponse:
    try:
        return LanguagesResponse(languages=load_languages())
    except LanguagesFileError as exc:
        # Return the contract envelope at the top level. Raising HTTPException
        # with `detail` would make FastAPI wrap this as {"detail": {"error": ...}}.
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal", "message": str(exc), "details": {}}},
        )
