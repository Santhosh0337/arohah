# Open questions (Person B)

Nothing below has been guessed. Items are open until answered.

## Gnani (bible 14.2)
1. **Prisma:** base URL, auth scheme, confirmed language codes, accepted audio format and sample rate, word timestamps and confidence, rate limits, behaviour on sung audio.
2. **Prisma mixed language:** how to declare Hinglish/Tanglish input, and whether word-level language tags come back.
3. **Timbre:** base URL, languages and voices, output audio format and mime type, rate limits, and whether each language wants native script or romanised text.
4. **LLM:** Aion or Evon, the model name string, reliability of JSON output, rate limits.
5. Whether one key covers all three services, and the usage quota for the internship.

## Languages
6. **Demo-language rule conflict.** English, Tamil and Hindi are the chosen demo languages, but bible 16.2 only allows a demo language once Prisma is `confirmed` (and Timbre confirmed or "text explanation only", keywords written, intent tests passed). Today all three are `unconfirmed`. Because the UI enables only `prisma === "confirmed"` languages, every dropdown entry will be disabled until Gnani answers. Do you want a dev-only override, or should we wait for confirmation?
7. Are `en-IN` and `ta-IN` the real Gnani codes? Only `hi-IN` was seen on Gnani's site.
8. Are Hindi and Tamil both covered by Prisma and Timbre? What is the plan if one is not (replace it, or mark it "text explanation only")?

## Contract items still marked [confirm]
9. Project create: async 202 + polling (as written, and what the client assumes) or synchronous.
10. TTS mime type and native-versus-romanised text (same as item 3), and the mixed-language mechanism (item 2). Only B's adapter code changes.
11. Final style ids and labels (`GET /api/styles` is A's).

## Dependencies on Person A (no files outside my paths were touched)
12. `backend/app` may have no `__init__.py`; `providers/__init__.py` works either way, but the import root must be `backend/`.
13. The registry reads `os.environ` only. Whatever starts the app (docker-compose `env_file`, python-dotenv, or A's settings) must put `.env` values into the environment.
14. `backend/requirements.txt` includes `requirements/gnani.txt`; I created it (comments only). Please confirm A has not also created it, to avoid a merge conflict.
15. `pytest` is not in `requirements/gnani.txt` (not mine to pin). Is it in `engine.txt`? My tests need it.
16. Does the root `.gitignore` cover `frontend/node_modules` and `frontend/dist`? I added `frontend/.gitignore` as a safeguard.
17. Which Node version should the team standardise on, and who commits the Prettier/Ruff configs?
18. A's pipeline lyrics stage should treat `provider_status()["prisma"] == "mock"` as: add a `provider_mock` warning and do not show the result as a Gnani result (bible 17.4).

## Added in Phase B2

### For Person A (files I did not touch)
19. **Register the languages router.** `backend/app/api/languages.py` exposes `router = APIRouter(prefix="/api")` with `GET /languages`. If A's auto-loader in `main.py` expects a different attribute name, or adds its own `/api` prefix, tell me and I will change `languages.py` (not `main.py`). Exact manual line if the loader is not ready: `app.include_router(languages.router)`.
20. **Where does `languages.json` live?** The team plan tree puts `data/` under `app/`, but CODEOWNERS and the bible say `backend/data/languages.json`, which is where B1 put it. The route checks both. A's seed/validation code should read it the same way (or import `load_languages` from `app.api.languages`).
21. **CORS** must allow `http://localhost:5173` (`ALLOWED_ORIGINS`) for the browser to call the API. The create flow cannot be tested against the real backend until `POST /api/projects`, `/status` and `/api/audio/{id}` exist.
22. **Audio on create.** The frontend sends the file as recorded or uploaded (`recording.webm`, `recording.m4a`, or the user's file). The only conversion done in the browser is OGG to WAV. A's ingest must accept WebM/Opus and M4A (the bible already says it does).

### Contract items still open (unchanged, now used by the UI)
9. Async create (202 + polling) is implemented in `lib/projectRun.ts`, and is untested against a real backend. Only a stubbed API was used.
23. `GET /api/languages` error shape: I return the contract error body with HTTP 500 if the file is unreadable. Confirm A wants that.

### Product
24. Pre-B3: should "Create project" stay enabled for unverified languages (current dev flag), or be blocked outright in the demo build? Today the flag is on in `.env.example` only.
25. Fonts: who commits the six `.woff2` files after running `npm run fonts` (they are a few hundred KB)? Fontsource CDN path in `scripts/fetch-fonts.mjs` is unverified from my environment.
