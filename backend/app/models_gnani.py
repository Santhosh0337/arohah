"""Pydantic schemas for Person B's routes (docs/API_CONTRACT.md).

Phase B2 adds the language models only. Voice and explain schemas arrive in
Phase B4.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ProviderSupport = Literal["confirmed", "unconfirmed", "unsupported"]


class Language(BaseModel):
    """One row of backend/data/languages.json (contract 2.2, bible 16.2)."""

    code: str
    name: str
    native_name: str
    script: str
    font_family: str
    prisma: ProviderSupport
    timbre: ProviderSupport
    command_keywords: bool
    demo: bool
    tested: bool


class LanguagesResponse(BaseModel):
    languages: list[Language]
