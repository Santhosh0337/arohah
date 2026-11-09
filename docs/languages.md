# Languages (Person B)

Source of truth: `backend/data/languages.json`, served by `GET /api/languages` (contract 2.2). Rules: bible section 16.

## Initial demo languages
| Language | Code | Script / font | Prisma | Timbre | Command keywords | Tested |
|---|---|---|---|---|---|---|
| English (India) | `en-IN` | Latn / Noto Sans | unconfirmed | unconfirmed | not written | no |
| Tamil | `ta-IN` | Taml / Noto Sans Tamil | unconfirmed | unconfirmed | not written | no |
| Hindi | `hi-IN` | Deva / Noto Sans Devanagari | unconfirmed | unconfirmed | not written | no |

`demo: true` records the product decision to target these three. It says nothing about provider support. Codes come from the bible matrix (`hi-IN` was seen on Gnani's site; `en-IN` and `ta-IN` are marked "confirm"). Nothing has been tested against Prisma or Timbre.

Mixed-language (Hinglish/Tanglish) is the "mixed language" checkbox, not a language row. How to declare it to Prisma is unknown.

## Future languages
Telugu and Malayalam are planned for later and are not demo commitments. They are not in `languages.json` yet. When added they start as `demo: false` and `unconfirmed`.

## What each status means in the UI
Only `prisma === "confirmed"` languages are selectable for lyrics; `unconfirmed` entries show as "not verified" and are disabled. Until Gnani confirms, all three would be disabled, so Phase B2 adds a dev flag, `VITE_ALLOW_UNVERIFIED_LANGUAGES=true`, that lets the form select `unconfirmed` languages (never `unsupported`). The form then says the setting is on. It changes no status and does not make Prisma work.

## GET /api/languages
Implemented in `backend/app/api/languages.py`. It reads `backend/data/languages.json` (or `backend/app/data/languages.json` if that is where the file is), validates every row, normalises text to NFC, and returns `{ "languages": [...] }` in UTF-8 with no ASCII escaping. The API sends statuses exactly as stored. If the API is unreachable the frontend uses a bundled copy and says so.

## Fonts and scripts
| Language | `font_family` | Files in `public/fonts/` |
|---|---|---|
| English | Noto Sans | `NotoSans-Latin-400.woff2`, `-600` |
| Tamil | Noto Sans Tamil | `NotoSansTamil-400.woff2`, `-600` |
| Hindi | Noto Sans Devanagari | `NotoSansDevanagari-400.woff2`, `-600` |

The files are fetched by `npm run fonts` and are not committed yet. Lyrics and language names carry a `lang` attribute (`ta`, `hi`, `en`).

## To finish a demo language
Prisma confirmed, Timbre confirmed (or "text explanation only"), keywords written in `voice/keywords/`, at least 10 intent utterances at 80% accuracy on the real provider, then tick `tested` with date and evidence in `DECISIONS_B.md`.

## Open questions
See `OPEN_QUESTIONS_B.md` items 1 to 8.
